"""Step 39 PET/SPECT common non-issueable report payload and PET policy guards."""
from pathlib import Path

import pytest

from engine.pet_ultralow_transmission_policy import (
    PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED,
    PET_ULTRALOW_TRANSMISSION_POLICY_BASIS,
    PET_ULTRALOW_TRANSMISSION_POLICY_STATUS,
    PET_ULTRALOW_TRANSMISSION_POLICY_VERSION,
    PET_ULTRALOW_TRANSMISSION_REVIEW_STATUS,
    PET_ULTRALOW_TRANSMISSION_THRESHOLD,
    assess_pet_production_barrier_policy,
)
from services.pet_spect_production_output_readiness import assess_pet_spect_production_output_readiness
from services.pet_spect_report_payload_adapter import (
    PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE,
    PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN,
    PetSpectReportPayloadAdapterError,
    build_non_issueable_pet_spect_report_payload,
)
from services.pet_spect_report_payload_readiness import require_step39_foundations_ready

ROOT = Path(__file__).resolve().parents[1]


def _pet_source_payload():
    return {"source_summary": {
        "radionuclide": "F18",
        "administered_activity_mbq_per_patient": 250.0,
        "patients_per_week": 50.0,
        "activity_scaling_factor": 1.0,
        "exposure_periods": [{
            "name": "Uptake",
            "start_after_administration_h": 0.0,
            "duration_h": 1.0,
            "activity_retention_factor": 1.0,
        }],
        "pet_position_west_m": 3.0,
        "pet_position_south_m": 2.0,
        "pet_position_height_affl_m": 1.0,
        "provenance_manifest_id": "pet-manifest",
        "provenance_manifest_revision": "r1",
        "radionuclide_dataset_id": "pet-radionuclides",
        "radionuclide_dataset_revision": "r1",
        "radionuclide_records_sha256": "a" * 64,
        "attenuation_dataset_id": "pet-attenuation",
        "attenuation_dataset_revision": "r1",
        "attenuation_records_sha256": "b" * 64,
        "physics_contract_version": 1,
        "solver_contract_version": 1,
    }}


def _pet_row(*, required_b=0.1, required_mm=10.0, provided_mm=12.0, provided_b=0.05, transmitted=0.5):
    return {
        "results_model_contract_version": 2,
        "results_source": "persisted_pet_single_source",
        "source_type": "pet_patient",
        "barrier_name": "North wall",
        "solver_mode": "isotropic_non_beam_tvl",
        "material": "Lead",
        "distance_m": 3.0,
        "occupancy_factor": 1.0,
        "design_goal_uSv_per_week": 10.0,
        "unshielded_weekly_dose_uSv": 200.0,
        "occupied_unshielded_weekly_dose_uSv": 200.0,
        "barrier_transmission_factor_B": required_b,
        "required_tvl_count": 1.0,
        "required_thickness_mm": required_mm,
        "provided_thickness_mm": provided_mm,
        "provided_transmission": provided_b,
        "transmitted_dose_uSv_per_week": transmitted,
        "margin_mm": provided_mm - required_mm,
        "compliance_status": "PASS" if provided_mm >= required_mm else "FAIL",
        "calculation_reasoning": "Replay-verified PET calculation.",
        "provenance_manifest_id": "pet-manifest",
        "provenance_manifest_revision": "r1",
        "radionuclide_dataset_id": "pet-radionuclides",
        "radionuclide_dataset_revision": "r1",
        "radionuclide_records_sha256": "a" * 64,
        "attenuation_dataset_id": "pet-attenuation",
        "attenuation_dataset_revision": "r1",
        "attenuation_records_sha256": "b" * 64,
        "physics_contract_version": 1,
        "solver_contract_version": 1,
        "replay_verified": True,
    }


def _spect_source_payload():
    return {"source_summary": {
        "radionuclide": "Tc99m",
        "administered_activity_mbq": 600.0,
        "patients_per_week": 20.0,
        "imaging_duration_h": 0.5,
        "source_position_x_m": 3.0,
        "source_position_y_m": 2.0,
        "physics_freeze": {"freeze_id": "spect-physics-step20-2026-08-23"},
    }}


def _spect_row(*, reportable=True, transmitted=0.5):
    return {
        "results_model_contract_version": 1,
        "results_source": "spect_step26_production_dispatch",
        "source_type": "spect_patient",
        "barrier_name": "East wall",
        "barrier_id": "east-wall",
        "solver_mode": "spect_tc99m_practical_archer",
        "material": "Lead",
        "material_key": "lead",
        "distance_m": 3.0,
        "occupancy_factor": 1.0,
        "design_goal_uSv_per_week": 10.0,
        "unshielded_weekly_dose_uSv": 100.0,
        "occupied_unshielded_weekly_dose_uSv": 100.0,
        "barrier_transmission_factor_B": 0.1,
        "required_thickness_mm": 1.0,
        "provided_thickness_mm": 1.2,
        "provided_transmission": 0.05 if reportable else 0.005,
        "transmitted_dose_uSv_per_week": transmitted if reportable else None,
        "transmitted_dose_reportable": reportable,
        "compliance_status": "PASS",
        "margin_mm": 0.2,
        "calculation_reasoning": "Approved SPECT production calculation.",
        "production_eligible": True,
        "output_eligible": False,
        "report_integration_enabled": False,
        "certification_enabled": False,
        "request_sha256": "c" * 64,
        "physics_freeze": {"freeze_id": "spect-physics-step20-2026-08-23"},
        "policy_version": 1,
        "policy_status": "approved_locked",
        "policy_decision_basis": "Step 25 thickness assessment.",
        "practical_record_id": "lead",
        "practical_provenance": "approved",
    }


