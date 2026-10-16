"""Regression guards for the SPECT Step 19 production-readiness boundary audit.

Step 19 is audit-only.  These tests freeze the current closed production
boundaries and make the principal NO-GO findings executable so a later step
must intentionally update the audit when a boundary is opened.
"""
from pathlib import Path
from types import SimpleNamespace

from engine.spect_barrier_schedule import (
    SPECT_BARRIER_SCHEDULE_STATUS,
    SpectBarrierScheduleRequest,
    calculate_spect_tc99m_barrier_schedule,
)
from modalities.registry import (
    locked_source_mapping,
    production_modality_names,
    source_calculation_blocked_reason,
    source_type_options,
)
from modalities.spect import (
    SPECT_CALCULATION_BLOCK_REASON,
    SpectSourceDomain,
)
from services.source_readiness import validate_room_source_readiness


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "architecture" / "SPECT_Production_Readiness_Boundary_Audit_Step_19.md"


def _metadata(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))["metadata"]


def test_step19_audit_document_records_no_go_and_step20_recommendation():
    text = AUDIT.read_text(encoding="utf-8")
    assert "Decision: NO-GO for production enablement" in text
    assert "SPECT Step 20 — physics dataset approval/freeze" in text
    assert "do not enable SPECT production selection" in text


def test_step19_registry_guard_evolves_at_step34_but_generic_calculator_stays_closed():
    assert "SPECT" in production_modality_names()
    assert "spect_patient" in source_type_options(production_only=True)
    assert ("spect_patient", "SPECT Patient Source") in locked_source_mapping(production_only=True)["SPECT"]
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON


def test_step19_all_spect_physics_datasets_remain_explicitly_nonproduction():
    paths = (
        ROOT / "data" / "spect" / "spect_radionuclide_physics_development.json",
        ROOT / "data" / "spect" / "spect_tc99m_attenuation_development.json",
        ROOT / "data" / "spect" / "spect_tc99m_practical_transmission_development.json",
    )
    for path in paths:
        assert _metadata(path)["approval_status"] == "development_nonproduction"


def test_step19_radionuclide_dataset_still_declares_pending_source_constant_approval():
    import json
    payload = json.loads(
        (ROOT / "data" / "spect" / "spect_radionuclide_physics_development.json").read_text(
            encoding="utf-8"
        )
    )
    record = payload["records"][0]
    assert record["code"] == "Tc99m"
    assert "pending separate dataset approval" in record["dose_rate_provenance"]


def test_step19_practical_schedule_remains_nonproduction():
    source = SpectSourceDomain(
        radionuclide="Tc99m",
        administered_activity_mbq=600.0,
        patients_per_week=20.0,
        imaging_duration_h=0.5,
    )
    schedule = calculate_spect_tc99m_barrier_schedule(
        source,
        (
            SpectBarrierScheduleRequest(
                barrier_id="N",
                barrier_name="North wall",
                material_key="lead",
                distance_m=2.0,
                occupancy_factor=1.0,
                design_goal_uSv_per_week=10.0,
            ),
        ),
    )
    assert schedule.status == SPECT_BARRIER_SCHEDULE_STATUS
    assert schedule.production_eligible is False


def test_step19_source_readiness_gap_is_now_closed_by_step22():
    """Step 19 identified this gap; Step 22 must keep it fail-closed."""

    room = SimpleNamespace(
        name="SPECT Room 1",
        modality="SPECT",
        modality_state={},
        sources=[],
    )
    source = SimpleNamespace(
        name="SPECT Patient Source",
        source_type="spect_patient",
        radiation_type="tc99m_140kev",
        params={},
    )
    result = validate_room_source_readiness(
        room,
        get_sources_for_room=lambda _room_name: [source],
    )

    assert result["source_results"][0]["overall_status"] == "REVIEW"
    assert result["source_results"][0]["blocking"] is False
    assert result["source_results"][0]["output_blocking"] is True
    assert result["errors"] == []
    assert result["blocking"] is False
    assert result["overall_status"] == "REVIEW"


def test_step19_preview_contracts_stay_out_of_production_and_report_paths():
    forbidden_tokens = (
        "calculate_spect_tc99m_barrier_schedule",
        "SpectBarrierScheduleResult",
        "SPECT_UI_DECISION_SUMMARY_BASELINE",
        "radshield_spect_ui_preview_state_v1",
    )
    paths = [
        ROOT / "app.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "services" / "project_serializer.py",
    ]
    paths.extend((ROOT / "reports").glob("*.py"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{token} leaked into production/report path {path}"


def test_step19_changes_are_audit_and_test_only():
    """Step 19 itself must not require a production-code implementation change."""

    assert AUDIT.exists()
    this_test = ROOT / "tests" / "test_spect_step19_production_readiness_audit.py"
    assert this_test.exists()
