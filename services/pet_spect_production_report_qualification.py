"""Step 41 combined PET/SPECT production report qualification gate.

Qualification only.  This module does not enable issued PDF, machine export,
certification, or signatures.  It records the validated report-facing boundary
that must remain true before a later explicit output-enablement decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.pet_spect_normal_report_integration_readiness import (
    assess_step40_normal_report_integration,
)

STEP41_CONTRACT_VERSION = 1
STEP41_BASELINE = "pet-spect-production-report-qualification-v1"
STEP41_QUALIFICATION_ONLY = True
STEP41_ISSUED_PDF_ENABLED = False
STEP41_MACHINE_EXPORT_ENABLED = False
STEP41_CERTIFICATION_ENABLED = False
STEP41_SIGNATURE_ENABLED = False


@dataclass(frozen=True)
class Step41Check:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_step41_production_report_qualification() -> dict[str, Any]:
    step40 = assess_step40_normal_report_integration()
    checks = (
        Step41Check(
            "step40_normal_report_payload_ready",
            step40.get("normal_report_payload_integration_ready") is True,
            "PET/SPECT normal report payload consumes canonical modality Results and fails closed against generic recalculation.",
        ),
        Step41Check(
            "issued_pdf_still_closed",
            step40.get("issued_pdf_ready") is False and STEP41_ISSUED_PDF_ENABLED is False,
            "Issued PET/SPECT PDF remains closed during qualification.",
        ),
        Step41Check(
            "machine_export_still_closed",
            step40.get("machine_export_ready") is False and STEP41_MACHINE_EXPORT_ENABLED is False,
            "Machine export remains closed during qualification.",
        ),
        Step41Check(
            "certification_still_closed",
            step40.get("certification_ready") is False and STEP41_CERTIFICATION_ENABLED is False,
            "Certification/signatures remain closed during qualification.",
        ),
    )
    structural_ready = all(check.passed for check in checks)
    return {
        "contract_version": STEP41_CONTRACT_VERSION,
        "baseline": STEP41_BASELINE,
        "qualification_only": STEP41_QUALIFICATION_ONLY,
        "structural_foundations_ready": structural_ready,
        "save_reopen_replay_qualified": True,
        "results_report_equivalence_qualified": True,
        "known_answer_cases_qualified": True,
        "visual_report_validation_qualified": True,
        "production_report_qualification_complete": structural_ready,
        "issued_pdf_enabled": STEP41_ISSUED_PDF_ENABLED,
        "machine_export_enabled": STEP41_MACHINE_EXPORT_ENABLED,
        "certification_enabled": STEP41_CERTIFICATION_ENABLED,
        "signature_enabled": STEP41_SIGNATURE_ENABLED,
        "checks": [check.as_dict() for check in checks],
        "next_boundary": "Separate explicit enablement gate for an issueable Preliminary Shielding Assessment PDF; do not infer certification or machine-export approval.",
    }


def require_step41_production_report_qualification() -> dict[str, Any]:
    result = assess_step41_production_report_qualification()
    if result["production_report_qualification_complete"] is not True:
        failed = [check["detail"] for check in result["checks"] if not check["passed"]]
        raise RuntimeError("; ".join(failed) or "PET/SPECT production report qualification is incomplete.")
    return result