def test_step39_pet_ultralow_policy_is_approved_locked_and_explicitly_a_radshield_boundary():
    assert PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED is True
    assert PET_ULTRALOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
    assert PET_ULTRALOW_TRANSMISSION_POLICY_VERSION == 1
    assert PET_ULTRALOW_TRANSMISSION_THRESHOLD == 0.01
    assert "software-validation" in PET_ULTRALOW_TRANSMISSION_POLICY_BASIS
    assert "not a TG-108 physical threshold" in PET_ULTRALOW_TRANSMISSION_POLICY_BASIS


def test_step39_pet_required_transmission_at_or_below_one_percent_requires_review():
    decision = assess_pet_production_barrier_policy(_pet_row(required_b=0.01))
    assert decision.status == PET_ULTRALOW_TRANSMISSION_REVIEW_STATUS
    assert decision.automatic_assessment_allowed is False
    assert decision.production_transmitted_dose_reportable is False


def test_step39_pet_supported_required_region_uses_thickness_and_suppresses_ultralow_provided_dose():
    decision = assess_pet_production_barrier_policy(
        _pet_row(required_b=0.05, required_mm=10.0, provided_mm=12.0, provided_b=0.005)
    )
    assert decision.status == "PASS"
    assert decision.automatic_assessment_allowed is True
    assert decision.production_transmitted_dose_reportable is False


def test_step39_common_pet_payload_consumes_results_and_suppresses_nonreportable_dose():
    payload = build_non_issueable_pet_spect_report_payload(
        modality="PET",
        source_payload=_pet_source_payload(),
        result_rows=[_pet_row(required_b=0.05, provided_b=0.005, transmitted=0.25)],
    )
    assert payload["modality"] == "PET"
    assert payload["non_issueable"] is True
    assert payload["issueable"] is False
    barrier = payload["barriers"][0]
    assert barrier["assessment_status"] == "PASS"
    assert barrier["transmitted_dose_reportable"] is False
    assert barrier["transmitted_dose_uSv_per_week"] is None
    assert barrier["result_payload"]["transmitted_dose_uSv_per_week"] is None


def test_step39_common_pet_payload_fails_closed_when_physicist_review_is_required():
    with pytest.raises(PetSpectReportPayloadAdapterError, match="requires physicist review"):
        build_non_issueable_pet_spect_report_payload(
            modality="PET",
            source_payload=_pet_source_payload(),
            result_rows=[_pet_row(required_b=0.005)],
        )


def test_step39_common_spect_payload_preserves_step25_reportability_boundary():
    payload = build_non_issueable_pet_spect_report_payload(
        modality="SPECT",
        source_payload=_spect_source_payload(),
        result_rows=[_spect_row(reportable=False)],
    )
    barrier = payload["barriers"][0]
    assert barrier["assessment_status"] == "PASS"
    assert barrier["transmitted_dose_reportable"] is False
    assert barrier["transmitted_dose_uSv_per_week"] is None
    assert barrier["policy_status"] == "approved_locked"


def test_step39_common_adapter_is_closed_and_has_no_generic_calculation_or_output_dependencies():
    assert PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE is False
    assert PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN is False
    text = (ROOT / "services" / "pet_spect_report_payload_adapter.py").read_text(encoding="utf-8")
    forbidden = (
        "engine.shielding_engine",
        "compute_room_barrier_table",
        "calc_barrier_result",
        "reports.results_payload_builder",
        "reports.report_generator",
        "reports.output_pipeline",
        "export_eligibility",
        "report_certification",
        "import app",
    )
    assert all(token not in text for token in forbidden)


def test_step39_foundations_feed_step40_normal_report_route_without_opening_output():
    result = assess_pet_spect_production_output_readiness()
    checks = {item["check_id"]: item for item in result["checks"]}
    assert result["pet_ultralow_transmission_policy_ready"] is True
    assert checks["pet_ultralow_transmission_policy_explicit"]["passed"] is True
    assert result["normal_report_payload_ready"] is True
    assert result["production_output_enablement_ready"] is False
    assert result["report_pipeline_state"]["generic_builder_dispatch"] is True  # CT only
    assert result["report_pipeline_state"]["generic_schedule_fallback"] is False


def test_step39_readiness_gate_is_green_while_issued_output_remains_closed():
    result = require_step39_foundations_ready()
    assert result["pet_ultralow_policy_ready"] is True
    assert result["common_non_issueable_payload_adapter_ready"] is True
    assert result["normal_report_integration_ready"] is True
    assert result["issued_pdf_ready"] is False
    assert result["machine_export_ready"] is False
    assert result["certification_ready"] is False


def test_step39_cli_reports_ready_adapter_but_closed_output(capsys):
    from tools import pet_spect_report_payload_readiness

    assert pet_spect_report_payload_readiness.main() == 0
    out = capsys.readouterr().out
    assert "PET/SPECT STEP 39 COMMON REPORT PAYLOAD READINESS" in out
    assert "PET ultralow policy ready: YES" in out
    assert "Common non-issueable payload adapter ready: YES" in out
    assert "Normal report integration ready: YES" in out
    assert "Issued PDF ready: NO" in out
