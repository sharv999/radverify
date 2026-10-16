"""Final PET release-gate / cleanup audit for Step 29.

Step 29 does not enable a new product surface. It verifies the controlled
production-host scope opened through Steps 26-28, records the cleanup of stale
historical wording, and proves that issued PDF, machine export, certification,
signatures, and the legacy generic source calculator remain closed.

The gate therefore has two simultaneous outcomes:

* controlled production-host release: GO;
* issued-output release: NO-GO.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PET_ISSUED_OUTPUT_BLOCK_REASON,
    PET_MODALITY,
    pet_source_readiness_result,
)
from modalities.registry import (
    coming_soon_modality_names,
    locked_source_mapping,
    production_modality_names,
    source_calculation_blocked_reason,
)
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
)
from services.export_eligibility import assess_export_eligibility
from services.pet_host_integration_gate import assess_pet_host_integration_readiness
from services.pet_pdf_integration_readiness_gate import assess_pet_pdf_integration_readiness
from services.pet_report_pdf_preview import (
    PET_PDF_PREVIEW_INTEGRATION_OPEN,
    PET_PDF_PREVIEW_ISSUEABLE,
    PET_PDF_PREVIEW_OUTPUT_ELIGIBLE,
)
from services.pet_results_model import PET_RESULTS_MODEL_CONTRACT_VERSION
from services.pet_results_presentation_contract import (
    PET_RESULTS_PRESENTATION_BASELINE,
    PET_RESULTS_PRESENTATION_CONTRACT_VERSION,
)

PET_RELEASE_GATE_CONTRACT_VERSION = 1
PET_RELEASE_GATE_BASELINE = "pet-release-gate-step29-v1-clean-controlled-host-results-only"
PET_CONTROLLED_HOST_RELEASE_SCOPE = (
    "working-project persistence + gated production calculation + in-app Results"
)
PET_ISSUED_OUTPUT_RELEASE_ENABLED = False
PET_RELEASE_CLEANUP_DEBT: tuple[str, ...] = ()


class PetReleaseGateError(RuntimeError):
    """Raised when the controlled PET release boundary is not satisfied."""


@dataclass(frozen=True)
class PetReleaseGateCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _output_gate_check() -> tuple[bool, str]:
    readiness = pet_source_readiness_result(
        "pet_patient",
        {},
        {"room_name": "PET release audit", "source_name": "PET Patient Source"},
    )
    preflight = {
        "overall_status": readiness["overall_status"],
        "blocking": readiness["blocking"],
        "errors": list(readiness["errors"]),
        "warnings": list(readiness["warnings"]),
        "room_results": [
            {
                "room_name": readiness["room_name"],
                "source_results": [readiness],
            }
        ],
    }
    eligibility = assess_export_eligibility(
        preflight=preflight,
        requested_report_status="Final",
    )
    passed = (
        eligibility.can_export_pdf is False
        and eligibility.can_export_csv is False
        and eligibility.can_certify is False
        and eligibility.allowed is False
    )
    return (
        passed,
        "PET output_blocking prevents issued PDF, machine export, and certification."
        if passed
        else "Issued-output eligibility is unexpectedly open for PET.",
    )


def assess_pet_release_gate() -> dict[str, Any]:
    """Return the final controlled-host PET release assessment without enabling output."""
    host = assess_pet_host_integration_readiness()
    pdf_gate = assess_pet_pdf_integration_readiness()
    output_closed, output_detail = _output_gate_check()

    root = Path(__file__).resolve().parents[1]
    app_text = (root / "app.py").read_text(encoding="utf-8")
    pet_text = (root / "modalities" / "pet.py").read_text(encoding="utf-8")
    historical_text = (
        root / "docs" / "architecture" / "PET_Production_Readiness_Boundary_Audit_Step_15.md"
    ).read_text(encoding="utf-8")

    checks = (
        PetReleaseGateCheck(
            "production_registry",
            "PET" in production_modality_names()
            and "PET" not in coming_soon_modality_names()
            and locked_source_mapping(production_only=True).get("PET")
            == [("pet_patient", "PET Patient Source")]
            and PET_MODALITY.production_enabled is True,
            "PET is admitted through the production registry with the locked pet_patient source.",
        ),
        PetReleaseGateCheck(
            "host_orchestration_registry_driven",
            "ROOM_TYPES = production_modality_names()" in app_text
            and "LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)" in app_text
            and 'if modality == "PET"' not in app_text
            and 'if room.modality == "PET"' not in app_text,
            "app.py remains registry-driven and contains no PET-specific room-admission branch.",
        ),
        PetReleaseGateCheck(
            "working_project_contract_frozen",
            PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3"
            and PET_WORKING_PROJECT_STATE_VERSION == 3
            and PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA == "radshield_pet_working_source_v2"
            and PET_WORKING_PROJECT_STATE_LEGACY_VERSION == 2,
            "Durable PET working-state schema v3 reflects the controlled production-host scope and retains v2 compatibility.",
        ),
        PetReleaseGateCheck(
            "production_host_ready",
            host.get("host_integration_ready") is True
            and host.get("production_calculation_enabled") is True
            and host.get("in_app_results_enabled") is True,
            "Step 26-27 approved physics/replay foundations and controlled production-host calculation/Results are ready.",
        ),
        PetReleaseGateCheck(
            "results_contract_frozen",
            PET_RESULTS_MODEL_CONTRACT_VERSION == 2
            and PET_RESULTS_PRESENTATION_CONTRACT_VERSION == 1
            and PET_RESULTS_PRESENTATION_BASELINE == "pet-normal-results-v1",
            "Canonical PET in-app Results model and presentation contracts remain frozen.",
        ),
        PetReleaseGateCheck(
            "legacy_generic_calculator_closed",
            source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON,
            "Legacy generic source calculation remains closed; production calculation uses the dedicated replay-verified dispatch path.",
        ),
        PetReleaseGateCheck(
            "issued_output_gate_closed",
            output_closed
            and pdf_gate.get("pdf_integration_switch_enabled") is False
            and pdf_gate.get("issued_pdf_enabled") is False
            and pdf_gate.get("machine_export_enabled") is False
            and pdf_gate.get("certification_enabled") is False,
            output_detail,
        ),
        PetReleaseGateCheck(
            "pdf_preview_nonissueable",
            PET_PDF_PREVIEW_INTEGRATION_OPEN is False
            and PET_PDF_PREVIEW_ISSUEABLE is False
            and PET_PDF_PREVIEW_OUTPUT_ELIGIBLE is False,
            "Step 28 PDF preview remains isolated, non-issueable, and output-ineligible.",
        ),
        PetReleaseGateCheck(
            "runtime_wording_current",
            "Controlled PET production-host assessment" in pet_text
            and "PET shielding calculations are not implemented in this build" not in pet_text
            and "production calculations are currently blocked" not in pet_text,
            "Runtime PET report wording matches the current controlled production-host state without opening issued output.",
        ),
        PetReleaseGateCheck(
            "historical_readiness_marked",
            historical_text.startswith("> **Historical snapshot:**")
            and "Steps 27-29" in historical_text,
            "The Step 15 NO-GO readiness audit is explicitly marked as a historical snapshot.",
        ),
    )

    controlled_host_ready = all(check.passed for check in checks)
    return {
        "contract_version": PET_RELEASE_GATE_CONTRACT_VERSION,
        "baseline": PET_RELEASE_GATE_BASELINE,
        "release_scope": PET_CONTROLLED_HOST_RELEASE_SCOPE,
        "controlled_host_release_ready": controlled_host_ready,
        "issued_output_release_enabled": PET_ISSUED_OUTPUT_RELEASE_ENABLED,
        "issued_output_release_ready": False,
        "working_project_enabled": controlled_host_ready,
        "production_calculation_enabled": controlled_host_ready,
        "in_app_results_enabled": controlled_host_ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "signatures_enabled": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
        "cleanup_debt": list(PET_RELEASE_CLEANUP_DEBT),
        "issued_output_block_reason": PET_ISSUED_OUTPUT_BLOCK_REASON,
    }


def require_pet_controlled_host_release_ready() -> dict[str, Any]:
    """Fail closed if the final PET controlled-host release boundary drifts."""
    assessment = assess_pet_release_gate()
    if assessment["controlled_host_release_ready"] is not True:
        raise PetReleaseGateError(
            "; ".join(assessment["blocking_reasons"])
            or "PET controlled production-host release gate is not ready."
        )
    return assessment
