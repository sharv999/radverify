"""Step 38 combined PET/SPECT production-output readiness audit guards."""
from pathlib import Path

from services.pet_spect_production_output_readiness import (
    PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT,
    STEP38_AUDIT_ONLY,
    STEP38_ISSUED_OUTPUT_ENABLEMENT,
    assess_pet_spect_production_output_readiness,
    require_step38_audit_foundations_valid,
)

ROOT = Path(__file__).resolve().parents[1]


def _checks(result):
    return {check["check_id"]: check for check in result["checks"]}


def test_step38_completed_pet_and_spect_production_host_foundations_remain_green():
    result = require_step38_audit_foundations_valid()
    assert result["pet_calculation_production_ready"] is True
    assert result["spect_calculation_production_ready"] is True
    assert result["pet_report_preview_foundations_ready"] is True
    assert result["spect_report_preview_foundations_ready"] is True


def test_step38_is_audit_only_and_does_not_enable_output():
    result = assess_pet_spect_production_output_readiness()
    assert STEP38_AUDIT_ONLY is True
    assert STEP38_ISSUED_OUTPUT_ENABLEMENT is False
    assert result["issued_output_enablement"] is False
    assert result["issued_pdf_ready"] is False
    assert result["machine_export_ready"] is False
    assert result["certification_ready"] is False
    assert result["production_output_enablement_ready"] is False


def test_step38_recognises_step40_normal_report_modal_results_integration():
    result = assess_pet_spect_production_output_readiness()
    checks = _checks(result)
    assert result["report_pipeline_state"]["generic_builder_dispatch"] is True  # CT path remains
    assert result["report_pipeline_state"]["consumes_modal_results"] is True
    assert result["normal_report_payload_ready"] is True
    assert checks["normal_report_uses_pet_spect_results_source_of_truth"]["passed"] is True


def test_step38_recognises_step40_pet_spect_schedule_fallback_is_disabled():
    result = assess_pet_spect_production_output_readiness()
    checks = _checks(result)
    assert result["report_pipeline_state"]["generic_schedule_fallback"] is False
    assert result["report_pipeline_state"]["pet_spect_fail_closed_schedule"] is True
    assert checks["canonical_schedule_has_no_pet_spect_generic_recalculation_fallback"]["passed"] is True


def test_step38_spect_and_pet_low_transmission_policies_are_locked_after_step39():
    result = assess_pet_spect_production_output_readiness()
    checks = _checks(result)
    assert result["spect_low_transmission_policy_ready"] is True
    assert checks["spect_low_transmission_policy_locked"]["passed"] is True
    assert PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT is True
    assert result["pet_ultralow_transmission_policy_ready"] is True
    assert checks["pet_ultralow_transmission_policy_explicit"]["passed"] is True


def test_step38_issued_pdf_and_machine_output_gates_remain_closed():
    result = assess_pet_spect_production_output_readiness()
    checks = _checks(result)
    assert checks["issued_pdf_gates_closed"]["passed"] is True
    assert checks["machine_export_and_certification_closed"]["passed"] is True


def test_step38_report_routing_blockers_are_resolved_after_step40_but_output_stays_closed():
    result = assess_pet_spect_production_output_readiness()
    text = "\n".join(result["blocking_reasons"])
    assert "generic shielding engine" not in text
    assert "generic recalculation" not in text
    assert "PET has no explicit production policy" not in text
    assert result["normal_report_payload_ready"] is True
    assert result["production_output_enablement_ready"] is False
    assert "payload-equivalence" in result["recommended_next_boundary"]


def test_step38_audit_is_not_imported_by_existing_issueable_output_modules():
    forbidden = "pet_spect_production_output_readiness"
    paths = [
        ROOT / "reports" / "results_payload_builder.py",
        ROOT / "reports" / "report_generator.py",
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "services" / "export_eligibility.py",
        ROOT / "services" / "report_certification.py",
    ]
    assert all(forbidden not in path.read_text(encoding="utf-8") for path in paths)


def test_step38_cli_reports_no_go_without_subprocess(capsys):
    from tools import pet_spect_production_output_readiness

    assert pet_spect_production_output_readiness.main() == 0
    out = capsys.readouterr().out
    assert "PET/SPECT STEP 38 PRODUCTION OUTPUT READINESS AUDIT" in out
    assert "PET calculation production ready: YES" in out
    assert "SPECT calculation production ready: YES" in out
    assert "Normal issued-report payload ready: YES" in out
    assert "Production output enablement: NO-GO" in out


def test_step38_document_records_split_decision_and_next_boundary():
    text = (
        ROOT / "docs" / "architecture" / "PET_SPECT_Production_Output_Readiness_Audit_Step_38.md"
    ).read_text(encoding="utf-8")
    assert "PET calculation production ready: **YES**" in text
    assert "SPECT calculation production ready: **YES**" in text
    assert "Production output enablement: **NO-GO**" in text
    assert "generic `compute_room_barrier_table()`" in text
    assert "PET ultralow-transmission" in text
    assert "Step 39" in text
