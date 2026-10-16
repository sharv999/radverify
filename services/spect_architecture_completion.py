"""Formal SPECT architecture-completion gate for Step 37.

Step 37 does not widen the product surface. It records that the current
controlled production-host scope is architecturally complete after the
Step 35 release gate and Step 36 cleanup.

Issued PDF, machine export, certification, and signature routing remain outside
this completion scope and stay closed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from modalities.registry import production_modality_names
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_VERSION,
)
from services.spect_release_gate import (
    SPECT_CONTROLLED_HOST_RELEASE_SCOPE,
    SPECT_RELEASE_CLEANUP_DEBT,
    assess_spect_release_gate,
)

SPECT_ARCHITECTURE_COMPLETION_CONTRACT_VERSION = 1
SPECT_ARCHITECTURE_COMPLETION_BASELINE = (
    "spect-architecture-complete-current-production-host-scope-v1"
)
SPECT_ARCHITECTURE_COMPLETION_STEP = 37
SPECT_ARCHITECTURE_COMPLETION_SCOPE = SPECT_CONTROLLED_HOST_RELEASE_SCOPE
SPECT_ARCHITECTURE_COMPLETE_CURRENT_SCOPE = True


class SpectArchitectureCompletionError(RuntimeError):
    """Raised if the frozen current-scope architecture-completion boundary drifts."""


@dataclass(frozen=True)
class SpectArchitectureCompletionCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_spect_architecture_completion() -> dict[str, Any]:
    """Return the Step 37 current-scope architecture-completion assessment."""
    release = assess_spect_release_gate()

    checks = (
        SpectArchitectureCompletionCheck(
            "controlled_host_release_green",
            release["controlled_host_release_ready"] is True,
            "Step 35/36 controlled production-host release remains GO.",
        ),
        SpectArchitectureCompletionCheck(
            "production_registry_stable",
            "SPECT" in production_modality_names(),
            "SPECT remains admitted through the production modality registry.",
        ),
        SpectArchitectureCompletionCheck(
            "working_state_v2_frozen",
            SPECT_WORKING_PROJECT_STATE_SCHEMA == "radshield_spect_working_source_v2"
            and SPECT_WORKING_PROJECT_STATE_VERSION == 2,
            "Durable SPECT working-project state remains frozen at schema v2.",
        ),
        SpectArchitectureCompletionCheck(
            "cleanup_debt_cleared",
            SPECT_RELEASE_CLEANUP_DEBT == ()
            and release.get("cleanup_debt") == [],
            "Step 36 historical wording/schema cleanup debt remains cleared.",
        ),
        SpectArchitectureCompletionCheck(
            "issued_output_scope_closed",
            release["issued_output_release_ready"] is False
            and release["issued_pdf_enabled"] is False
            and release["machine_export_enabled"] is False
            and release["certification_enabled"] is False,
            "Issued PDF, machine export, and certification remain outside the completed scope.",
        ),
    )

    architecture_complete = (
        SPECT_ARCHITECTURE_COMPLETE_CURRENT_SCOPE
        and all(check.passed for check in checks)
    )
    return {
        "contract_version": SPECT_ARCHITECTURE_COMPLETION_CONTRACT_VERSION,
        "baseline": SPECT_ARCHITECTURE_COMPLETION_BASELINE,
        "completion_step": SPECT_ARCHITECTURE_COMPLETION_STEP,
        "completion_scope": SPECT_ARCHITECTURE_COMPLETION_SCOPE,
        "architecture_complete_current_scope": architecture_complete,
        "issued_output_in_completion_scope": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
    }


def require_spect_architecture_complete_current_scope() -> dict[str, Any]:
    """Fail closed if the Step 37 architecture-completion boundary drifts."""
    result = assess_spect_architecture_completion()
    if result["architecture_complete_current_scope"] is not True:
        raise SpectArchitectureCompletionError(
            "; ".join(result["blocking_reasons"])
            or "SPECT current production-host architecture is not complete."
        )
    return result
