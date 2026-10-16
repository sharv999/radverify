"""Production CT modality descriptor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from config.geometry_constants import CT_GANTRY_DEPTH_M, CT_GANTRY_WIDTH_M, CT_TABLE_LENGTH_M, CT_TABLE_WIDTH_M

from modalities.base import DeclarativeModalityPlugin, GeometryUISpec, LayoutRenderSpec, ModalitySpec, ReportWordingSpec, SourceFormFieldSpec, SourceFormSchema, SourceSpec
from services.ct_scanner_resolution import (
    canonical_ct_vendor_label,
    default_ct_phantom_for_family,
    friendly_ct_model_name,
    raw_ct_family,
    resolve_family_selection,
)


CT_SOURCE_TYPE = "ct_scatter"
CT_SOURCE_LABEL = "Secondary scatter source diagnostic"
CT_DEFAULT_SOURCE_PARAMS = {
    "preset": "ct_low_dose",
    "use_scanner_db": "1",
    "scanner_vendor": "",
    "scanner_model": "",
    "scanner_kvp": 140,
    "scanner_source": "",
    "scans_per_week": 60,
    "ksec_mGy_per_100mAs_at_1m": 0.06,
    "workload_mAs_per_scan": 630,
}

CT_SOURCE_UI_LABELS = {
    "scanner_vendor": "Scanner vendor",
    "scanner_model": "Scanner model",
    "scanner_kvp": "Scanner kVp",
    "scans_per_week": "Scans per week",
    "workload_mAs_per_scan": "Workload (mAs/scan)",
    "ksec_mGy_per_100mAs_at_1m": "Ksec (mGy/100 mAs @ 1 m)",
    "manual_ksec_entered_by": "Manual ksec entered by",
    "manual_ksec_reason": "Manual ksec reason/source",
    "manual_ksec_reference": "Manual ksec reference",
    "manual_ksec_last_updated": "Manual ksec updated",
    "scanner_source": "Ksec status/source",
    "scanner_debug": "Scanner resolved",
}

CT_SOURCE_READINESS_LABELS = {
    "source_type": "Source type",
    "scanner_family": "Scanner family",
    "scanner_model": "Scanner model",
    "ksec": "Ksec",
    "ksec_basis": "Ksec basis",
    "manual_ksec_audit": "Manual ksec audit",
    "ksec_energy_basis": "Ksec energy basis",
    "scans_per_week": "Scans per week",
    "workload_mAs_per_scan": "Workload mAs/scan",
    "scanner_kvp": "Scanner kVp",
    "tvl_key": "TVL key",
}


CT_REPORT_WORDING = ReportWordingSpec(
    report_title="Preliminary CT Shielding Schedule",
    report_subtitle="Preliminary / quotation-only CT shielding assessment schedule",
    cover_introduction=(
        "This output is intended as an internal calculation schedule to support early project pricing and design review. "
        "It is not a certified radiation shielding assessment report."
    ),
    limitations_heading="Preliminary assessment limitations",
    limitation_bullets=(
        "This document is a preliminary CT shielding schedule for internal quotation and early design review only.",
        "It is not a certified radiation shielding assessment report and should not be issued as final regulatory documentation.",
        "Final shielding assessment requires review of architectural drawings, construction details, source/workload assumptions, occupancy assumptions and installed materials.",
        "Calculated results depend on the entered room geometry, scanner model/ksec data, workload, design goal and occupancy factors.",
        "Manual ksec overrides must be independently verified before final certification.",
    ),
    room_schedule_prefix="Room schedule",
    room_layout_heading="Room layout",
    barrier_schedule_heading="Barrier schedule",
    source_inputs_heading="Source inputs",
    methodology_rows=(("CT", "CT scatter workload model using scanner and workload inputs."),),
    construction_shielding_height_mm=2700,
)

CT_SOURCE_REPORT_SUMMARY_COLUMNS = (
    ("name", "Source"),
    ("source_type", "Type"),
    ("radiation_type", "Radiation"),
    ("ksec_basis_status", "ksec basis / status"),
)


def ct_source_report_summary_row(source_payload: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """Return the PDF source-summary row for a CT scatter source.

    The calculation/report payload already contains the resolved ksec basis;
    this formatter only controls CT-specific display wording for the concise
    quotation report.
    """

    basis = source_payload.get("ksec_basis", {}) or {}
    basis_text = ""
    if isinstance(basis, Mapping) and basis.get("is_ct_scatter"):
        basis_text = str(basis.get("basis", "") or basis.get("status", "") or "")
        ksec = basis.get("ksec_mGy_per_100mAs_at_1m")
        if ksec not in (None, ""):
            basis_text += f"; ksec={ksec}"

    return (
        str(source_payload.get("name", "") or ""),
        str(source_payload.get("source_type", "") or ""),
        str(source_payload.get("radiation_type", "") or ""),
        basis_text,
    )


def ct_source_report_content(source_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build CT-owned report content consumed generically by PDF/export services."""
    params = dict(source_payload.get("params", {}) or {})
    source_type = str(source_payload.get("source_type", CT_SOURCE_TYPE) or CT_SOURCE_TYPE)
    status = resolve_ct_ksec_status_from_params(source_type, params).as_dict()
    if not status.get("is_ct_scatter"):
        return {}

    status["ksec_mGy_per_100mAs_at_1m"] = status.get("ksec")
    status["scanner_ksec_status"] = str(params.get("scanner_ksec_status", "") or "")
    status["manual_ksec_override"] = str(params.get("manual_ksec_override", "") or "")
    status["ksec_definition"] = str(params.get("ksec_definition", "") or "")
    status["ksec_reference_distance_m"] = params.get("ksec_reference_distance_m", "")

    audit_parts: list[str] = []
    if status.get("manual_override"):
        for label, key in (
            ("entered by", "manual_ksec_entered_by"),
            ("reason/source:", "manual_ksec_reason"),
            ("reference:", "manual_ksec_source_reference"),
            ("updated", "manual_ksec_last_updated"),
        ):
            value = str(status.get(key, "") or "").strip()
            if value:
                audit_parts.append(f"{label} {value}")
        if not audit_parts:
            audit_parts.append("audit trail incomplete")
    status["manual_ksec_audit_text"] = "; ".join(audit_parts)

    source_audit = str(status.get("source_text", "") or status.get("scanner_source", "") or "-")
    if status["manual_ksec_audit_text"]:
        source_audit = f"{source_audit} | {status['manual_ksec_audit_text']}"

    detail_rows = [
        ["Scanner model", str(status.get("scanner_model", "") or "")],
        ["Scanner family ID", str(status.get("scanner_family", "") or "")],
        ["ksec", str(status.get("ksec_display", "") or "")],
        ["ksec basis", str(status.get("basis_label", "") or "")],
        ["ksec source", str(status.get("source_text", "") or "")],
    ]
    if status["manual_ksec_audit_text"]:
        detail_rows.append(["manual ksec audit", status["manual_ksec_audit_text"]])

    limitation = str(status.get("limitation", "") or "").strip()
    notes = []
    if limitation:
        notes.append({
            "text": limitation,
            "style": "FailText" if status.get("basis") == "manual_override_required" else "Muted",
        })

    assumptions = []
    if status.get("basis") == "manual_override":
        assumptions.append(
            "One or more CT scatter ksec values were supplied as documented manual overrides. "
            "These values should be traceable to a vendor source, site measurement, or physicist-approved engineering basis."
        )
    elif status.get("basis") == "manual_override_required":
        assumptions.append(
            "One or more selected CT scanners have NULL or missing database ksec and no manual override. "
            "The associated shielding calculations are incomplete and should not be issued as final until resolved."
        )

    return {
        "metadata": status,
        "input_supplement": {
            "group_key": "ct_ksec_basis",
            "heading": "CT scanner ksec basis",
            "headings": ["Room", "Scanner", "Family ID", "Ksec", "Basis", "Source / audit"],
            "row": [
                str(source_payload.get("room_name", "") or ""),
                str(status.get("scanner_model", "") or ""),
                str(status.get("scanner_family", "") or ""),
                str(status.get("ksec_display", "") or ""),
                str(status.get("basis_label", "") or ""),
                source_audit,
            ],
            "column_widths_mm": [24, 34, 36, 22, 27, 43],
            "blocking_message": (
                "<b>Calculation incomplete:</b> one or more selected CT scanners have NULL/missing database ksec "
                "and no documented manual override. The report should not be issued as a final compliance certificate "
                "until these source inputs are resolved."
                if status.get("basis") == "manual_override_required" else ""
            ),
            "warning_message": (
                "One or more CT scatter ksec values were entered as documented manual overrides because a "
                "scanner-specific database value was not available."
                if status.get("basis") == "manual_override" else ""
            ),
        },
        "detail_tables": [{"rows": detail_rows, "widths_mm": [45, 105], "header": False}],
        "detail_notes": notes,
        "parameter_rows": [
            ["Ksec basis", str(status.get("basis_label", "") or "")],
            ["Ksec value", str(status.get("ksec_display", "") or "")],
            *([["Manual ksec audit", status["manual_ksec_audit_text"]]] if status["manual_ksec_audit_text"] else []),
            *([["Ksec note", limitation]] if limitation else []),
        ],
        "assumption_bullets": assumptions,
        "summary_tags": {"ksec_basis": str(status.get("basis", "") or "")},
    }


