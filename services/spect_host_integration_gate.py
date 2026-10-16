"""Step 34 controlled SPECT production-host integration gate.

This gate proves that SPECT may participate in the normal desktop host for room
selection, working-project persistence, gated production calculation, and in-app
Results while issued PDF/export/certification remain closed behind their own
boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from engine.spect_production_dispatch_gate import assess_spect_production_dispatch_readiness
from modalities.registry import production_modality_names, coming_soon_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, spect_source_readiness_result
from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness
from services.spect_report_pdf_preview import (
    SPECT_PDF_PREVIEW_INTEGRATION_OPEN,
    SPECT_PDF_PREVIEW_ISSUEABLE,
    SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE,
)

SPECT_HOST_INTEGRATION_CONTRACT_VERSION = 1
SPECT_HOST_INTEGRATION_BASELINE = "spect-production-host-integration-v1-controlled"
SPECT_HOST_INTEGRATION_ENABLED = True
SPECT_ISSUED_OUTPUT_INTEGRATION_ENABLED = False


class SpectHostIntegrationError(RuntimeError):
    """Raised when the Step 34 controlled host boundary is not satisfied."""


@dataclass(frozen=True)
class SpectHostIntegrationCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_spect_host_integration_readiness() -> dict[str, Any]:
    production_dispatch = assess_spect_production_dispatch_readiness()
    pdf_gate = assess_spect_pdf_integration_readiness()
    readiness = spect_source_readiness_result(
        "spect_patient",
        {},
        {"room_name": "SPECT host audit", "source_name": "SPECT Patient Source"},
    )

    checks = (
        SpectHostIntegrationCheck(
            "registry_host_enabled",
            "SPECT" in production_modality_names() and "SPECT" not in coming_soon_modality_names(),
            "SPECT is selectable through the registry-driven production host room path.",
        ),
        SpectHostIntegrationCheck(
            "production_dispatch_ready",
            production_dispatch.production_ready is True and production_dispatch.dispatch_enabled is True,
            "Step 24-26 production calculation dispatch is enabled and readiness-validated.",
        ),
        SpectHostIntegrationCheck(
            "host_readiness_nonblocking",
            readiness.get("blocking") is False and readiness.get("output_blocking") is True,
            "SPECT host calculation/Results are nonblocking while issued output remains explicitly blocked.",
        ),
        SpectHostIntegrationCheck(
            "legacy_generic_calculator_closed",
            source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON,
            "The legacy generic source-calculation route remains closed; Step 26 is the only production dispatch path.",
        ),
        SpectHostIntegrationCheck(
            "issued_pdf_gate_closed",
            pdf_gate.get("validated_foundations") is True
            and pdf_gate.get("pdf_integration_switch_enabled") is False
            and pdf_gate.get("issued_pdf_enabled") is False,
            "Step 32 PDF foundations are validated but issued PDF integration remains disabled.",
        ),
        SpectHostIntegrationCheck(
            "step33_preview_nonissueable",
            SPECT_PDF_PREVIEW_INTEGRATION_OPEN is False
            and SPECT_PDF_PREVIEW_ISSUEABLE is False
            and SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE is False,
            "Step 33 PDF preview remains isolated, non-issueable, and output-ineligible.",
        ),
    )
    host_ready = SPECT_HOST_INTEGRATION_ENABLED and all(check.passed for check in checks)
    return {
        "contract_version": SPECT_HOST_INTEGRATION_CONTRACT_VERSION,
        "baseline": SPECT_HOST_INTEGRATION_BASELINE,
        "host_integration_enabled": SPECT_HOST_INTEGRATION_ENABLED,
        "host_integration_ready": host_ready,
        "working_project_enabled": host_ready,
        "production_calculation_enabled": host_ready,
        "in_app_results_enabled": host_ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": [check.detail for check in checks if not check.passed],
    }


def require_spect_host_integration_ready() -> dict[str, Any]:
    assessment = assess_spect_host_integration_readiness()
    if assessment["host_integration_ready"] is not True:
        raise SpectHostIntegrationError(
            "; ".join(assessment["blocking_reasons"]) or "SPECT host integration is not ready."
        )
    return assessment
