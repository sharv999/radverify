"""Formal PET architecture-completion gate for Step 29.

Step 29 does not widen the product surface. It records that PET has reached the
same formal controlled production-host footing as SPECT: durable working-state
persistence, gated production calculation, and in-app Results are complete;
issued PDF, machine export, certification, and signature routing remain outside
this completion scope and stay closed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from modalities.registry import production_modality_names
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
)
from services.pet_release_gate import (
    PET_CONTROLLED_HOST_RELEASE_SCOPE,
    PET_RELEASE_CLEANUP_DEBT,
    assess_pet_release_gate,
)

PET_ARCHITECTURE_COMPLETION_CONTRACT_VERSION = 1
PET_ARCHITECTURE_COMPLETION_BASELINE = "pet-architecture-complete-current-production-host-scope-v1"
PET_ARCHITECTURE_COMPLETION_STEP = 29
PET_ARCHITECTURE_COMPLETION_SCOPE = PET_CONTROLLED_HOST_RELEASE_SCOPE
PET_ARCHITECTURE_COMPLETE_CURRENT_SCOPE = True


class PetArchitectureCompletionError(RuntimeError):
    """Raised if the frozen PET current-scope architecture-completion boundary drifts."""


@dataclass(frozen=True)
class PetArchitectureCompletionCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_pet_architecture_completion() -> dict[str, Any]:
    """Return the Step 29 current-scope PET architecture-completion assessment."""
    release = assess_pet_release_gate()

    checks = (
        PetArchitectureCompletionCheck(
            "controlled_host_release_green",
            release["controlled_host_release_ready"] is True,
            "Step 29 controlled production-host release remains GO.",
        ),
        PetArchitectureCompletionCheck(
            "production_registry_stable",
            "PET" in production_modality_names(),
            "PET remains admitted through the production modality registry.",
        ),
        PetArchitectureCompletionCheck(
            "working_state_v3_frozen",
            PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3"
            and PET_WORKING_PROJECT_STATE_VERSION == 3,
            "Durable PET working-project state remains frozen at schema v3.",
        ),
        PetArchitectureCompletionCheck(
            "cleanup_debt_cleared",
            PET_RELEASE_CLEANUP_DEBT == ()
            and release.get("cleanup_debt") == [],
            "Historical wording/schema cleanup debt is cleared.",
        ),
        PetArchitectureCompletionCheck(
            "issued_output_scope_closed",
            release["issued_output_release_ready"] is False
            and release["issued_pdf_enabled"] is False
            and release["machine_export_enabled"] is False
            and release["certification_enabled"] is False
            and release["signatures_enabled"] is False,
            "Issued PDF, machine export, certification, and signatures remain outside the completed scope.",
        ),
    )

    architecture_complete = PET_ARCHITECTURE_COMPLETE_CURRENT_SCOPE and all(
        check.passed for check in checks
    )
    return {
        "contract_version": PET_ARCHITECTURE_COMPLETION_CONTRACT_VERSION,
        "baseline": PET_ARCHITECTURE_COMPLETION_BASELINE,
        "completion_step": PET_ARCHITECTURE_COMPLETION_STEP,
        "completion_scope": PET_ARCHITECTURE_COMPLETION_SCOPE,
        "architecture_complete_current_scope": architecture_complete,
        "issued_output_in_completion_scope": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
    }


def require_pet_architecture_complete_current_scope() -> dict[str, Any]:
    """Fail closed if the Step 29 PET architecture-completion boundary drifts."""
    result = assess_pet_architecture_completion()
    if result["architecture_complete_current_scope"] is not True:
        raise PetArchitectureCompletionError(
            "; ".join(result["blocking_reasons"])
            or "PET current production-host architecture is not complete."
        )
    return result
