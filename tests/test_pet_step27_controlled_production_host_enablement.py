from __future__ import annotations

import copy

from geometry.pet_preview_position import PetPreviewPosition
from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PET_ISSUED_OUTPUT_BLOCK_REASON,
    PetExposurePhase,
    PetSourceDomain,
    pet_source_readiness_result,
)
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
    PetWorkingProjectState,
    pet_working_project_state_from_dict,
    pet_working_project_state_to_dict,
)
from services.pet_host_integration_gate import (
    PET_HOST_INTEGRATION_BASELINE,
    PET_HOST_INTEGRATION_CONTRACT_VERSION,
    assess_pet_host_integration_readiness,
    require_pet_host_integration_ready,
)
from services.pet_report_readiness_contract import PET_REPORT_INTEGRATION_OPEN


def _state() -> PetWorkingProjectState:
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


def test_step27_promotes_pet_through_registry_but_keeps_legacy_generic_dispatch_closed():
    assert "PET" in production_modality_names()
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON


def test_step27_current_working_state_declares_host_and_calculation_enabled_output_closed():
    payload = pet_working_project_state_to_dict(_state())
    assert payload["schema"] == PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3"
    assert payload["schema_version"] == PET_WORKING_PROJECT_STATE_VERSION == 3
    assert payload["production_host_enabled"] is True
    assert payload["production_calculation_enabled"] is True
    assert payload["issued_output_enabled"] is False


def test_step27_legacy_v2_working_state_remains_readable_and_migrates_to_v3():
    current = pet_working_project_state_to_dict(_state())
    legacy = {
        "schema": PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
        "schema_version": PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
        "production_eligible": False,
        "single_source_per_room": True,
        "provenance_manifest": copy.deepcopy(current["provenance_manifest"]),
        "position": copy.deepcopy(current["position"]),
        "source": copy.deepcopy(current["source"]),
    }
    restored = pet_working_project_state_from_dict(legacy)
    migrated = pet_working_project_state_to_dict(restored)
    assert migrated["schema"] == PET_WORKING_PROJECT_STATE_SCHEMA
    assert migrated["production_host_enabled"] is True
    assert migrated["issued_output_enabled"] is False


def test_step27_source_readiness_allows_calculation_results_but_hard_blocks_output():
    result = pet_source_readiness_result(
        "pet_patient",
        {},
        {"room_name": "PET Room 1", "source_name": "PET Patient Source"},
    )
    assert result["overall_status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["output_blocking"] is True
    assert result["errors"] == []
    assert result["message"] == PET_ISSUED_OUTPUT_BLOCK_REASON


def test_step27_host_gate_is_ready_but_issued_outputs_remain_closed():
    result = require_pet_host_integration_ready()
    assert result["host_integration_ready"] is True
    assert result["working_project_enabled"] is True
    assert result["production_calculation_enabled"] is True
    assert result["in_app_results_enabled"] is True
    assert result["issued_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["certification_enabled"] is False
    assert PET_REPORT_INTEGRATION_OPEN is False


def test_step27_contract_identity_is_frozen():
    result = assess_pet_host_integration_readiness()
    assert PET_HOST_INTEGRATION_CONTRACT_VERSION == 1
    assert PET_HOST_INTEGRATION_BASELINE == "pet-production-host-integration-step27-v1-controlled"
    assert result["blocking_reasons"] == []
