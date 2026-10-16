"""Step 42 explicit PET/SPECT Preliminary Shielding Assessment PDF enablement.

This is the only authorization boundary that may turn a Step 40/41 PET/SPECT
report payload into an issueable *preliminary* PDF.  It does not enable machine
exports, certification, signatures, or final/certified report status.
"""
from __future__ import annotations

from typing import Any

from services.pet_spect_production_report_qualification import (
    require_step41_production_report_qualification,
)

STEP42_CONTRACT_VERSION = 1
STEP42_BASELINE = "pet-spect-preliminary-pdf-issuance-v1"
STEP42_PRELIMINARY_PDF_ENABLED = True
STEP42_MACHINE_EXPORT_ENABLED = False
STEP42_BARRIER_RESULTS_JSON_ENABLED = True
STEP42_CERTIFICATION_ENABLED = False
STEP42_SIGNATURE_ENABLED = False
STEP42_REPORT_STATUS = "Preliminary"
STEP42_REPORT_STATUS_EFFECTIVE = "Preliminary — Issueable"
STEP42_ALLOWED_MODALITIES = frozenset({"PET", "SPECT"})

_FINAL_STATUS_TOKENS = ("FINAL", "CERTIFIED", "ISSUED", "FOR ISSUE", "APPROVED")
_ALLOWED_LEGACY_SOURCE_ERROR_SUFFIXES = (
    "Room has no sources.",
    "Missing required source type(s): pet_patient.",
    "Missing required source type(s): spect_patient.",
)


class PetSpectPreliminaryPdfIssuanceError(ValueError):
    """Raised when a payload is not safe for Step 42 preliminary PDF issuance."""


def is_pet_spect_preliminary_pdf_candidate(app: Any, report_status: object = "Draft") -> bool:
    """Return True only for PET/SPECT-only projects requesting non-final output."""
    status = str(report_status or "Draft").strip().upper()
    if any(token in status for token in _FINAL_STATUS_TOKENS):
        return False
    rooms = list(getattr(getattr(app, "project", None), "rooms", ()) or ())
    modalities = {str(getattr(room, "modality", "") or "").strip().upper() for room in rooms}
    return bool(rooms) and bool(modalities) and modalities.issubset(STEP42_ALLOWED_MODALITIES)


