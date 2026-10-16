from __future__ import annotations

from pathlib import Path

from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import (
    new_spect_working_project_state,
    set_room_spect_working_state,
)
from services.export_eligibility import assess_export_eligibility
from services.source_readiness import validate_project_source_readiness
from services.spect_report_readiness_contract import (
    SPECT_REPORT_CLOSED_GATE_FIELDS,
    SPECT_REPORT_FORBIDDEN_RESULT_FIELDS,
    SPECT_REPORT_INTEGRATION_OPEN,
    SPECT_REPORT_PERMITTED_RESULT_FIELDS,
    SPECT_REPORT_REQUIRED_RESULT_FIELDS,
    SPECT_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER,
    audit_spect_result_row,
)
from services.spect_results_model import build_room_results_model


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
    return Project(project_name="SPECT Step 28", rooms=[room]), room


def test_step28_current_spect_results_satisfy_frozen_report_allowlist():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    assert rows
    audited = audit_spect_result_row(rows[0])
    assert audited["report_integration_open"] is False
    assert audited["ready_for_future_adapter"] is True
    assert audited["missing_required_fields"] == []
    assert audited["closed_gate_mismatches"] == []
    assert tuple(audited["permitted_result_payload"].keys()) == SPECT_REPORT_PERMITTED_RESULT_FIELDS


def test_step28_allowlist_excludes_ui_only_fields_and_requires_source_adapter():
    assert SPECT_REPORT_INTEGRATION_OPEN is False
    assert len(SPECT_REPORT_PERMITTED_RESULT_FIELDS) == 30
    assert SPECT_REPORT_REQUIRED_RESULT_FIELDS == SPECT_REPORT_PERMITTED_RESULT_FIELDS
    assert not set(SPECT_REPORT_FORBIDDEN_RESULT_FIELDS) & set(SPECT_REPORT_PERMITTED_RESULT_FIELDS)
    assert SPECT_REPORT_CLOSED_GATE_FIELDS == {
        "output_eligible": False,
        "report_integration_enabled": False,
        "certification_enabled": False,
    }
    assert "radionuclide" in SPECT_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER
    assert "administered_activity_mbq" in SPECT_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER
    assert "source_position_x_m" in SPECT_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER


def test_step28_low_transmission_nonreportable_dose_remains_suppressed():
    project, room = _project(lead_mm=3.0)
    rows = build_room_results_model(project, room, fallback_results=[])
    lead = rows[0]
    assert lead["compliance_status"] == "PASS"
    assert lead["transmitted_dose_reportable"] is False
    assert lead["transmitted_dose_uSv_per_week"] is None
    audited = audit_spect_result_row(lead)
    assert audited["ready_for_future_adapter"] is True
    assert audited["permitted_result_payload"]["transmitted_dose_uSv_per_week"] is None


def test_step28_report_readiness_contract_is_not_imported_by_report_modules():
    forbidden_tokens = (
        "spect_results_model",
        "spect_results_presentation_contract",
        "spect_report_readiness_contract",
        "build_spect_production_results_payload",
    )
    for path in Path("reports").glob("*.py"):
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden_tokens:
            assert token not in text, f"{path} must not import Step 27/28 SPECT report boundary"


def test_step28_results_payload_builder_has_no_spect_report_adapter_integration():
    text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8-sig")
    assert "spect_report_readiness_contract" not in text
    assert "spect_results_model" not in text
    assert "build_spect_production_results_payload" not in text


def test_step28_persisted_spect_still_blocks_issueable_outputs():
    project, _room = _project()
    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(
        preflight=readiness,
        requested_report_status="Final",
    )
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_step28_contract_fails_closed_on_missing_required_or_open_gate():
    project, room = _project()
    row = build_room_results_model(project, room, fallback_results=[])[0]
    missing = dict(row)
    missing.pop("request_sha256")
    audited_missing = audit_spect_result_row(missing)
    assert audited_missing["ready_for_future_adapter"] is False
    assert audited_missing["missing_required_fields"] == ["request_sha256"]

    opened = dict(row)
    opened["report_integration_enabled"] = True
    audited_opened = audit_spect_result_row(opened)
    assert audited_opened["ready_for_future_adapter"] is False
    assert audited_opened["closed_gate_mismatches"] == ["report_integration_enabled"]


def test_step28_audit_document_records_no_go_and_next_boundary():
    text = Path("docs/architecture/SPECT_Report_Readiness_Audit_Step_28.md").read_text(encoding="utf-8-sig")
    assert "SPECT_REPORT_INTEGRATION_OPEN = False" in text
    assert "All 30 fields are required" in text
    assert "NO-GO for opening SPECT PDF/report generation" in text
    assert "SPECT Step 29 — non-issueable report-payload adapter harness" in text
    assert "PDF/CSV/certification remain unavailable" in text
