from geometry.pet_preview_position import PetPreviewPosition
from modalities.pet import PET_CALCULATION_BLOCK_REASON, PetExposurePhase, PetSourceDomain
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from serialization.pet_working_project_state import PetWorkingProjectState
from services.pet_production_host_readiness_gate import (
    PET_PRODUCTION_HOST_INTEGRATION_ENABLED,
    PET_PRODUCTION_HOST_READINESS_BASELINE,
    PET_PRODUCTION_HOST_READINESS_CONTRACT_VERSION,
    audit_pet_production_host_readiness,
)
from services.pet_report_readiness_contract import PET_REPORT_INTEGRATION_OPEN
from tools import pet_production_host_readiness


def _state():
    return PetWorkingProjectState(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            residual_activity_factor=1.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0, 1.0),),
        ),
        position=PetPreviewPosition(2.0, 2.0, 1.0),
    )


def test_step26_foundations_now_support_controlled_host_promotion():
    result = audit_pet_production_host_readiness(sample_state=_state())
    assert result["validated_foundations"] is True
    assert result["production_host_integration_enabled"] is True
    assert result["production_host_ready"] is True
    assert result["issued_output_enabled"] is False
    assert result["blocking_checks"] == []


def test_step26_records_promoted_host_and_next_parity_target():
    assert "PET" in production_modality_names()
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON
    result = audit_pet_production_host_readiness(sample_state=_state())
    assert "non-issueable PDF" in result["recommended_next_step"]
    assert "issued output closed" in result["recommended_next_step"]


def test_step26_does_not_open_report_or_issueable_output_boundaries():
    assert PET_REPORT_INTEGRATION_OPEN is False
    assert PET_PRODUCTION_HOST_INTEGRATION_ENABLED is True
    result = audit_pet_production_host_readiness(sample_state=_state())
    issued = next(row for row in result["checks"] if row["name"] == "issued_output_boundary_closed")
    assert issued["status"] == "PASS"


def test_step26_contract_identity_is_frozen():
    assert PET_PRODUCTION_HOST_READINESS_CONTRACT_VERSION == 1
    assert PET_PRODUCTION_HOST_READINESS_BASELINE == "pet-production-host-readiness-step26-v1"


def test_step26_cli_reports_promoted_host_without_subprocess(capsys):
    assert pet_production_host_readiness.main() == 0
    output = capsys.readouterr().out
    assert "PET STEP 26 PRODUCTION-HOST READINESS" in output
    assert "Validated foundations: YES" in output
    assert "Production host integration enabled: YES" in output
    assert "Production host ready: YES" in output
    assert "Issued PDF/export/certification enabled: NO" in output