CT_NULL_KSEC_BLOCK_REASON = "BLOCKED: selected CT scanner has NULL/missing ksec."

CT_KSEC_VALIDATION_MESSAGES = {
    "not_applicable_message": "Not a CT scatter source.",
    "manual_override_required_label": "Manual override required",
    "manual_override_required_message": "CT scanner ksec is missing. A documented manual override is required before final calculation or certification.",
    "manual_override_required_limitation": (
        "Selected CT scanner has NULL or missing ksec and no usable manual override. "
        "Shielding calculations for this source are incomplete until ksec is resolved."
    ),
    "manual_override_label": "Manual override",
    "manual_override_message": "Manual CT scanner ksec override is being used.",
    "manual_override_limitation": (
        "Manual CT scatter ksec override used. The value should be traceable to a vendor source, "
        "site measurement, published source, or physicist-approved engineering basis."
    ),
    "manual_override_audit_incomplete_message": "Manual ksec override audit trail is incomplete: add a reason/source or reference.",
    "database_label": "Database",
    "database_message": "Database CT scanner ksec is being used.",
    "missing_scanner_family": "Scanner family is not resolved.",
    "missing_scanner_model": "Scanner model is not recorded.",
    "ksec_energy_missing": "Ksec energy basis is missing; scanner kVp fallback may be used.",
    "scans_invalid": "Scans per week must be greater than zero.",
    "workload_invalid": "Workload mAs/scan must be greater than zero.",
    "scanner_kvp_invalid": "Scanner kVp is missing or invalid.",
    "tvl_key_missing": "TVL key/radiation type is not resolved.",
}


