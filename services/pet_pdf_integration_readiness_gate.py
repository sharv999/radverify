"""PET Step 28 PDF integration readiness gate.

This module audits the frozen PET report-preview chain and provides an explicit
fail-closed gate for any future PET PDF integration. Step 28 does not open
issued PDF, machine export, certification, signature, or normal output routing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.pet_host_integration_gate import assess_pet_host_integration_readiness
from services.pet_report_readiness_contract import (
    PET_REPORT_INTEGRATION_OPEN,
    PET_REPORT_PERMITTED_RESULT_FIELDS,
    PET_REPORT_READINESS_BASELINE,
    PET_REPORT_READINESS_CONTRACT_VERSION,
)
from services.pet_report_payload_harness import (
    PET_REPORT_PAYLOAD_HARNESS_BASELINE,
    PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
)
from services.pet_source_summary_harness import (
    PET_SOURCE_SUMMARY_HARNESS_BASELINE,
    PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
)
from services.pet_combined_report_payload_harness import (
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE,
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION,
)
from services.pet_report_section_view_model import (
    PET_REPORT_SECTION_VIEW_MODEL_BASELINE,
    PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    PET_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN,
)
from services.pet_report_plain_text_preview import (
    PET_PLAIN_TEXT_PREVIEW_BASELINE,
    PET_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION,
    PET_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN,
)

PET_PDF_INTEGRATION_READINESS_CONTRACT_VERSION = 1
PET_PDF_INTEGRATION_READINESS_BASELINE = "pet-pdf-integration-readiness-step28-v1-gate-closed"
PET_PDF_INTEGRATION_SWITCH_ENABLED = False
PET_PDF_GATE_BLOCK_REASON = (
    "PET PDF integration is not enabled. Step 28 validates the production-host and "
    "report-preview foundations only; issued PDF/output integration remains closed."
)


class PetPdfIntegrationNotEnabledError(RuntimeError):
    """Raised when code attempts to cross the closed PET PDF integration gate."""


@dataclass(frozen=True)
class PetPdfReadinessCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _foundational_checks() -> tuple[PetPdfReadinessCheck, ...]:
    host = assess_pet_host_integration_readiness()
    return (
        PetPdfReadinessCheck(
            "step27_production_host_ready",
            host.get("host_integration_ready") is True
            and host.get("issued_pdf_enabled") is False
            and host.get("machine_export_enabled") is False
            and host.get("certification_enabled") is False,
            "Step 27 production-host calculation/Results boundary is ready while issued outputs remain closed.",
        ),
        PetPdfReadinessCheck(
            "report_contract_frozen",
            PET_REPORT_READINESS_CONTRACT_VERSION == 1
            and PET_REPORT_READINESS_BASELINE == "pet-report-readiness-v1-closed"
            and PET_REPORT_INTEGRATION_OPEN is False
            and len(PET_REPORT_PERMITTED_RESULT_FIELDS) == 31,
            "Frozen 31-field PET Results allowlist remains closed to issueable report integration.",
        ),
        PetPdfReadinessCheck(
            "non_issueable_payload_chain_frozen",
            PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION == 1
            and PET_REPORT_PAYLOAD_HARNESS_BASELINE == "pet-report-payload-harness-v1-non-issueable"
            and PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION == 1
            and PET_SOURCE_SUMMARY_HARNESS_BASELINE == "pet-source-summary-harness-v1-non-issueable"
            and PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION == 1
            and PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE == "pet-combined-report-payload-envelope-v1-non-issueable",
            "PET source-summary, barrier payload, and combined-envelope harnesses remain frozen and non-issueable.",
        ),
        PetPdfReadinessCheck(
            "view_model_and_text_preview_frozen",
            PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION == 1
            and PET_REPORT_SECTION_VIEW_MODEL_BASELINE == "pet-report-section-view-model-v1-non-issueable"
            and PET_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN is False
            and PET_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION == 1
            and PET_PLAIN_TEXT_PREVIEW_BASELINE == "pet-plain-text-preview-v1-non-issueable"
            and PET_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN is False,
            "PET deterministic report view-model and plain-text preview remain isolated and non-issueable.",
        ),
    )


def assess_pet_pdf_integration_readiness() -> dict[str, Any]:
    """Return the Step 28 PDF readiness decision without opening integration."""
    checks = _foundational_checks()
    foundations_ready = all(check.passed for check in checks)
    switch_enabled = PET_PDF_INTEGRATION_SWITCH_ENABLED is True
    integration_ready = foundations_ready and switch_enabled
    blockers = [check.detail for check in checks if not check.passed]
    if not switch_enabled:
        blockers.append(PET_PDF_GATE_BLOCK_REASON)
    return {
        "contract_version": PET_PDF_INTEGRATION_READINESS_CONTRACT_VERSION,
        "baseline": PET_PDF_INTEGRATION_READINESS_BASELINE,
        "validated_foundations": foundations_ready,
        "pdf_integration_switch_enabled": switch_enabled,
        "pdf_integration_ready": integration_ready,
        "issued_pdf_enabled": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "checks": [check.to_dict() for check in checks],
        "blocking_reasons": blockers,
    }


def require_pet_pdf_integration_enabled() -> dict[str, Any]:
    """Fail closed until a later scoped change explicitly opens PET PDF integration."""
    assessment = assess_pet_pdf_integration_readiness()
    if assessment["pdf_integration_ready"] is not True:
        raise PetPdfIntegrationNotEnabledError(
            "; ".join(assessment["blocking_reasons"]) or PET_PDF_GATE_BLOCK_REASON
        )
    return assessment
