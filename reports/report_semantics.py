from __future__ import annotations

"""Canonical report-domain interpretation shared by payload construction and renderers.

This module owns status normalization, barrier wording, and report-level conclusion
semantics.  Renderers should consume these values rather than independently
re-deriving compliance meaning from raw calculation fields.
"""

from typing import Any, Dict, Optional


def safe_float_or_none(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def stringify_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(stringify_value(v) for v in value)
    return str(value)


def normalise_status(status: str) -> str:
    """Collapse report/certification status labels to PASS/REVIEW/FAIL."""
    s = str(status or "").strip().upper()
    if any(
        token in s
        for token in (
            "FAIL",
            "ERROR",
            "NON-COMPLIANT",
            "INCOMPLETE",
            "NOT CERTIFIED",
            "NOT FOR CERTIFICATION",
        )
    ):
        return "FAIL"
    if any(token in s for token in ("REVIEW", "WARN", "WARNING", "DRAFT")):
        return "REVIEW"
    return "PASS"


def user_facing_status_from_live(live: Dict[str, Any]) -> str:
    """Return report/export-facing status, including the UI margin risk policy."""
    if not isinstance(live, dict):
        live = {}

    status = normalise_status(live.get("compliance_status", ""))
    margin = safe_float_or_none(live.get("margin_mm"))

    if status == "FAIL" or (margin is not None and margin < 0):
        return "FAIL"
    if status == "REVIEW" or (margin is not None and margin < 0.5):
        return "REVIEW"
    return status


def status_text(status: str) -> str:
    s = normalise_status(status)
    if s == "FAIL":
        return "FAIL (exceeds design goal)"
    if s == "REVIEW":
        return "REVIEW (check assumptions / margins)"
    return "PASS (meets design goal)"


def rollup_room_status(pass_count: int, review_count: int, fail_count: int) -> str:
    if fail_count > 0:
        return "FAIL"
    if review_count > 0:
        return "REVIEW"
    return "PASS"


def governing_requirement_text(barrier: Dict[str, Any]) -> str:
    material = str(barrier.get("material", "") or "").strip()
    req_pb = barrier.get("required_lead_mm")
    req_conc = barrier.get("required_concrete_mm")

    if material == "Pb" and req_pb is not None:
        return f"Pb {req_pb:.2f} mm"
    if material == "Concrete" and req_conc is not None:
        return f"Concrete {req_conc:.1f} mm"

    parts = []
    if req_pb is not None:
        parts.append(f"Pb {req_pb:.2f} mm")
    if req_conc is not None:
        parts.append(f"Concrete {req_conc:.1f} mm")
    return " / ".join(parts) if parts else "Requirement not determined — review shielding model inputs"


def first_exposed_transmitted_dose(live: Dict[str, Any]) -> Optional[float]:
    for key in (
        "transmitted_dose_uSv_per_week",
        "transmitted_weekly_dose_uSv",
        "shielded_weekly_dose_uSv",
        "shielded_dose_uSv_per_week",
    ):
        value = safe_float_or_none(live.get(key))
        if value is not None:
            return value
    return None


def compliance_statement(barrier: Dict[str, Any]) -> str:
    status = normalise_status(barrier.get("status", ""))
    if status == "FAIL":
        return (
            "This barrier is assessed as not complying with the adopted weekly design goal "
            "under the stated operating conditions. Additional shielding or revised design inputs are required."
        )
    if status == "REVIEW":
        return (
            "This barrier is likely to comply with the adopted weekly design goal; however, "
            "confirmation of the stated assumptions is recommended due to limited margin."
        )
    return (
        "This barrier is assessed as complying with the adopted weekly design goal "
        "for the stated operating conditions."
    )


def recommended_action(barrier: Dict[str, Any]) -> str:
    status = normalise_status(barrier.get("status", ""))
    material = barrier.get("material", "")

    if status == "FAIL":
        if material == "Pb" and barrier.get("required_lead_mm") is not None:
            return f"Increase lead shielding to at least {barrier['required_lead_mm']:.2f} mm and confirm installed thickness."
        if material == "Concrete" and barrier.get("required_concrete_mm") is not None:
            return f"Increase concrete shielding to at least {barrier['required_concrete_mm']:.1f} mm and confirm installed thickness."
        return "Increase shielding or revise source / occupancy assumptions."
    if status == "REVIEW":
        return "Confirm source workload, occupancy classification and installed barrier thickness."
    return "No action required."


def action_priority(status: str) -> str:
    s = normalise_status(status)
    if s == "FAIL":
        return "Critical"
    if s == "REVIEW":
        return "Moderate"
    return "Minor"


def fmt_float(value: Optional[float], decimals: int) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def provided_mm_display(barrier: Dict[str, Any]) -> str:
    thickness = barrier.get("provided_thickness_mm")
    material = barrier.get("material")
    if thickness is None:
        return ""
    if material == "Pb":
        return f"{thickness:.2f}"
    return f"{thickness:.1f}"


def provided_statement(barrier: Dict[str, Any]) -> str:
    material = barrier.get("material") or "Material"
    thickness = barrier.get("provided_thickness_mm")
    if thickness is None:
        return f"{material} not stated"
    if material == "Pb":
        return f"{material} {thickness:.2f} mm"
    return f"{material} {thickness:.1f} mm"


def required_statement(barrier: Dict[str, Any]) -> str:
    material = barrier.get("material")
    if material == "Pb" and barrier.get("required_lead_mm") is not None:
        return f"Pb {barrier['required_lead_mm']:.2f} mm"
    if material == "Concrete" and barrier.get("required_concrete_mm") is not None:
        return f"Concrete {barrier['required_concrete_mm']:.1f} mm"

    parts = []
    if barrier.get("required_lead_mm") is not None:
        parts.append(f"Pb {barrier['required_lead_mm']:.2f} mm")
    if barrier.get("required_concrete_mm") is not None:
        parts.append(f"Concrete {barrier['required_concrete_mm']:.1f} mm")
    return " / ".join(parts) if parts else "Not available"


def executive_conclusion_text(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {}) or {}
    cert = payload.get("certification", {}) or {}
    export_gate = payload.get("export_eligibility", {}) or {}
    integrity = payload.get("calculation_integrity", {}) or {}

    blocking_issues = list(cert.get("blocking_issues", []) or export_gate.get("blocking_reasons", []) or [])
    if blocking_issues or bool(integrity.get("blocking", False)):
        issue_count = len(blocking_issues) if blocking_issues else len(integrity.get("blocking_reasons", []) or [])
        return (
            "The assessment is incomplete and not suitable for final certification because "
            f"{issue_count or 1} blocking report-gate issue(s) remain. Resolve the listed source, export, "
            "or calculation-integrity issue(s), then regenerate the assessment before relying on the "
            "reported barrier outcomes."
        )

    if summary.get("fail_count", 0) > 0:
        return (
            f"The current assessment identifies {summary['fail_count']} barrier(s) that do not satisfy "
            "the adopted weekly design goal. Shielding upgrades or revision of design assumptions are required "
            "before those barriers can be regarded as compliant."
        )
    if summary.get("review_count", 0) > 0:
        return (
            f"No barrier has been assessed as FAIL; however, {summary['review_count']} barrier(s) are classified "
            "as REVIEW and should be confirmed against the stated source, occupancy and construction assumptions."
        )

    if not bool(cert.get("certification_allowed", False)):
        label = str(cert.get("label", "DRAFT — NOT FINAL CERTIFICATION") or "DRAFT — NOT FINAL CERTIFICATION")
        return (
            "All assessed barriers are classified as PASS against the adopted weekly design goals for the stated "
            f"room use and source assumptions. However, the report status is {label}; it should not be treated "
            "as a final certificate until reviewed and intentionally issued as Final."
        )

    return (
        "All assessed barriers are classified as PASS against the adopted weekly design goals for the stated room use and source assumptions."
    )


def overall_assessment_status(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {}) or {}
    cert = payload.get("certification", {}) or {}
    overall = str(cert.get("assessment_status", "") or "").strip().upper() or "PASS"
    if overall in {"INCOMPLETE", "ERROR"}:
        return "FAIL"
    if summary.get("source_ksec_incomplete_count", 0) > 0 or summary.get("fail_count", 0) > 0:
        return "FAIL"
    if summary.get("review_count", 0) > 0 or summary.get("source_ksec_manual_override_count", 0) > 0:
        return "REVIEW"
    return normalise_status(overall)


def compliance_risk(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {}) or {}
    if summary.get("fail_count", 0) > 0:
        return "High"
    if summary.get("review_count", 0) > 0:
        return "Moderate"
    return "Low"


def attach_report_presentation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach canonical display wording used by all output renderers."""
    for room in payload.get("rooms", []) or []:
        for barrier in room.get("barriers", []) or []:
            barrier["provided_mm_display"] = provided_mm_display(barrier)
            barrier["provided_statement"] = provided_statement(barrier)
            barrier["required_statement"] = required_statement(barrier)

    payload["presentation"] = {
        "overall_assessment_status": overall_assessment_status(payload),
        "compliance_risk": compliance_risk(payload),
        "executive_conclusion_text": executive_conclusion_text(payload),
    }
    return payload


def report_presentation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return canonical presentation data, attaching it for legacy payloads if absent."""
    presentation = payload.get("presentation")
    if isinstance(presentation, dict) and presentation.get("executive_conclusion_text"):
        return presentation
    attach_report_presentation(payload)
    return payload["presentation"]