def authorize_issueable_preliminary_pet_spect_pdf(payload: dict[str, Any]) -> dict[str, Any]:
    """Authorize one already-qualified PET/SPECT payload for preliminary PDF issue.

    The function mutates ``payload`` in place and also returns it.  It never
    authorizes machine export, certification, signatures, or a final-like status.
    """
    require_step41_production_report_qualification()
    _validate_payload_for_preliminary_issue(payload)

    modalities = _payload_modalities(payload)
    modality_label = "/".join(sorted(modalities))
    title = (
        f"Preliminary {next(iter(modalities))} Shielding Assessment"
        if len(modalities) == 1
        else "Preliminary PET/SPECT Shielding Assessment"
    )

    meta = payload.setdefault("meta", {})
    original_status = str(meta.get("report_status", "Draft") or "Draft")
    meta["report_status_requested"] = original_status
    meta["report_status"] = STEP42_REPORT_STATUS
    meta["report_status_effective"] = STEP42_REPORT_STATUS_EFFECTIVE
    meta["report_title"] = title

    report_wording = dict(meta.get("report_wording", {}) or {})
    report_wording.update(
        {
            "report_title": title,
            "report_subtitle": "Issueable preliminary shielding assessment — not a certificate of shielding compliance",
            "cover_introduction": (
                "This preliminary shielding assessment is issued for design and shielding review using the validated "
                "PET/SPECT production calculation and report-payload boundaries. It is not a certificate of shielding compliance."
            ),
            "limitations_heading": "Preliminary assessment limitations",
        }
    )
    bullets = [str(item) for item in list(report_wording.get("limitation_bullets", []) or [])]
    replacement = [
        "This document is an issueable preliminary shielding assessment, not a final shielding compliance certificate.",
        "Canonical barrier-results JSON is enabled for traceability; other machine-readable exports, certification and signature workflows remain disabled for PET/SPECT.",
        "Final shielding acceptance requires professional review of architectural drawings, construction details, source/workload assumptions, occupancy assumptions and installed materials.",
        "PET/CT and SPECT/CT CT shielding components must be assessed separately through the CT modality.",
    ]
    # Remove stale pre-Step-42 statements that say all issued PDF output is disabled.
    bullets = [
        item
        for item in bullets
        if "issued PDF" not in item and "issued output remains disabled" not in item.lower()
    ]
    for item in replacement:
        if item not in bullets:
            bullets.append(item)
    report_wording["limitation_bullets"] = bullets
    meta["report_wording"] = report_wording

    assessment_status = _preliminary_assessment_status(payload)
    contains_nonpassing = assessment_status in {"REVIEW", "FAIL"}
    preliminary_warnings = []
    if contains_nonpassing:
        preliminary_warnings.append(
            f"Preliminary assessment contains {assessment_status} barrier result(s); "
            "the report is issueable for design review but the affected shielding must be resolved before final acceptance."
        )

    payload["preliminary_pdf_issuance"] = {
        "contract_version": STEP42_CONTRACT_VERSION,
        "baseline": STEP42_BASELINE,
        "modalities": sorted(modalities),
        "modality_label": modality_label,
        "preliminary_pdf_enabled": True,
        "issueable": True,
        "assessment_status": assessment_status,
        "contains_nonpassing_barriers": contains_nonpassing,
        "machine_export_enabled": False,
        "barrier_results_json_enabled": True,
        "certification_enabled": False,
        "signature_enabled": False,
        "step41_qualification_required": True,
    }

    payload["export_eligibility"] = {
        "can_export_pdf": True,
        "can_export_csv": False,
        "can_certify": False,
        "requires_acknowledgement": False,
        "requested_report_status": original_status,
        "report_status_effective": STEP42_REPORT_STATUS_EFFECTIVE,
        "blocking_reasons": [],
        "warnings": preliminary_warnings,
        "allowed": False,
        "blocking": False,
    }

    payload["certification"] = {
        "label": "PRELIMINARY — NOT CERTIFICATION",
        "certificate_title": title,
        "assessment_status": assessment_status,
        "report_status_effective": STEP42_REPORT_STATUS_EFFECTIVE,
        "certification_allowed": False,
        "signature_allowed": False,
        "watermark": "PRELIMINARY",
        "statement_heading": "Preliminary assessment statement",
        "statement": _preliminary_assessment_statement(assessment_status),
        "validity_heading": "Preliminary assessment conditions",
        "validity_points": [
            "This preliminary assessment applies only to the documented geometry, workloads, occupancy factors, design goals and shielding construction inputs.",
            "Any material design, workload, occupancy or room-layout change requires reassessment.",
            "Canonical barrier-results JSON is enabled for traceability; other machine exports, certification and signatures remain outside the Step 42 enabled scope.",
        ],
        "blocking_issues": [],
        "warnings": preliminary_warnings,
        "mandatory_disclaimers": [
            "This document is an issueable preliminary shielding assessment and is not a certificate of shielding compliance."
        ],
        "disclaimers": [
            "This document is an issueable preliminary shielding assessment and is not a certificate of shielding compliance."
        ],
    }
    return payload



def _preliminary_assessment_status(payload: dict[str, Any]) -> str:
    """Return the worst reportable preliminary result without recalculation."""
    summary = payload.get("summary", {}) or {}
    if int(summary.get("fail_count", 0) or 0) > 0:
        return "FAIL"
    if int(summary.get("review_count", 0) or 0) > 0:
        return "REVIEW"

    room_statuses = {
        str(room.get("overall_status", "") or "").strip().upper()
        for room in list(payload.get("rooms", []) or [])
        if isinstance(room, dict)
    }
    if "FAIL" in room_statuses:
        return "FAIL"
    if "REVIEW" in room_statuses:
        return "REVIEW"
    return "PASS"


def _preliminary_assessment_statement(status: str) -> str:
    status = str(status or "PASS").strip().upper()
    if status == "FAIL":
        return (
            "One or more assessed barriers do not meet the adopted weekly design goals for the stated operating conditions. "
            "This preliminary assessment may be issued for design review so that the failed barrier(s) can be redesigned and "
            "reassessed. It is not a certificate of shielding compliance."
        )
    if status == "REVIEW":
        return (
            "One or more assessed barriers require review before the shielding design is frozen. This preliminary assessment "
            "may be issued for design coordination and resolution of those review items. It is not a certificate of shielding compliance."
        )
    return (
        "All assessed barriers in this preliminary assessment are classified as PASS against the adopted weekly design goals "
        "for the stated operating conditions. This document may be issued as a preliminary shielding assessment but is not a "
        "certificate of shielding compliance."
    )

