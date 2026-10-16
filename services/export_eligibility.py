from __future__ import annotations

"""
Central export/report eligibility gate.

MVP risk protected:
    Prevent the live preview, canonical payload, PDF gate and machine-readable
    exports from making different decisions when source data are incomplete.

This module deliberately knows nothing about Tkinter or report rendering. It
only converts source-readiness/preflight state into one explicit contract that
all output surfaces can consume.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional

from modalities.ct import CT_NULL_KSEC_BLOCK_REASON
from modalities.registry import source_blocking_reason_for_basis


NULL_KSEC_BLOCK_REASON = CT_NULL_KSEC_BLOCK_REASON
FINAL_STATUS_TOKENS = {"FINAL", "CERTIFIED", "ISSUED", "FOR ISSUE", "APPROVED"}


@dataclass(frozen=True)
class ExportEligibility:
    """Single output gate shared by preview/report/export code."""

    can_export_pdf: bool
    can_export_csv: bool
    can_certify: bool
    requires_acknowledgement: bool
    requested_report_status: str = "Draft"
    report_status_effective: str = "Draft"
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        """True only when all output modes are safe without restrictions."""
        return self.can_export_pdf and self.can_export_csv and self.can_certify

    @property
    def blocking(self) -> bool:
        return bool(self.blocking_reasons)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["allowed"] = self.allowed
        data["blocking"] = self.blocking
        return data


def assess_export_eligibility(
    *,
    preflight: Optional[Dict[str, Any]] = None,
    requested_report_status: str = "Draft",
) -> ExportEligibility:
    """
    Convert source readiness into one explicit export decision.

    Rules:
      * blocking source errors prevent CSV/JSON machine exports;
      * blocking source errors prevent Final/Certified/Issued PDFs;
      * Draft PDFs may still be generated, but are downgraded and visibly marked
        incomplete/review-only in the payload/certificate;
      * warnings allow exports but prevent certification/signature.
    """
    preflight = preflight or {}
    requested = str(requested_report_status or "Draft").strip() or "Draft"

    blocking_reasons = _normalised_blocking_reasons(preflight)
    warnings = _unique_texts(preflight.get("warnings", []) or [])
    wants_final = _is_final_like_status(requested)

    hard_output_block = _has_explicit_output_block(preflight)
    has_blocking = bool(blocking_reasons) or bool(preflight.get("blocking", False)) or hard_output_block
    if hard_output_block and not blocking_reasons:
        blocking_reasons = _explicit_output_block_reasons(preflight)
    if has_blocking and not blocking_reasons:
        blocking_reasons = ["BLOCKED: source validation has unresolved critical issue(s)."]

    if has_blocking:
        effective = "Draft — Incomplete Source Data"
        return ExportEligibility(
            can_export_pdf=False if hard_output_block else not wants_final,
            can_export_csv=False,
            can_certify=False,
            requires_acknowledgement=True,
            requested_report_status=requested,
            report_status_effective=effective,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
        )

    if warnings:
        return ExportEligibility(
            can_export_pdf=True,
            can_export_csv=True,
            can_certify=False,
            requires_acknowledgement=True,
            requested_report_status=requested,
            report_status_effective="Draft — Review Required" if wants_final else requested,
            blocking_reasons=[],
            warnings=warnings,
        )

    return ExportEligibility(
        can_export_pdf=True,
        can_export_csv=True,
        can_certify=True,
        requires_acknowledgement=False,
        requested_report_status=requested,
        report_status_effective=requested,
        blocking_reasons=[],
        warnings=[],
    )


def apply_export_eligibility_to_payload(
    payload: Dict[str, Any],
    *,
    preflight: Optional[Dict[str, Any]] = None,
    requested_report_status: Optional[str] = None,
) -> ExportEligibility:
    """
    Attach the central output gate to the canonical payload in-place.

    This keeps PDF rendering, JSON/CSV exports and tests aligned with the same
    decision used by the output pipeline preflight.
    """
    if preflight is None:
        preflight = payload.get("source_readiness", {}) or {}

    calculation_integrity = payload.get("calculation_integrity", {}) or {}
    gate_preflight = _preflight_with_calculation_integrity(
        preflight,
        calculation_integrity,
    )

    meta = payload.setdefault("meta", {})
    requested = requested_report_status or meta.get("report_status", "Draft")

    eligibility = assess_export_eligibility(
        preflight=gate_preflight,
        requested_report_status=str(requested or "Draft"),
    )
    eligibility_dict = eligibility.to_dict()

    payload["export_eligibility"] = eligibility_dict
    payload["source_readiness"] = preflight
    meta["report_status_requested"] = eligibility.requested_report_status
    meta["report_status_effective"] = eligibility.report_status_effective

    cert = payload.setdefault("certification", {})
    cert["report_status_effective"] = eligibility.report_status_effective
    cert["blocking_issues"] = list(eligibility.blocking_reasons)
    cert["warnings"] = list(eligibility.warnings)
    cert["certification_allowed"] = bool(cert.get("certification_allowed", True)) and eligibility.can_certify
    cert["signature_allowed"] = bool(cert.get("signature_allowed", True)) and eligibility.can_certify

    if eligibility.blocking_reasons:
        cert["assessment_status"] = "INCOMPLETE"
        cert["label"] = "INCOMPLETE — NOT FOR CERTIFICATION"
        cert["certificate_title"] = "Shielding Assessment — Not Certified"
        cert["statement_heading"] = "Assessment incomplete"
        cert["statement"] = (
            "The assessment contains unresolved source-data issue(s). It must not be "
            "issued as a final shielding compliance certificate until all blocking "
            "issues are resolved."
        )
    elif eligibility.warnings and not eligibility.can_certify:
        cert.setdefault("assessment_status", "REVIEW")
        cert.setdefault("label", "REVIEW — NOT FOR CERTIFICATION")
        cert.setdefault("certificate_title", "Shielding Assessment — Review Required")

    return eligibility


def build_export_prompt_message(eligibility: ExportEligibility) -> str:
    """Human-readable confirmation text for UI prompts."""
    lines: List[str] = []

    if eligibility.blocking_reasons:
        lines.append("Critical source validation issue(s):")
        lines.extend(f"• {item}" for item in eligibility.blocking_reasons[:8])

    if eligibility.warnings:
        if lines:
            lines.append("")
        lines.append("Source validation warning(s):")
        lines.extend(f"• {item}" for item in eligibility.warnings[:8])

    if lines:
        lines.append("")

    if eligibility.blocking_reasons:
        if eligibility.can_export_pdf:
            lines.append(
                "A Draft PDF can still be generated, but machine-readable exports "
                "and final certification are blocked."
            )
        elif not _is_final_like_status(eligibility.requested_report_status):
            lines.append("Normal PDF/CSV export and certification are blocked until these issue(s) are resolved.")
        else:
            lines.append("Final/certified output is blocked until these issue(s) are resolved.")
    elif eligibility.warnings:
        lines.append("Proceed with a review-required draft output?")
    else:
        lines.append("Proceed with output generation?")

    return "\n".join(lines)



def _preflight_with_calculation_integrity(
    preflight: Dict[str, Any],
    calculation_integrity: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a gate preflight containing source and payload-integrity blockers."""
    merged = dict(preflight or {})
    errors = list(merged.get("errors", []) or [])

    if isinstance(calculation_integrity, dict) and bool(calculation_integrity.get("blocking", False)):
        errors.extend(list(calculation_integrity.get("blocking_reasons", []) or []))
        merged["blocking"] = True
        if bool(calculation_integrity.get("output_blocking", False)):
            merged["output_blocking"] = True
        if str(merged.get("overall_status", "") or "").strip().upper() not in {"FAIL", "ERROR"}:
            merged["overall_status"] = "FAIL"

    merged["errors"] = errors
    return merged

