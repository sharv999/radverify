"""Step 27 controlled PET production-host integration gate.

The gate proves that PET may participate in the normal desktop host for room
selection, durable working-project persistence, replay-verified production
calculation, and in-app Results while all issued-output paths remain closed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PET_ISSUED_OUTPUT_BLOCK_REASON,
    pet_source_readiness_result,
)
from modalities.registry import (
    coming_soon_modality_names,
    production_modality_names,
    source_calculation_blocked_reason,
)
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
)
from services.pet_production_host_readiness_gate import audit_pet_production_host_readiness
from services.pet_report_readiness_contract import PET_REPORT_INTEGRATION_OPEN

PET_HOST_INTEGRATION_CONTRACT_VERSION = 1
PET_HOST_INTEGRATION_BASELINE = "pet-production-host-integration-step27-v1-controlled"
PET_HOST_INTEGRATION_ENABLED = True
PET_ISSUED_OUTPUT_INTEGRATION_ENABLED = False


class PetHostIntegrationError(RuntimeError):
    """Raised when the controlled PET host boundary is not satisfied."""


@dataclass(frozen=True)
class PetHostIntegrationCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_pet_host_integration_readiness() -> dict[str, Any]:
    step26 = audit_pet_production_host_readiness()
    readiness = pet_source_readiness_result(
        "pet_patient",
        {},
        {"room_name": "PET host audit", "source_name": "PET Patient Source"},
    )
    checks = (
        PetHostIntegrationCheck(
            "registry_host_enabled",
            "PET" in production_modality_names() and "PET" not in coming_soon_modality_names(),
            "PET is selectable through the registry-driven production host room path.",
        ),
        PetHostIntegrationCheck(
            "working_state_host_semantics",
            PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3"
            and PET_WORKING_PROJECT_STATE_VERSION == 3,
            "PET working state is v3 with production-host/calculation enabled and issued output disabled.",
        ),
        PetHostIntegrationCheck(
            "step26_foundations_ready",
            step26.get("validated_foundations") is True
            and step26.get("production_host_integration_enabled") is True,
            "Approved physics, replay dispatch, Results, and report-boundary foundations remain validated.",
        ),
        PetHostIntegrationCheck(
            "host_readiness_nonblocking",
            readiness.get("blocking") is False
            and readiness.get("output_blocking") is True
            and readiness.get("message") == PET_ISSUED_OUTPUT_BLOCK_REASON,
            "PET calculation/Results are nonblocking while issued output remains explicitly blocked.",
        ),
        PetHostIntegrationCheck(
            "legacy_generic_calculator_closed",
            source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON,
            "The legacy generic source-calculation route remains closed; PET uses its dedicated replay-verified dispatch.",
        ),
        PetHostIntegrationCheck(
            "issued_output_boundary_closed",
            PET_REPORT_INTEGRATION_OPEN is False and PET_ISSUED_OUTPUT_INTEGRATION_ENABLED is False,
            "Issued PET PDF/export/certification remains outside Step 27.",
        ),
    )
    ready = PET_HOST_INTEGRATION_ENABLED and all(check.passed for check in checks)
    return {
        "contract_version": PET_HOST_INTEGRATION_CONTRACT_VERSION,
        "baseline": PET_HOST_INTEGRATION_BASELINE,
        "host_integration_enabled": PET_HOST_INTEGRATION_ENABLED,
        "host_integration_ready": ready,
        "working_project_enabled": ready,
        "production_calculation_enabled": ready,
        "in_app_results_enabled": ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
    }


def require_pet_host_integration_ready() -> dict[str, Any]:
    assessment = assess_pet_host_integration_readiness()
    if assessment["host_integration_ready"] is not True:
        raise PetHostIntegrationError(
            "; ".join(assessment["blocking_reasons"]) or "PET host integration is not ready."
        )
    return assessment
