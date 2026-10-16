from __future__ import annotations

from pathlib import Path

import pytest

from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import (
    new_spect_working_project_state,
    set_room_spect_working_state,
)
from services.source_readiness import validate_project_source_readiness
from services.spect_results_model import (
    SPECT_RESULTS_PAYLOAD_SCHEMA,
    SPECT_RESULTS_PAYLOAD_VERSION,
    build_room_results_model,
    build_spect_production_results_payload,
)
from services.spect_results_presentation_contract import (
    SPECT_RESULTS_NON_ISSUEABLE_NOTE,
    SPECT_RESULTS_PRESENTATION_BASELINE,
    SPECT_RESULTS_PRESENTATION_CONTRACT_VERSION,
    spect_results_room_lines,
)


def _project(*, lead_mm: float = 1.0):
    room = Room(
        name="SPECT Room",
        modality="SPECT",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy=f"Pb {lead_mm} mm",
                thickness_mm=lead_mm,
                distance_m=2.0,
                occupancy_factor=1.0,
                design_goal_uSv_per_week=1.0,
            ),
            Barrier(
                name="South wall",
                material="Concrete",
                material_legacy="Concrete 150 mm",
                thickness_mm=150.0,
                distance_m=3.0,
                occupancy_factor=0.25,
                design_goal_uSv_per_week=10.0,
            ),
        ],
    )
    source = SpectSourceDomain(
        radionuclide="Tc99m",
        administered_activity_mbq=600.0,
        patients_per_week=20.0,
        imaging_duration_h=0.5,
    )
    set_room_spect_working_state(room, new_spect_working_project_state(source))
    return Project(project_name="SPECT Step 27", rooms=[room]), room


def test_step27_builds_production_results_payload_from_step26_dispatch():
    project, room = _project()
    payload = build_spect_production_results_payload(project, room)
    assert payload.schema == SPECT_RESULTS_PAYLOAD_SCHEMA
    assert payload.schema_version == SPECT_RESULTS_PAYLOAD_VERSION
    assert payload.production_eligible is True
    assert payload.output_eligible is False
    assert payload.report_integration_enabled is False
    assert payload.certification_enabled is False
    assert len(payload.rows) == 2
    assert len(payload.request_sha256) == 64
    assert all(row["results_source"] == "spect_step26_production_dispatch" for row in payload.rows)
    assert all(row["source_type"] == "spect_patient" for row in payload.rows)
    assert all(row["production_eligible"] is True for row in payload.rows)
    assert all(row["output_eligible"] is False for row in payload.rows)


def test_step27_results_rows_use_step25_production_decision_and_contract():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    assert rows
    for row in rows:
        assert row["results_presentation_contract_version"] == SPECT_RESULTS_PRESENTATION_CONTRACT_VERSION
        assert row["results_presentation_baseline"] == SPECT_RESULTS_PRESENTATION_BASELINE
        assert row["compliance_status"] in {"PASS", "FAIL", "NOT_ASSESSED"}
        assert "policy_decision_basis" in row
        assert row["policy_status"] == "approved_locked"


def test_step27_results_payload_is_deterministic():
    project, room = _project()
    first = build_spect_production_results_payload(project, room).as_dict()
    second = build_spect_production_results_payload(project, room).as_dict()
    assert first == second


def test_step27_nonreportable_ultralow_provided_dose_is_suppressed():
    # The required target remains >1%, so Step 26 dispatch is allowed, while the
    # extra provided lead drives the modeled provided transmission into the <=1%
    # caution region. Step 25 permits thickness acceptance but forbids using that
    # ultralow transmitted-dose prediction as production evidence.
    project, room = _project(lead_mm=3.0)
    payload = build_spect_production_results_payload(project, room)
    lead = payload.rows[0]
    assert lead["compliance_status"] == "PASS"
    assert lead["transmitted_dose_reportable"] is False
    assert lead["transmitted_dose_uSv_per_week"] is None


def test_step27_low_transmission_required_target_still_fails_closed():
    project, room = _project()
    room.barriers[0].distance_m = 1.0
    room.barriers[0].design_goal_uSv_per_week = 0.5
    with pytest.raises(Exception, match="Step 25 low-transmission policy"):
        build_spect_production_results_payload(project, room)


def test_step27_results_presentation_is_explicitly_non_issueable():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    text = "\n".join(line for line, _tag in spect_results_room_lines(room.name, rows))
    assert SPECT_RESULTS_NON_ISSUEABLE_NOTE in text
    assert "SPECT Tc-99m production calculation results" in text
    assert "Request SHA-256:" in text
    assert "Step 25 production status:" in text


def test_step27_does_not_remove_step22_output_blocker():
    project, room = _project()
    assert build_room_results_model(project, room, fallback_results=[])
    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True


def test_step27_report_export_certification_modules_do_not_import_spect_results_adapter():
    forbidden = (
        "spect_results_model",
        "spect_results_presentation_contract",
        "build_spect_production_results_payload",
    )
    roots = [Path("reports"), Path("services")]
    excluded = {
        Path("services/spect_results_model.py"),
        Path("services/spect_results_presentation_contract.py"),
    }
    checked = []
    for root in roots:
        for path in root.glob("*.py"):
            if path in excluded:
                continue
            name = path.name.lower()
            if root.name == "services" and not any(token in name for token in ("export", "cert", "report")):
                continue
            checked.append(path)
            text = path.read_text(encoding="utf-8-sig")
            for token in forbidden:
                assert token not in text, f"{path} must not import Step 27 SPECT Results integration"
    assert checked


def test_step27_desktop_results_rendering_knows_spect_contract_but_output_pipeline_does_not():
    app_text = Path("app.py").read_text(encoding="utf-8-sig")
    rendering = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8-sig")
    output_pipeline = Path("reports/output_pipeline.py").read_text(encoding="utf-8-sig")
    assert "build_spect_results_model" in app_text
    assert "spect_results_room_lines" in rendering
    assert "spect_results_model" not in output_pipeline
    assert "spect_results_presentation_contract" not in output_pipeline