def _has_explicit_output_block(preflight: Dict[str, Any]) -> bool:
    """True when a source contract forbids all normal output, including Draft PDF.

    This is intentionally distinct from ordinary incomplete-source blocking,
    where the existing workflow may still permit an acknowledged Draft PDF.
    Non-production SPECT uses this hard gate until a later production step
    deliberately removes it.
    """
    return bool(preflight.get("output_blocking", False)) or any(
        bool(source_result.get("output_blocking", False))
        for source_result in _iter_source_results(preflight)
    )



def _explicit_output_block_reasons(preflight: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    for source_result in _iter_source_results(preflight):
        if not bool(source_result.get("output_blocking", False)):
            continue
        message = str(source_result.get("message", "") or "").strip()
        room_name = str(source_result.get("room_name", "") or "").strip()
        if message:
            if room_name and not message.startswith(f"{room_name}:"):
                message = f"{room_name}: {message}"
            reasons.append(message)
    return _unique_texts(reasons)

def _normalised_blocking_reasons(preflight: Dict[str, Any]) -> List[str]:
    raw_errors = list(preflight.get("errors", []) or [])
    source_results = list(_iter_source_results(preflight))
    has_structured_null_ksec = any(_source_result_has_null_ksec(sr) for sr in source_results)

    reasons: List[str] = []

    # Preserve generic top-level preflight wording for legacy callers/tests.
    # Exception: when structured source-level readiness proves the specific CT
    # NULL/manual-override-required condition, replace matching top-level CT
    # NULL wording with the canonical single safety reason rather than reporting
    # both the raw text and the canonical text.
    for text in raw_errors:
        t = str(text or "").strip()
        if not t:
            continue
        if has_structured_null_ksec and _normalise_blocking_text(t) == NULL_KSEC_BLOCK_REASON:
            continue
        reasons.append(t)

    for source_result in source_results:
        if _source_result_has_null_ksec(source_result):
            reasons.append(_source_result_blocking_reason(source_result))
            for err in source_result.get("errors", []) or []:
                err_text = str(err or "").strip()
                if not err_text:
                    continue
                # Do not duplicate the canonical CT NULL-ksec reason. Preserve
                # any additional, non-ksec source error text.
                if _normalise_blocking_text(err_text) == NULL_KSEC_BLOCK_REASON:
                    continue
                reasons.append(err_text)
            continue

        for err in source_result.get("errors", []) or []:
            err_text = str(err or "").strip()
            if err_text:
                reasons.append(err_text)

    return _unique_texts(reasons)


def _source_result_has_null_ksec(source_result: Dict[str, Any]) -> bool:
    ksec_basis = str(source_result.get("ksec_basis", "") or source_result.get("basis", "") or "").strip()
    ksec_status = source_result.get("ksec_status", {}) or {}
    basis = ksec_basis or str(ksec_status.get("basis", "") or "").strip()
    return bool(_source_result_blocking_reason(source_result, basis=basis))


def _source_result_blocking_reason(source_result: Dict[str, Any], *, basis: str | None = None) -> str:
    source_type = str(source_result.get("source_type", "") or "").strip()
    if basis is None:
        ksec_status = source_result.get("ksec_status", {}) or {}
        basis = str(source_result.get("ksec_basis", "") or source_result.get("basis", "") or ksec_status.get("basis", "") or "").strip()
    reason = source_blocking_reason_for_basis(source_type, basis)
    return reason or (NULL_KSEC_BLOCK_REASON if basis == "manual_override_required" else "")

def _iter_source_results(preflight: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    # Room-level preflight objects are also valid callers of the eligibility
    # service, so inspect their source_results directly as well as the normal
    # project-level room_results envelope.
    for source_result in preflight.get("source_results", []) or []:
        if isinstance(source_result, dict):
            yield source_result

    for room_result in preflight.get("room_results", []) or []:
        if not isinstance(room_result, dict):
            continue
        for source_result in room_result.get("source_results", []) or []:
            if isinstance(source_result, dict):
                yield source_result


def _normalise_blocking_text(text: str) -> str:
    """Normalise only the explicit CT NULL-ksec safety messages.

    Preserve generic caller-supplied errors such as "Missing CT ksec" so
    legacy preflight tests and non-CT validation messages keep their original
    wording. The canonical NULL_KSEC_BLOCK_REASON is reserved for the specific
    safety-critical state where the selected CT scanner has NULL/missing ksec
    and requires a manual override before machine export/final certification.
    """
    t = str(text or "").strip()
    lower = t.lower()

    explicit_null_ksec = (
        "null/missing ksec" in lower
        or "ksec is null/missing" in lower
        or "ksec null/missing" in lower
        or "null ksec" in lower
        or "ct scanner ksec is missing" in lower
        or "selected ct scanner" in lower and "missing ksec" in lower
        or "manual override required" in lower and "ksec" in lower
    )
    if explicit_null_ksec:
        return NULL_KSEC_BLOCK_REASON

    return t


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


def _is_final_like_status(status: str) -> bool:
    s = str(status or "").strip().upper()
    return any(token in s for token in FINAL_STATUS_TOKENS)