@dataclass(frozen=True)
class KsecStatus:
    is_ct_scatter: bool
    basis: str
    basis_label: str
    status: str
    severity: str
    ksec: Optional[float]
    ksec_display: str
    message: str
    limitation: str
    scanner_family: str
    scanner_vendor: str
    scanner_model: str
    source_text: str
    audit_complete: bool
    manual_override: bool
    manual_ksec_entered_by: str
    manual_ksec_reason: str
    manual_ksec_source_reference: str
    manual_ksec_last_updated: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_ct_scatter": self.is_ct_scatter,
            "basis": self.basis,
            "basis_label": self.basis_label,
            "status": self.status,
            "severity": self.severity,
            "ksec": self.ksec,
            "ksec_display": self.ksec_display,
            "message": self.message,
            "limitation": self.limitation,
            "scanner_family": self.scanner_family,
            "scanner_vendor": self.scanner_vendor,
            "scanner_model": self.scanner_model,
            "source_text": self.source_text,
            "audit_complete": self.audit_complete,
            "manual_override": self.manual_override,
            "manual_ksec_entered_by": self.manual_ksec_entered_by,
            "manual_ksec_reason": self.manual_ksec_reason,
            "manual_ksec_source_reference": self.manual_ksec_source_reference,
            "manual_ksec_last_updated": self.manual_ksec_last_updated,
            "scanner_source": self.source_text,
            "ksec_source": self.source_text,
            "ksec_confidence": self.severity,
        }


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _is_truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "manual", "override"}


def _float_or_none(value: Any) -> Optional[float]:
    raw = _text(value)
    if raw in {"", "NULL", "null", "None", "none", "nan", "NaN"}:
        return None
    try:
        number = float(raw)
    except Exception:
        return None
    if number <= 0:
        return None
    return number


def _source_text_indicates_missing_or_default(source_text: str) -> bool:
    text = _text(source_text).lower()
    return any(
        marker in text
        for marker in (
            "conservative default",
            "manual override required",
            "null ksec",
            "missing worst_case_ksec",
            "missing worst case",
            "no json scatter match",
            "ksec cannot be resolved",
        )
    )


def is_ct_ksec_source_type(source_type: Any) -> bool:
    return _text(source_type) in {CT_SOURCE_TYPE, "spect_ct_secondary_scatter"}


def resolve_ct_ksec_status_from_params(
    source_type: Any,
    params: Mapping[str, Any] | None,
) -> KsecStatus:
    """Resolve CT ksec/database/manual-override blocking state for CT-like sources."""

    p = dict(params or {})
    stype = _text(source_type)
    is_ct = is_ct_ksec_source_type(stype)

    scanner_family = _text(p.get("scanner_family"))
    scanner_vendor = _text(p.get("scanner_vendor"))
    scanner_model = _text(p.get("scanner_model"))
    source_text = _text(
        p.get("scanner_source")
        or p.get("ksec_source")
        or p.get("source_text")
    )

    entered_by = _text(p.get("manual_ksec_entered_by"))
    reason = _text(p.get("manual_ksec_reason") or p.get("manual_ksec_reason_source"))
    reference = _text(p.get("manual_ksec_source_reference") or p.get("manual_ksec_reference"))
    updated = _text(p.get("manual_ksec_last_updated"))

    if not is_ct:
        return KsecStatus(
            is_ct_scatter=False,
            basis="not_applicable",
            basis_label="Not applicable",
            status="PASS",
            severity="info",
            ksec=None,
            ksec_display="",
            message=CT_KSEC_VALIDATION_MESSAGES["not_applicable_message"],
            limitation="",
            scanner_family=scanner_family,
            scanner_vendor=scanner_vendor,
            scanner_model=scanner_model,
            source_text=source_text,
            audit_complete=True,
            manual_override=False,
            manual_ksec_entered_by=entered_by,
            manual_ksec_reason=reason,
            manual_ksec_source_reference=reference,
            manual_ksec_last_updated=updated,
        )

    ksec = _float_or_none(p.get("ksec_mGy_per_100mAs_at_1m"))
    manual = _is_truthy(p.get("manual_ksec_override"))
    source_indicates_missing_or_default = _source_text_indicates_missing_or_default(source_text)

    if source_indicates_missing_or_default and not manual:
        ksec = None

    if ksec is None:
        basis = "manual_override_required"
        basis_label = CT_KSEC_VALIDATION_MESSAGES["manual_override_required_label"]
        status = "FAIL"
        severity = "critical"
        display = ""
        message = CT_KSEC_VALIDATION_MESSAGES["manual_override_required_message"]
        limitation = CT_KSEC_VALIDATION_MESSAGES["manual_override_required_limitation"]
        audit_complete = False

    elif manual:
        basis = "manual_override"
        basis_label = CT_KSEC_VALIDATION_MESSAGES["manual_override_label"]
        status = "REVIEW"
        severity = "warning"
        display = f"{ksec:.6g} mGy/100 mAs @ 1 m"
        audit_complete = bool(reason or reference)
        message = CT_KSEC_VALIDATION_MESSAGES["manual_override_message"]
        limitation = CT_KSEC_VALIDATION_MESSAGES["manual_override_limitation"]
        if not audit_complete:
            limitation += " " + CT_KSEC_VALIDATION_MESSAGES["manual_override_audit_incomplete_message"]

    else:
        basis = "database"
        basis_label = CT_KSEC_VALIDATION_MESSAGES["database_label"]
        status = "PASS"
        severity = "info"
        display = f"{ksec:.6g} mGy/100 mAs @ 1 m"
        message = CT_KSEC_VALIDATION_MESSAGES["database_message"]
        limitation = ""
        audit_complete = True

    return KsecStatus(
        is_ct_scatter=True,
        basis=basis,
        basis_label=basis_label,
        status=status,
        severity=severity,
        ksec=ksec,
        ksec_display=display,
        message=message,
        limitation=limitation,
        scanner_family=scanner_family,
        scanner_vendor=scanner_vendor,
        scanner_model=scanner_model,
        source_text=source_text,
        audit_complete=audit_complete,
        manual_override=manual,
        manual_ksec_entered_by=entered_by,
        manual_ksec_reason=reason,
        manual_ksec_source_reference=reference,
        manual_ksec_last_updated=updated,
    )