def assess_step42_preliminary_pdf_enablement() -> dict[str, Any]:
    step41 = require_step41_production_report_qualification()
    return {
        "contract_version": STEP42_CONTRACT_VERSION,
        "baseline": STEP42_BASELINE,
        "step41_qualification_complete": step41.get("production_report_qualification_complete") is True,
        "preliminary_pdf_enabled": STEP42_PRELIMINARY_PDF_ENABLED,
        "machine_export_enabled": STEP42_MACHINE_EXPORT_ENABLED,
        "barrier_results_json_enabled": STEP42_BARRIER_RESULTS_JSON_ENABLED,
        "certification_enabled": STEP42_CERTIFICATION_ENABLED,
        "signature_enabled": STEP42_SIGNATURE_ENABLED,
        "final_or_certified_pdf_enabled": False,
        "production_output_state": "PRELIMINARY_PDF_ENABLED",
    }


def _validate_payload_for_preliminary_issue(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise PetSpectPreliminaryPdfIssuanceError("Step 42 requires a report payload mapping.")

    meta = payload.get("meta", {}) or {}
    requested = str(meta.get("report_status", "Draft") or "Draft").strip().upper()
    if any(token in requested for token in _FINAL_STATUS_TOKENS):
        raise PetSpectPreliminaryPdfIssuanceError(
            "Step 42 authorizes Preliminary PET/SPECT PDF only; Final/Certified/Issued status remains disabled."
        )

    rooms = list(payload.get("rooms", []) or [])
    if not rooms:
        raise PetSpectPreliminaryPdfIssuanceError("Step 42 requires at least one PET/SPECT room.")
    modalities = _payload_modalities(payload)
    if not modalities or not modalities.issubset(STEP42_ALLOWED_MODALITIES):
        raise PetSpectPreliminaryPdfIssuanceError("Step 42 is restricted to PET/SPECT-only report payloads.")

    for room in rooms:
        modality = str(room.get("modality", "") or "").strip().upper()
        route = room.get("pet_spect_report_route")
        if not isinstance(route, dict):
            raise PetSpectPreliminaryPdfIssuanceError(
                f"{modality or 'PET/SPECT'} room is missing the Step 40 canonical report route."
            )
        if str(room.get("error", "") or "").strip():
            raise PetSpectPreliminaryPdfIssuanceError(
                f"{modality} room report payload contains an unresolved error: {room.get('error')}"
            )
        # REVIEW and FAIL are valid preliminary-assessment outcomes.  They are
        # intentionally reportable so the client can see which barriers require
        # design review or redesign.  Only unresolved calculation/source errors
        # and integrity failures remain issuance blockers.

    integrity = payload.get("calculation_integrity", {}) or {}
    if bool(integrity.get("blocking", False)):
        raise PetSpectPreliminaryPdfIssuanceError("Calculation-integrity gate is blocking Preliminary PDF issuance.")

    readiness = payload.get("source_readiness", {}) or {}
    unexpected_errors = [
        str(item)
        for item in list(readiness.get("errors", []) or [])
        if not _is_allowed_legacy_source_inventory_error(str(item))
    ]
    if unexpected_errors:
        raise PetSpectPreliminaryPdfIssuanceError(
            "Source-readiness contains unresolved blocking issue(s): " + "; ".join(unexpected_errors)
        )


def _payload_modalities(payload: dict[str, Any]) -> set[str]:
    return {
        str(room.get("modality", "") or "").strip().upper()
        for room in list(payload.get("rooms", []) or [])
        if isinstance(room, dict) and str(room.get("modality", "") or "").strip()
    }


def _is_allowed_legacy_source_inventory_error(text: str) -> bool:
    stripped = str(text or "").strip()
    return any(stripped.endswith(suffix) for suffix in _ALLOWED_LEGACY_SOURCE_ERROR_SUFFIXES)
