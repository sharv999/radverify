from __future__ import annotations

"""
Central report wording/certification guard.

MVP risk protected:
    Prevent a generated PDF/report payload from using final certificate or
    clean PASS wording when export eligibility, source readiness, calculation
    integrity, manual CT ksec assumptions, or report status require draft/review
    wording.

This module is intentionally payload-shaped and UI-free. It does not recalculate
physics; it only converts already-built payload gate state into controlled report
wording.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List


FINAL_STATUS_TOKENS = {"FINAL", "CERTIFIED", "ISSUED", "FOR ISSUE", "APPROVED"}


@dataclass(frozen=True)
class ReportWordingState:
    label: str
    certificate_title: str
    assessment_status: str
    report_status_effective: str
    certification_allowed: bool
    signature_allowed: bool
    watermark: str
    statement_heading: str
    statement: str
    validity_heading: str
    validity_points: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mandatory_disclaimers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)

        # Backwards-compatible alias used by the existing certification code/tests.
        data["disclaimers"] = list(self.mandatory_disclaimers)
        return data


def build_report_wording_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the final report/certificate wording state from already-computed gates.

    Dominance order:
      1. export/source/calculation blockers -> INCOMPLETE, not certifiable;
      2. FAIL barrier results -> FAIL, not certifiable;
      3. REVIEW/manual override/warnings -> REVIEW, not certifiable;
      4. clean Draft -> DRAFT, not certifiable;
      5. clean Final -> CERTIFIED PASS.
    """
    payload = payload or {}
    summary = payload.get("summary", {}) or {}
    meta = payload.get("meta", {}) or {}
    source_readiness = payload.get("source_readiness", {}) or {}
    export_eligibility = payload.get("export_eligibility", {}) or {}
    calculation_integrity = payload.get("calculation_integrity", {}) or {}

    requested_status = _first_nonempty(
        export_eligibility.get("requested_report_status"),
        meta.get("report_status_requested"),
        meta.get("report_status"),
        "Draft",
    )
    requested_is_final = _is_final_like_status(requested_status)

    blocking_issues = _collect_blocking_issues(
        source_readiness=source_readiness,
        export_eligibility=export_eligibility,
        calculation_integrity=calculation_integrity,
    )
    warnings = _collect_warnings(
        source_readiness=source_readiness,
        export_eligibility=export_eligibility,
        calculation_integrity=calculation_integrity,
    )

    source_blocking = bool(source_readiness.get("blocking", False))
    export_blocks_certification = (
        "can_certify" in export_eligibility
        and not bool(export_eligibility.get("can_certify", False))
        and bool(export_eligibility.get("blocking", False))
    )
    calculation_incomplete = (
        isinstance(calculation_integrity, dict)
        and (
            bool(calculation_integrity.get("blocking", False))
            or calculation_integrity.get("calculation_complete") is False
        )
    )

    incomplete_ksec = _int(summary.get("source_ksec_incomplete_count")) > 0
    fail_count = _int(summary.get("fail_count"))
    review_count = _int(summary.get("review_count"))
    manual_count = _int(summary.get("source_ksec_manual_override_count"))

    if blocking_issues or source_blocking or export_blocks_certification or calculation_incomplete or incomplete_ksec:
        return _incomplete_state(
            requested_status=requested_status,
            blocking_issues=blocking_issues or ["BLOCKED: report contains unresolved critical issue(s)."],
            warnings=warnings,
            calculation_incomplete=calculation_incomplete,
            incomplete_ksec=incomplete_ksec,
        ).to_dict()

    if fail_count > 0:
        return _fail_state(
            requested_status=requested_status,
            fail_count=fail_count,
            warnings=warnings,
        ).to_dict()

    if review_count > 0 or manual_count > 0 or warnings:
        return _review_state(
            requested_status=requested_status,
            review_count=review_count,
            manual_count=manual_count,
            warnings=warnings,
        ).to_dict()

    if not requested_is_final:
        return _draft_pass_state(
            requested_status=requested_status,
            warnings=warnings,
        ).to_dict()

    return _certified_pass_state(requested_status=requested_status).to_dict()