def _float_or_none_for_readiness(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower().endswith("kvp"):
            text = text[:-3].strip()
        return float(text)
    except Exception:
        return None


def _add_check(checks: list[dict[str, str]], name: str, status: str, detail: str = "") -> None:
    checks.append({"name": str(name), "status": str(status), "detail": str(detail or "")})


def _overall_status(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "FAIL"
    if warnings:
        return "REVIEW"
    return "PASS"


def ct_ksec_source_readiness_result(
    source_type: str,
    params: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return source-readiness result for a CT ksec scatter source.

    This is the CT modality's validation/blocking rule implementation.  It is
    intentionally UI-independent and preserves the legacy result shape consumed
    by preflight, export eligibility and report payload builders.
    """

    params = dict(params or {})
    room_name = _text(context.get("room_name"))
    room_modality = _text(context.get("room_modality"))
    source_name = _text(context.get("source_name"))
    radiation_type = _text(context.get("radiation_type"))

    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def label(key: str, default: str) -> str:
        return str(CT_SOURCE_READINESS_LABELS.get(key, default))

    if not is_ct_ksec_source_type(source_type):
        _add_check(checks, label("source_type", "Source type"), "PASS", source_type or "non-CT source")
        return {
            "overall_status": "PASS",
            "status": "PASS",
            "blocking": False,
            "room_name": room_name,
            "room_modality": room_modality,
            "source_name": source_name,
            "source_type": source_type,
            "message": "Source ready.",
            "checks": checks,
            "errors": [],
            "warnings": [],
            "basis": "not_applicable",
        }

    _add_check(checks, label("source_type", "Source type"), "PASS", source_type)

    family = _text(params.get("scanner_family"))
    vendor = _text(params.get("scanner_vendor"))
    model = _text(params.get("scanner_model"))

    if family:
        _add_check(checks, label("scanner_family", "Scanner family"), "PASS", family)
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["missing_scanner_family"]
        errors.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("scanner_family", "Scanner family"), "FAIL", msg)

    if model:
        model_label = f"{vendor} {model}".strip()
        _add_check(checks, label("scanner_model", "Scanner model"), "PASS", model_label)
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["missing_scanner_model"]
        warnings.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("scanner_model", "Scanner model"), "REVIEW", msg)

    ksec_info = resolve_ct_ksec_status_from_params(source_type, params).as_dict()
    basis = str(ksec_info.get("basis", "") or "")
    ksec_status = str(ksec_info.get("status", "FAIL") or "FAIL")
    ksec_message = str(ksec_info.get("message", "") or "")

    if basis == "manual_override_required" or ksec_status == "FAIL":
        msg = CT_KSEC_VALIDATION_MESSAGES["manual_override_required_message"]
        errors.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("ksec", "Ksec"), "FAIL", ksec_message or msg)
        limitation = str(ksec_info.get("limitation", "") or "").strip()
        if limitation:
            _add_check(checks, label("ksec_basis", "Ksec basis"), "FAIL", limitation)

    elif basis == "manual_override":
        msg = CT_KSEC_VALIDATION_MESSAGES["manual_override_message"]
        warnings.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("ksec", "Ksec"), "REVIEW", ksec_info.get("ksec_display", "") or msg)
        _add_check(checks, label("ksec_basis", "Ksec basis"), "REVIEW", ksec_info.get("source_text", "") or "manual override")

        if bool(ksec_info.get("audit_complete", False)):
            _add_check(checks, label("manual_ksec_audit", "Manual ksec audit"), "PASS", "Reason/source or reference present.")
        else:
            audit_msg = CT_KSEC_VALIDATION_MESSAGES["manual_override_audit_incomplete_message"]
            warnings.append(f"{room_name}: {audit_msg}" if room_name else audit_msg)
            _add_check(checks, label("manual_ksec_audit", "Manual ksec audit"), "REVIEW", audit_msg)

    else:
        display = str(ksec_info.get("ksec_display", "") or "")
        _add_check(checks, label("ksec", "Ksec"), "PASS", f"Database ksec: {display}" if display else "Database ksec available.")
        _add_check(checks, label("ksec_basis", "Ksec basis"), "PASS", str(ksec_info.get("source_text", "") or "database"))

    ksec_energy = _float_or_none_for_readiness(params.get("ksec_energy_kvp", params.get("scanner_kvp", "")))
    if ksec_energy is not None and ksec_energy > 0:
        _add_check(checks, label("ksec_energy_basis", "Ksec energy basis"), "PASS", f"{ksec_energy:g} kVp")
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["ksec_energy_missing"]
        warnings.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("ksec_energy_basis", "Ksec energy basis"), "REVIEW", msg)

    scans = _float_or_none_for_readiness(params.get("scans_per_week", ""))
    if scans is not None and scans > 0:
        _add_check(checks, label("scans_per_week", "Scans per week"), "PASS", f"{scans:g}")
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["scans_invalid"]
        errors.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("scans_per_week", "Scans per week"), "FAIL", msg)

    workload = _float_or_none_for_readiness(params.get("workload_mAs_per_scan", ""))
    if workload is not None and workload > 0:
        _add_check(checks, label("workload_mAs_per_scan", "Workload mAs/scan"), "PASS", f"{workload:g}")
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["workload_invalid"]
        errors.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("workload_mAs_per_scan", "Workload mAs/scan"), "FAIL", msg)

    kvp = _float_or_none_for_readiness(params.get("scanner_kvp", ""))
    if kvp is not None and kvp > 0:
        _add_check(checks, label("scanner_kvp", "Scanner kVp"), "PASS", f"{kvp:g}")
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["scanner_kvp_invalid"]
        warnings.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("scanner_kvp", "Scanner kVp"), "REVIEW", msg)

    tvl_key = _text(radiation_type or params.get("tvl_key", ""))
    if tvl_key:
        _add_check(checks, label("tvl_key", "TVL key"), "PASS", tvl_key)
    else:
        msg = CT_KSEC_VALIDATION_MESSAGES["tvl_key_missing"]
        warnings.append(f"{room_name}: {msg}" if room_name else msg)
        _add_check(checks, label("tvl_key", "TVL key"), "REVIEW", msg)

    status = _overall_status(errors, warnings)

    return {
        "overall_status": status,
        "status": status,
        "blocking": bool(errors),
        "room_name": room_name,
        "room_modality": room_modality,
        "source_name": source_name,
        "source_type": source_type,
        "message": ksec_message or ("Source ready." if status == "PASS" else "Source requires review."),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "scanner_family": family,
        "scanner_vendor": vendor,
        "scanner_model": model,
        "scanner_kvp": kvp,
        "ksec_energy_kvp": ksec_energy,
        "ksec_mGy_per_100mAs_at_1m": ksec_info.get("ksec"),
        "ksec_display": ksec_info.get("ksec_display", ""),
        "basis": basis,
        "basis_label": ksec_info.get("basis_label", ""),
        "severity": ksec_info.get("severity", ""),
        "audit_complete": ksec_info.get("audit_complete", ""),
        "manual_override": ksec_info.get("manual_override", ""),
        "source_text": ksec_info.get("source_text", ""),
        "limitation": ksec_info.get("limitation", ""),
        "ksec_basis": basis,
        "ksec_status": ksec_info,
        "scanner_ksec_status": str(params.get("scanner_ksec_status", "") or ""),
        "scanner_source": str(params.get("scanner_source", "") or ""),
        "manual_ksec_override": str(params.get("manual_ksec_override", "") or ""),
        "scans_per_week": scans,
        "workload_mAs_per_scan": workload,
        "radiation_type": tvl_key,
    }

CT_MODALITY = ModalitySpec(
    modality_id="CT",
    display_name="CT",
    production_enabled=True,
    default_room_name="CT Room 1",
    expected_sources=(
        SourceSpec(
            CT_SOURCE_TYPE,
            CT_SOURCE_LABEL,
            role="ct_ksec_scatter",
            default_radiation_type="xray_140kvp",
            default_params=CT_DEFAULT_SOURCE_PARAMS,
            form_kind="ct_ksec",
            ui_labels=CT_SOURCE_UI_LABELS,
            readiness_labels=CT_SOURCE_READINESS_LABELS,
            report_summary_columns=CT_SOURCE_REPORT_SUMMARY_COLUMNS,
            report_summary_formatter=ct_source_report_summary_row,
            report_content_builder=ct_source_report_content,
            dose_model="ct_ksec_weekly_dose",
            default_tvl_key="xray_140kvp",
            contribution_group="ct_scatter",
            ncrp_solver_mode="ncrp_ct_secondary",
            validation_kind="ct_ksec",
            readiness_validator=ct_ksec_source_readiness_result,
            blocking_reason_by_basis={"manual_override_required": CT_NULL_KSEC_BLOCK_REASON},
        ),
    ),
    geometry_ui=GeometryUISpec(
        selector_kind="ct_scanner_database",
        scanner_metadata_group="ct_standalone_diagnostic",
        symbol_kind="ct_scanner",
        primary_source_role="ct_ksec_scatter",
        source_label="CT",
    ),
    layout_rendering=LayoutRenderSpec(
        source_symbol_kind="ct_scanner",
        show_radiation_symbol=True,
        show_one_m_circle=True,
        show_barrier_status_text=False,
        annotation_kind="ct_weekly_scatter",
        equipment_width_m=CT_GANTRY_WIDTH_M,
        equipment_depth_m=CT_GANTRY_DEPTH_M,
        table_width_m=CT_TABLE_WIDTH_M,
        table_length_m=CT_TABLE_LENGTH_M,
        label_cleanup_phrases=("diagnostic CT family.", "diagnostic CT.", "CT component."),
        source_label_param="scanner_model",
        render_param_keys=(
            "ksec_mGy_per_100mAs_at_1m",
            "scans_per_week",
            "workload_mAs_per_scan",
            "scanner_kvp",
            "scanner_family",
            "scanner_vendor",
            "scanner_model",
            "scanner_source",
            "scanner_ksec_status",
            "ksec_energy_kvp",
        ),
        render_param_defaults={
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "scanner_kvp": 140,
        },
    ),
    classification="ionising_imaging_controlled",
    default_energy_label="140 kVp",
    default_solver_mode="auto",
    controlled_area_required=True,
    xray_generator_present=True,
    notes="Standalone CT room using CT secondary scatter model.",
    report_wording=CT_REPORT_WORDING,
)


class CTModalityPlugin(DeclarativeModalityPlugin):
    """CT plugin with modality-owned Geometry source synchronisation."""

    def initialise_app_services(self, app, base_path) -> None:
        from services.ct_scanner_resolution import load_ct_scanner_resolution_context
        app.ct_scanner_resolution_context = load_ct_scanner_resolution_context(base_path)
        app.ct_scanner_resolution_status_message = app.ct_scanner_resolution_context.engine_status_message

    def source_form_vendor_values(self, app, source_type):
        from services.ct_scanner_resolution import ct_vendor_values_for_source_type
        return tuple(ct_vendor_values_for_source_type(app.ct_scanner_resolution_context, source_type) or ())

    def source_form_model_values(self, app, source_type):
        from services.ct_scanner_resolution import ct_model_values_for_source_type
        vendor = str(app.ct_vars["scanner_vendor"].get()).strip()
        return tuple(ct_model_values_for_source_type(app.ct_scanner_resolution_context, source_type, vendor) or ())

    def source_form_schema(self, app, source_type):
        source_spec = self.source_spec_for_type(source_type)
        if source_spec is None or source_spec.form_kind != "ct_ksec":
            return None

        labels = dict(source_spec.ui_labels or {})
        def label(key, default):
            return str(labels.get(key, default))

        return SourceFormSchema(
            source_type=source_spec.source_type,
            fields=(
                SourceFormFieldSpec(
                    key="scanner_vendor", label=label("scanner_vendor", "Scanner vendor"), row=0,
                    variable_group="ct_vars", widget_kind="combobox", state="disabled",
                    values=self.source_form_vendor_values(app, source_type), widget_attr="ct_vendor_combo",
                ),
                SourceFormFieldSpec(
                    key="scanner_model", label=label("scanner_model", "Scanner model"), row=1,
                    variable_group="ct_vars", widget_kind="combobox", state="disabled",
                    values=self.source_form_model_values(app, source_type), widget_attr="ct_model_combo",
                ),
                SourceFormFieldSpec(
                    key="scanner_kvp", label=label("scanner_kvp", "Scanner kVp"), row=2,
                    variable_group="ct_vars", widget_kind="readonly_entry",
                ),
                SourceFormFieldSpec(
                    key="scans_per_week", label=label("scans_per_week", "Scans per week"), row=3,
                    variable_group="ct_vars",
                ),
                SourceFormFieldSpec(
                    key="workload_mAs_per_scan", label=label("workload_mAs_per_scan", "Workload (mAs/scan)"), row=4,
                    variable_group="ct_vars",
                ),
                SourceFormFieldSpec(
                    key="ksec_mGy_per_100mAs_at_1m",
                    label=label("ksec_mGy_per_100mAs_at_1m", "Ksec (mGy/100 mAs @ 1 m)"), row=5,
                    variable_group="ct_vars", widget_attr="ct_ksec_entry",
                    event_sequence="<KeyRelease>", event_kind="manual_ksec_edited",
                ),
                SourceFormFieldSpec(
                    key="manual_ksec_entered_by", label=label("manual_ksec_entered_by", "Manual ksec entered by"), row=6,
                    variable_group="ct_vars",
                ),
                SourceFormFieldSpec(
                    key="manual_ksec_reason", label=label("manual_ksec_reason", "Manual ksec reason/source"), row=7,
                    variable_group="ct_vars",
                ),
                SourceFormFieldSpec(
                    key="manual_ksec_reference", label=label("manual_ksec_reference", "Manual ksec reference"), row=8,
                    variable_group="ct_vars",
                ),
                SourceFormFieldSpec(
                    key="manual_ksec_last_updated", label=label("manual_ksec_last_updated", "Manual ksec updated"), row=9,
                    variable_group="ct_vars", widget_kind="readonly_entry",
                ),
                SourceFormFieldSpec(
                    key="scanner_source", label=label("scanner_source", "Ksec status/source"), row=10,
                    variable_group="ct_vars", widget_kind="readonly_entry",
                ),
                SourceFormFieldSpec(
                    key="scanner_debug", label=label("scanner_debug", "Scanner resolved"), row=11,
                    variable_group="ct_vars", widget_kind="readonly_entry",
                ),
            ),
        )

    @staticmethod
    def _form_energy_kvp(app) -> int:
        try:
            return int(float(str(app.ct_vars["scanner_kvp"].get()).strip()))
        except Exception:
            return 140

    def source_form_tvl_params(self, app, source_type):
        source_spec = self.source_spec_for_type(source_type)
        if source_spec is None or source_spec.form_kind != "ct_ksec":
            return None
        return {
            "scans_per_week": str(app.ct_vars["scans_per_week"].get()).strip() or 0,
            "ksec_mGy_per_100mAs_at_1m": str(app.ct_vars["ksec_mGy_per_100mAs_at_1m"].get()).strip() or 0,
            "workload_mAs_per_scan": str(app.ct_vars["workload_mAs_per_scan"].get()).strip() or 0,
        }

    def handle_source_form_event(self, app, event_kind, source_type, *, force=False):
        if event_kind == "manual_ksec_edited":
            from tabs.source_ct_audit import mark_manual_ct_ksec_override
            return mark_manual_ct_ksec_override(app)

        from services.ct_scanner_resolution import central_ct_ksec_resolver, resolve_family_selection
        if not hasattr(app, "ct_vars"):
            return None
        stype = str(source_type or "")
        if event_kind in {"vendor_changed", "model_changed"}:
            selection = resolve_family_selection(
                app.ct_scanner_resolution_context,
                source_type=stype,
                vendor=app.ct_vars["scanner_vendor"].get(),
                model=app.ct_vars["scanner_model"].get(),
            )
            app.ct_vars["scanner_family"].set(selection.scanner_family)
            app.ct_vars["scanner_phantom"].set(selection.scanner_phantom)
        use_auto = str(app.ct_vars["use_scanner_db"].get()).strip() == "1"
        manual_override = str(app.ct_vars["manual_ksec_override"].get()).strip() == "1"
        if not use_auto and not force:
            return None
        if manual_override and not force:
            return None
        resolution = central_ct_ksec_resolver(
            app.ct_scanner_resolution_context,
            source_type=stype,
            vendor=app.ct_vars["scanner_vendor"].get(),
            model=app.ct_vars["scanner_model"].get(),
            kvp=self._form_energy_kvp(app),
        )
        app.ct_vars["scanner_family"].set(resolution.scanner_family)
        app.ct_vars["scanner_phantom"].set(resolution.phantom)
        app.ct_vars["manual_ksec_override"].set("0")
        for key in ("manual_ksec_entered_by", "manual_ksec_reason", "manual_ksec_reference", "manual_ksec_last_updated"):
            app.ct_vars[key].set("")
        app.ct_vars["scanner_source"].set(resolution.scanner_source)
        app.ct_vars["scanner_debug"].set(resolution.scanner_debug)
        if resolution.requires_manual_override or resolution.ksec_mGy_per_100mAs_at_1m is None:
            app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set("")
            return None
        ksec = float(resolution.ksec_mGy_per_100mAs_at_1m)
        app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set(f"{ksec:.6g}")
        return ksec

    def collect_source_form_params(self, app, source_type):
        defaults = self.default_source_params(source_type)
        def val(key, default=""):
            try:
                return app.ct_vars[key].get()
            except Exception:
                return default
        def f(key, default):
            try: return float(val(key, default))
            except Exception: return float(default)
        def i(key, default):
            try: return int(float(val(key, default)))
            except Exception: return int(default)
        raw_ksec = str(val("ksec_mGy_per_100mAs_at_1m", "")).strip()
        return {
            "preset": str(val("preset", defaults.get("preset", "ct_low_dose"))).strip() or str(defaults.get("preset", "ct_low_dose")),
            "use_scanner_db": str(val("use_scanner_db", defaults.get("use_scanner_db", "1"))).strip() or "1",
            "manual_ksec_override": str(val("manual_ksec_override", "0")).strip() or "0",
            "scanner_family": str(val("scanner_family", "")).strip(),
            "scanner_phantom": str(val("scanner_phantom", defaults.get("scanner_phantom", "body"))).strip() or "body",
            "scanner_vendor": str(val("scanner_vendor", "")).strip(),
            "scanner_model": str(val("scanner_model", "")).strip(),
            "scanner_kvp": i("scanner_kvp", defaults.get("scanner_kvp", 140)),
            "scanner_source": str(val("scanner_source", "")).strip(),
            "scans_per_week": f("scans_per_week", defaults.get("scans_per_week", 60.0)),
            "ksec_mGy_per_100mAs_at_1m": "" if raw_ksec in {"", "NULL", "null", "None", "none"} else f("ksec_mGy_per_100mAs_at_1m", defaults.get("ksec_mGy_per_100mAs_at_1m", 0.0)),
            "workload_mAs_per_scan": f("workload_mAs_per_scan", defaults.get("workload_mAs_per_scan", 630.0)),
        }

    def load_source_form_params(self, app, source_type, params) -> bool:
        from services.ct_scanner_resolution import (canonical_ct_vendor_label, default_ct_phantom_for_family, friendly_ct_model_name, raw_ct_family, resolve_database_ct_ksec_from_context, resolve_family_selection)
        p = dict(params or {})
        defaults = self.default_source_params(source_type)
        family = str(p.get("scanner_family", "") or "").strip()
        vendor = str(p.get("scanner_vendor", "") or "").strip()
        model = str(p.get("scanner_model", "") or "").strip()
        if family:
            try:
                fam = raw_ct_family(app.ct_scanner_resolution_context, family)
                if not vendor: vendor = canonical_ct_vendor_label(app.ct_scanner_resolution_context, fam.get("vendor", ""))
                if not model: model = friendly_ct_model_name(app.ct_scanner_resolution_context, family)
            except Exception: pass
        if not family:
            family = resolve_family_selection(app.ct_scanner_resolution_context, source_type=source_type, vendor=vendor, model=model).scanner_family
        app.ct_vars["scanner_family"].set(family)
        app.ct_vars["scanner_phantom"].set(str(p.get("scanner_phantom", "") or default_ct_phantom_for_family(app.ct_scanner_resolution_context, family)))
        app.ct_vars["scanner_vendor"].set(vendor)
        app.ct_vars["scanner_model"].set(model or friendly_ct_model_name(app.ct_scanner_resolution_context, family))
        for key, default in (("preset", "ct_low_dose"), ("use_scanner_db", "1"), ("manual_ksec_override", "0"), ("scanner_kvp", "140"), ("scans_per_week", "60"), ("workload_mAs_per_scan", "630")):
            app.ct_vars[key].set(str(p.get(key, defaults.get(key, default))))
        for key in ("manual_ksec_entered_by", "manual_ksec_reason", "manual_ksec_reference", "manual_ksec_last_updated"):
            if key in app.ct_vars: app.ct_vars[key].set(str(p.get(key, "")))
        app.ct_vars["scanner_source"].set(str(p.get("scanner_source", "")))
        app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set("" if p.get("ksec_mGy_per_100mAs_at_1m") in (None, "", "NULL", "null", "None") else str(p.get("ksec_mGy_per_100mAs_at_1m")))
        return True

    def prepare_geometry_source_params(self, source_type, existing_params, context):
        if existing_params:
            params = dict(existing_params)
        else:
            selected_type = str(context.get("selected_source_type", "") or "")
            selected_model = str(context.get("selected_model", "") or "")
            app = context.get("app")
            params = {}
            if selected_type == str(source_type or "") and selected_model and app is not None:
                resolution_context = app.ct_scanner_resolution_context
                vendor = ""
                try:
                    vendor = str(app._ct_scatter_vendor_values_for_source_type(self.spec.modality_id)[0] or "")
                except Exception:
                    vendor = ""

                selection = resolve_family_selection(
                    resolution_context,
                    source_type=str(source_type or ""),
                    vendor=vendor,
                    model=selected_model,
                    current_family="",
                )
                family = selection.scanner_family
                phantom = default_ct_phantom_for_family(resolution_context, family)
                try:
                    raw_family = raw_ct_family(resolution_context, family)
                    vendor = canonical_ct_vendor_label(
                        resolution_context,
                        raw_family.get("vendor", ""),
                    )
                except Exception:
                    pass
                display_model = friendly_ct_model_name(resolution_context, family)
                ksec, source_text = app._ct_source_ksec_per_100mAs(
                    source_type=str(source_type or ""),
                    scanner_family=family,
                    vendor=vendor,
                    model=display_model,
                    kvp=140,
                    phantom=phantom,
                )
                params = {
                    "preset": "ct_low_dose",
                    "use_scanner_db": "1",
                    "manual_ksec_override": "0",
                    "scanner_family": family,
                    "scanner_phantom": phantom,
                    "scanner_vendor": vendor,
                    "scanner_model": display_model,
                    "scanner_kvp": 140,
                    "scanner_source": source_text,
                    "scans_per_week": 60,
                    "ksec_mGy_per_100mAs_at_1m": ksec,
                    "workload_mAs_per_scan": 630,
                }
            if not params:
                params = self.default_source_params(source_type)

        params.setdefault("preset", "ct_low_dose")
        params.setdefault("use_scanner_db", "1")
        params.setdefault("manual_ksec_override", "0")
        params.setdefault("scans_per_week", 60)
        params.setdefault("workload_mAs_per_scan", 630)
        params.setdefault("scanner_kvp", 140)
        return params

    def finalise_source_form_params(self, app, source_type, params):
        from engine.normalization import normalize_source_params
        from tabs.source_ct_audit import inject_ct_audit_params

        defaults = self.default_source_params(source_type)
        clean = dict(params or {})
        scans = app._safe_float(
            clean.get("scans_per_week", defaults.get("scans_per_week", 60)),
            defaults.get("scans_per_week", 60),
        )
        workload = app._safe_float(
            clean.get("workload_mAs_per_scan", defaults.get("workload_mAs_per_scan", 630)),
            defaults.get("workload_mAs_per_scan", 630),
        )
        clean["scans_per_week"] = scans
        clean["workload_mAs_per_scan"] = workload
        clean = normalize_source_params(str(source_type or ""), clean)
        clean["scans_per_week"] = scans
        clean["workload_mAs_per_scan"] = workload
        return inject_ct_audit_params(app, clean)

    def live_preview_lines(self, app, source_type, source_name, radiation_type):
        from models.shielding_models import Source
        from engine.shielding_engine import compute_ct_source_summary
        from services.ct_scanner_resolution import metadata_for_ct_family

        params = self.collect_source_form_params(app, source_type) or {}
        ksec_raw = str(params.get("ksec_mGy_per_100mAs_at_1m", "") or "").strip()
        base = [
            "Inputs",
            "------",
            f"Scanner DB auto: {'yes' if str(params.get('use_scanner_db', '1')) == '1' else 'no'}",
            f"Scanner DB match: {params.get('scanner_vendor', '')} / {params.get('scanner_model', '')} @ {params.get('scanner_kvp', '')} kVp",
            f"CT scanner metadata: {metadata_for_ct_family(app.ct_scanner_resolution_context, str(params.get('scanner_family', '') or '')) or 'not specified'}",
            f"Resolved JSON family: {params.get('scanner_family', '') or 'none'}",
            f"Ksec source: {params.get('scanner_source', '')}",
        ]
        if ksec_raw in {"", "NULL", "null", "None", "none", "-"}:
            return tuple(base + [
                "Input Ksec: not available",
                f"Input workload: {int(round(float(params.get('workload_mAs_per_scan', 0) or 0)))} mAs/scan",
                f"Input scans/week: {int(round(float(params.get('scans_per_week', 0) or 0)))}",
                "", "Calculated", "----------",
                "BLOCKED: selected CT scanner has NULL/missing ksec.",
                "Add a documented manual ksec override in the Sources tab before calculation or certification.",
            ])
        summary = compute_ct_source_summary(
            Source(
                name=source_name,
                source_type=str(source_type or ""),
                radiation_type=radiation_type,
                params=params,
            )
        )
        return tuple(base + [
            f"Input Ksec: {summary['ksec_mGy_per_100mAs_at_1m']:.4f} mGy/100 mAs @ 1 m",
            f"Input workload: {int(round(summary['workload_mAs_per_scan']))} mAs/scan",
            f"Input scans/week: {int(round(summary['scans_per_week']))}",
            "", "Calculated", "----------",
            f"Weekly scatter dose: {summary['k1sec_mGy_per_week']:.4f} mGy/wk @ 1 m",
        ])

    def prepare_geometry_source_view(self, source_payloads, context):
        app = context.get("app")
        live_source_params = {}
        for key, var in (getattr(app, "ct_vars", {}) or {}).items():
            try:
                value = var.get()
            except Exception:
                continue
            if value not in (None, ""):
                live_source_params[key] = value

        merged_context = dict(context)
        merged_context["live_source_params"] = live_source_params
        return super().prepare_geometry_source_view(source_payloads, merged_context)


CT_PLUGIN = CTModalityPlugin(CT_MODALITY)
