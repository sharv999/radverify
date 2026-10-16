"""SPECT Step 32 PDF integration readiness gate.

This module audits the frozen Step 28-31 report-preview chain and provides an
explicit fail-closed gate for any future SPECT PDF integration.  Step 32 does
not render PDFs or modify any issueable-output module, and leaves the
integration switch disabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from services.spect_report_readiness_contract import (
    SPECT_REPORT_INTEGRATION_OPEN,
    SPECT_REPORT_PERMITTED_RESULT_FIELDS,
    SPECT_REPORT_READINESS_BASELINE,
    SPECT_REPORT_READINESS_CONTRACT_VERSION,
)
from services.spect_report_payload_harness import (
    SPECT_REPORT_PAYLOAD_HARNESS_BASELINE,
    SPECT_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
)
from services.spect_source_summary_harness import (
    SPECT_SOURCE_SUMMARY_HARNESS_BASELINE,
    SPECT_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
)
from services.spect_report_section_view_model import (
    SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE,
    SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    SPECT_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN,
)
from services.spect_report_plain_text_preview import (
    SPECT_PLAIN_TEXT_PREVIEW_BASELINE,
    SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION,
    SPECT_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN,
)

SPECT_PDF_INTEGRATION_READINESS_CONTRACT_VERSION = 1
SPECT_PDF_INTEGRATION_READINESS_BASELINE = "spect-pdf-integration-readiness-v1-gate-closed"

# Step 32 deliberately leaves this off.  A later step may only change this
# after adding a non-issueable PDF adapter and its regression coverage.
SPECT_PDF_INTEGRATION_SWITCH_ENABLED = False

SPECT_PDF_GATE_BLOCK_REASON = (
    "SPECT PDF integration is not enabled. Step 32 validates the report-preview "
    "foundations only; issued PDF/output integration remains closed."
)


class SpectPdfIntegrationNotEnabledError(RuntimeError):
    """Raised when code attempts to cross the closed Step 32 PDF gate."""


@dataclass(frozen=True)
class SpectPdfReadinessCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
        }


def _foundational_checks() -> Tuple[SpectPdfReadinessCheck, ...]:
    return (
        SpectPdfReadinessCheck(
            "step28_report_contract_frozen",
            SPECT_REPORT_READINESS_CONTRACT_VERSION == 1
            and SPECT_REPORT_READINESS_BASELINE == "spect-report-readiness-v1-closed"
            and SPECT_REPORT_INTEGRATION_OPEN is False
            and len(SPECT_REPORT_PERMITTED_RESULT_FIELDS) == 30,
            "Step 28 frozen 30-field Results allowlist remains closed to report integration.",
        ),
        SpectPdfReadinessCheck(
            "step29_non_issueable_harness_frozen",
            SPECT_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION == 1
            and SPECT_REPORT_PAYLOAD_HARNESS_BASELINE == "spect-report-payload-harness-v1-non-issueable"
            and SPECT_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION == 1
            and SPECT_SOURCE_SUMMARY_HARNESS_BASELINE == "spect-source-summary-harness-v1-non-issueable",
            "Step 29 source-summary and barrier report-payload harnesses are frozen and non-issueable.",
        ),
        SpectPdfReadinessCheck(
            "step30_view_model_frozen",
            SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION == 1
            and SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE == "spect-report-section-view-model-v1-non-issueable"
            and SPECT_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN is False,
            "Step 30 deterministic report section/view-model remains non-issueable and disconnected.",
        ),
        SpectPdfReadinessCheck(
            "step31_plain_text_renderer_frozen",
            SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION == 1
            and SPECT_PLAIN_TEXT_PREVIEW_BASELINE == "spect-plain-text-report-preview-v1-non-issueable"
            and SPECT_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN is False,
            "Step 31 plain-text preview renderer remains pure, deterministic and non-issueable.",
        ),
    )


def assess_spect_pdf_integration_readiness() -> Dict[str, Any]:
    """Return the Step 32 readiness decision without opening PDF integration."""
    checks = _foundational_checks()
    foundations_ready = all(check.passed for check in checks)
    switch_enabled = SPECT_PDF_INTEGRATION_SWITCH_ENABLED is True
    integration_ready = foundations_ready and switch_enabled

    blockers = []
    if not foundations_ready:
        blockers.extend(check.detail for check in checks if not check.passed)
    if not switch_enabled:
        blockers.append(SPECT_PDF_GATE_BLOCK_REASON)

    return {
        "contract_version": SPECT_PDF_INTEGRATION_READINESS_CONTRACT_VERSION,
        "baseline": SPECT_PDF_INTEGRATION_READINESS_BASELINE,
        "validated_foundations": foundations_ready,
        "pdf_integration_switch_enabled": switch_enabled,
        "pdf_integration_ready": integration_ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "checks": [check.to_dict() for check in checks],
        "blocking_reasons": blockers,
    }


def require_spect_pdf_integration_enabled() -> Dict[str, Any]:
    """Fail closed until a later step explicitly opens the SPECT PDF gate."""
    assessment = assess_spect_pdf_integration_readiness()
    if not assessment["pdf_integration_ready"]:
        raise SpectPdfIntegrationNotEnabledError(
            "; ".join(assessment["blocking_reasons"]) or SPECT_PDF_GATE_BLOCK_REASON
        )
    return assessment