def _incomplete_state(
    *,
    requested_status: str,
    blocking_issues: List[str],
    warnings: List[str],
    calculation_incomplete: bool,
    incomplete_ksec: bool,
) -> ReportWordingState:
    validity_points = [
        "Resolve all blocking source-readiness, export-gate and calculation-integrity issues.",
        "Regenerate the shielding calculations, payload, outputs and report after corrections are made.",
        "Do not use this draft report for final shielding certification or regulatory submission as a certificate.",
    ]

    disclaimers = [
        "This output is not a final certificate of shielding compliance.",
        "It must remain draft/review-only until all listed blocking issues are resolved and the report is intentionally issued as Final.",
    ]

    if incomplete_ksec:
        validity_points.insert(0, "Resolve missing CT scanner ksec values or enter a documented manual override.")
        disclaimers.append("One or more CT source inputs are incomplete due to missing/null ksec.")

    if calculation_incomplete:
        validity_points.insert(0, "Resolve payload calculation-integrity issue(s), including any room calculation failure, wall/result mismatch or missing opening rows.")
        disclaimers.append("One or more report payload calculation-integrity checks failed.")

    return ReportWordingState(
        label="INCOMPLETE — NOT FOR CERTIFICATION",
        certificate_title="Shielding Assessment — Not Certified",
        assessment_status="INCOMPLETE",
        report_status_effective="Draft — Incomplete Source Data",
        certification_allowed=False,
        signature_allowed=False,
        watermark="DRAFT — NOT FOR CERTIFICATION",
        statement_heading="Assessment incomplete",
        statement=(
            "This report contains unresolved source-data, export-gate or calculation-integrity issue(s). "
            "It must not be issued as a final shielding compliance certificate until all blocking issues "
            "are resolved and the assessment is regenerated."
        ),
        validity_heading="Conditions before certification",
        validity_points=validity_points,
        blocking_issues=blocking_issues,
        warnings=warnings,
        mandatory_disclaimers=disclaimers,
    )


def _fail_state(*, requested_status: str, fail_count: int, warnings: List[str]) -> ReportWordingState:
    return ReportWordingState(
        label="FAIL — NOT FOR CERTIFICATION",
        certificate_title="Shielding Assessment — Not Certified",
        assessment_status="FAIL",
        report_status_effective="Draft — Design action required / Not for certification",
        certification_allowed=False,
        signature_allowed=False,
        watermark="NOT CERTIFIED",
        statement_heading="Non-compliance statement",
        statement=(
            f"The assessment identifies {fail_count} barrier(s) that do not comply with the adopted "
            "weekly design goals under the stated operating conditions. The design must not be regarded "
            "as compliant until the identified barrier deficiencies are resolved and the assessment is regenerated."
        ),
        validity_heading="Required action before certification",
        validity_points=[
            "Resolve all FAIL barrier results or revise the design assumptions.",
            "Regenerate the assessment after design changes are made.",
            "Certification is not permitted while any barrier remains classified as FAIL.",
        ],
        warnings=warnings,
        mandatory_disclaimers=[
            "This output is not a final certificate of shielding compliance because one or more barriers are classified as FAIL."
        ],
    )


def _review_state(
    *,
    requested_status: str,
    review_count: int,
    manual_count: int,
    warnings: List[str],
) -> ReportWordingState:
    validity_points = [
        "Review all REVIEW-classified barriers and confirm whether they are acceptable.",
        "Confirm all source assumptions, workloads and shielding construction details before final issue.",
        "Do not label the report as final certified until review items are closed or formally accepted.",
    ]

    disclaimers = [
        "This report should remain draft/review-required until listed review items are resolved or formally accepted."
    ]

    if manual_count > 0:
        validity_points.insert(1, "Review any manual CT ksec override and confirm its reason, source/reference and approval basis.")
        disclaimers.append("Manual CT ksec override use requires explicit review and traceable documentation.")

    return ReportWordingState(
        label="REVIEW — NOT FINAL CERTIFICATION",
        certificate_title="Draft Shielding Assessment — Review Required",
        assessment_status="REVIEW",
        report_status_effective="Draft — Review required / Not final certification",
        certification_allowed=False,
        signature_allowed=False,
        watermark="DRAFT — REVIEW REQUIRED",
        statement_heading="Review-required assessment statement",
        statement=(
            "No barrier is currently classified as FAIL; however, review items remain. These may include REVIEW "
            "barriers, manual CT ksec override use, source-readiness warnings or assumptions requiring confirmation. "
            "This report should remain draft/review-required until those items are resolved or formally accepted."
        ),
        validity_heading="Items requiring review before final certification",
        validity_points=validity_points,
        warnings=warnings,
        mandatory_disclaimers=disclaimers,
    )


