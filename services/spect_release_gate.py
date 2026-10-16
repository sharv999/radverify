"""Final SPECT release-gate / cleanup audit for Step 35.

Step 35 does not enable a new product surface.  It verifies the controlled
production-host scope opened through Steps 20-34 and proves that issued PDF,
machine export, certification, and the legacy generic source calculator remain
closed.

The gate therefore has two simultaneous outcomes:

* controlled production-host release: GO;
* issued-output release: NO-GO.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
    SPECT_LOW_TRANSMISSION_POLICY_STATUS,
    SPECT_LOW_TRANSMISSION_POLICY_VERSION,
    SPECT_LOW_TRANSMISSION_THRESHOLD,
)
from engine.spect_production_dispatch_gate import assess_spect_production_dispatch_readiness
from modalities.registry import (
    coming_soon_modality_names,
    locked_source_mapping,
    production_modality_names,
    source_calculation_blocked_reason,
)
from modalities.spect import (
    SPECT_CALCULATION_BLOCK_REASON,
    spect_source_readiness_result,
)
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_VERSION,
)
from services.export_eligibility import assess_export_eligibility
from services.spect_host_integration_gate import assess_spect_host_integration_readiness
from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness
from services.spect_report_pdf_preview import (
    SPECT_PDF_PREVIEW_INTEGRATION_OPEN,
    SPECT_PDF_PREVIEW_ISSUEABLE,
    SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE,
)
from services.spect_results_model import (
    SPECT_RESULTS_MODEL_CONTRACT_VERSION,
    SPECT_RESULTS_PAYLOAD_SCHEMA,
    SPECT_RESULTS_PAYLOAD_VERSION,
)

SPECT_RELEASE_GATE_CONTRACT_VERSION = 2
SPECT_RELEASE_GATE_BASELINE = "spect-release-gate-v2-clean-controlled-host-results-only"
SPECT_CONTROLLED_HOST_RELEASE_SCOPE = (
    "working-project persistence + gated production calculation + in-app Results"
)
SPECT_ISSUED_OUTPUT_RELEASE_ENABLED = False

# Step 36 clears the historical wording/schema debt recorded by Step 35.
SPECT_RELEASE_CLEANUP_DEBT: tuple[str, ...] = ()


class SpectReleaseGateError(RuntimeError):
    """Raised when the controlled Step 35 SPECT release boundary is not satisfied."""


@dataclass(frozen=True)
class SpectReleaseGateCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _output_gate_check() -> tuple[bool, str]:
    readiness = spect_source_readiness_result(
        "spect_patient",
        {},
        {"room_name": "SPECT release audit", "source_name": "SPECT Patient Source"},
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
        "Step 22/34 output_blocking prevents issued PDF, machine export, and certification."
        if passed
        else "Issued-output eligibility is unexpectedly open for SPECT.",
    )


def assess_spect_release_gate() -> dict[str, Any]:
    """Return the final controlled-host release assessment without enabling output."""
    host = assess_spect_host_integration_readiness()
    dispatch = assess_spect_production_dispatch_readiness()
    pdf_gate = assess_spect_pdf_integration_readiness()
    output_closed, output_detail = _output_gate_check()

    root = Path(__file__).resolve().parents[1]
    app_text = (root / "app.py").read_text(encoding="utf-8")

    checks = (
        SpectReleaseGateCheck(
            "production_registry",
            "SPECT" in production_modality_names()
            and "SPECT" not in coming_soon_modality_names()
            and locked_source_mapping(production_only=True).get("SPECT")
            == [("spect_patient", "SPECT Patient Source")],
            "SPECT is admitted through the production registry with the locked spect_patient source.",
        ),
        SpectReleaseGateCheck(
            "host_orchestration_registry_driven",
            "ROOM_TYPES = production_modality_names()" in app_text
            and "LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)" in app_text
            and 'if modality == "SPECT"' not in app_text
            and 'if room.modality == "SPECT"' not in app_text,
            "app.py remains registry-driven and contains no SPECT-specific room-admission branch.",
        ),
        SpectReleaseGateCheck(
            "working_project_contract_frozen",
            SPECT_WORKING_PROJECT_STATE_SCHEMA == "radshield_spect_working_source_v2"
            and SPECT_WORKING_PROJECT_STATE_VERSION == 2,
            "Step 36 durable SPECT working-state schema v2 reflects the controlled production-host scope.",
        ),
        SpectReleaseGateCheck(
            "production_dispatch_ready",
            dispatch.production_ready is True and dispatch.dispatch_enabled is True,
            "Step 20-26 frozen physics, replay, policy, and production dispatch gate are ready.",
        ),
        SpectReleaseGateCheck(
            "results_contract_frozen",
            SPECT_RESULTS_MODEL_CONTRACT_VERSION == 1
            and SPECT_RESULTS_PAYLOAD_SCHEMA == "radshield_spect_production_results_payload_v1"
            and SPECT_RESULTS_PAYLOAD_VERSION == 1
            and host.get("in_app_results_enabled") is True,
            "Step 27 production Results payload is frozen and enabled only for in-app Results.",
        ),
        SpectReleaseGateCheck(
            "low_transmission_policy_approved",
            SPECT_LOW_TRANSMISSION_POLICY_APPROVED is True
            and SPECT_LOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
            and SPECT_LOW_TRANSMISSION_POLICY_VERSION == 1
            and SPECT_LOW_TRANSMISSION_THRESHOLD == 0.01,
            "Step 25 <=1% low-transmission policy is approved, locked, and fail-closed.",
        ),
        SpectReleaseGateCheck(
            "legacy_generic_calculator_closed",
            source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON,
            "Legacy generic source calculation remains closed; production calculation uses Step 26 only.",
        ),
        SpectReleaseGateCheck(
            "issued_output_gate_closed",
            output_closed
            and pdf_gate.get("pdf_integration_switch_enabled") is False
            and pdf_gate.get("issued_pdf_enabled") is False,
            output_detail,
        ),
        SpectReleaseGateCheck(
            "pdf_preview_nonissueable",
            SPECT_PDF_PREVIEW_INTEGRATION_OPEN is False
            and SPECT_PDF_PREVIEW_ISSUEABLE is False
            and SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE is False,
            "Step 33 PDF preview remains isolated, non-issueable, and output-ineligible.",
        ),
    )

    controlled_host_ready = all(check.passed for check in checks)
    issued_output_ready = False
    return {
        "contract_version": SPECT_RELEASE_GATE_CONTRACT_VERSION,
        "baseline": SPECT_RELEASE_GATE_BASELINE,
        "release_scope": SPECT_CONTROLLED_HOST_RELEASE_SCOPE,
        "controlled_host_release_ready": controlled_host_ready,
        "issued_output_release_enabled": SPECT_ISSUED_OUTPUT_RELEASE_ENABLED,
        "issued_output_release_ready": issued_output_ready,
        "working_project_enabled": controlled_host_ready,
        "production_calculation_enabled": controlled_host_ready,
        "in_app_results_enabled": controlled_host_ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
        "cleanup_debt": list(SPECT_RELEASE_CLEANUP_DEBT),
    }


def require_spect_controlled_host_release_ready() -> dict[str, Any]:
    """Fail closed if the controlled Step 35 host release boundary drifts."""
    assessment = assess_spect_release_gate()
    if assessment["controlled_host_release_ready"] is not True:
        raise SpectReleaseGateError(
            "; ".join(assessment["blocking_reasons"])
            or "SPECT controlled production-host release gate is not ready."
        )
    return assessment