def _draft_pass_state(*, requested_status: str, warnings: List[str]) -> ReportWordingState:
    return ReportWordingState(
        label="DRAFT — NOT FINAL CERTIFICATION",
        certificate_title="Draft Shielding Assessment",
        assessment_status="PASS",
        report_status_effective="Draft — Not final certification",
        certification_allowed=False,
        signature_allowed=False,
        watermark="DRAFT",
        statement_heading="Draft assessment statement",
        statement=(
            "All assessed barriers are classified as PASS against the adopted weekly design goals for the stated "
            "operating conditions. This output is still marked Draft and should not be treated as a final certificate "
            "until it is reviewed and intentionally issued as Final."
        ),
        validity_heading="Conditions before final issue",
        validity_points=[
            "Review the calculation inputs, source data, geometry and shielding schedule.",
            "Confirm installed shielding thicknesses and construction details.",
            "Issue a Final report only after professional review and approval.",
        ],
        warnings=warnings,
        mandatory_disclaimers=[
            "Draft PASS wording is not final certification wording."
        ],
    )


def _certified_pass_state(*, requested_status: str) -> ReportWordingState:
    return ReportWordingState(
        label="CERTIFIED PASS",
        certificate_title="Certificate of Shielding Compliance",
        assessment_status="PASS",
        report_status_effective="Final",
        certification_allowed=True,
        signature_allowed=True,
        watermark="",
        statement_heading="Certification statement",
        statement=(
            "All assessed barriers are classified as PASS against the adopted weekly design goals for the stated "
            "operating conditions. This report may be used as a certificate of shielding compliance subject to "
            "the conditions of validity below."
        ),
        validity_heading="Conditions of validity",
        validity_points=[
            "This certificate applies only to the room layouts, barrier materials, installed shielding thicknesses and source workloads documented in this report.",
            "Any change in equipment type, room configuration, workload, occupancy, adjacent area use or shielding construction may invalidate this assessment.",
            "Shielding must be installed in accordance with the specified construction requirements and maintain full barrier continuity.",
            "Final regulatory acceptance remains subject to jurisdiction-specific installation and verification requirements.",
        ],
    )


def _collect_blocking_issues(
    *,
    source_readiness: Dict[str, Any],
    export_eligibility: Dict[str, Any],
    calculation_integrity: Dict[str, Any],
) -> List[str]:
    values: List[Any] = []
    values.extend(source_readiness.get("errors", []) or [])
    values.extend(export_eligibility.get("blocking_reasons", []) or [])
    values.extend(calculation_integrity.get("blocking_reasons", []) or [])
    return _unique_texts(values)


def _collect_warnings(
    *,
    source_readiness: Dict[str, Any],
    export_eligibility: Dict[str, Any],
    calculation_integrity: Dict[str, Any],
) -> List[str]:
    values: List[Any] = []
    values.extend(source_readiness.get("warnings", []) or [])
    values.extend(export_eligibility.get("warnings", []) or [])
    values.extend(calculation_integrity.get("warnings", []) or [])
    return _unique_texts(values)


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _is_final_like_status(status: str) -> bool:
    s = str(status or "").strip().upper()
    return any(token in s for token in FINAL_STATUS_TOKENS)


def _int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except Exception:
        return 0


def _unique_texts(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
