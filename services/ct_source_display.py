from __future__ import annotations

"""
Human-readable CT source display state.

This module is intentionally UI-toolkit independent. It centralises the display
strings used by Geometry, Sources, Results/Barriers and report/export code so
scanner/ksec wording does not drift between tabs.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from modalities.registry import source_form_kind_for_type
from services.ksec_status import resolve_ksec_status_from_params


@dataclass(frozen=True)
class CTSourceDisplayState:
    is_ct_scatter: bool
    scanner_family: str
    scanner_vendor: str
    scanner_model: str
    scanner_label: str
    ksec_display: str
    ksec_energy_display: str
    ksec_status_display: str
    scanner_debug_display: str
    energy_basis_display: str
    basis: str
    status: str
    requires_manual_override: bool
    is_manual_override: bool
    audit_complete: bool


def build_ct_source_display_state(
    source_type: Any,
    params: Mapping[str, Any] | None,
    *,
    fallback_energy_kvp: Any = "",
) -> CTSourceDisplayState:
    p = dict(params or {})
    source_type_text = _text(source_type)
    is_ct = source_form_kind_for_type(source_type_text) == "ct_ksec"

    scanner_family = _text(p.get("scanner_family"))
    scanner_vendor = _text(p.get("scanner_vendor"))
    scanner_model = _text(p.get("scanner_model"))
    scanner_label = _first_nonempty(scanner_model, scanner_family, "CT scanner")

    energy_value = _first_nonempty(
        p.get("ksec_energy_kvp"),
        p.get("scanner_kvp"),
        fallback_energy_kvp,
    )
    ksec_energy_display = format_ksec_energy(energy_value)

    status = resolve_ksec_status_from_params(source_type_text, p).as_dict()
    basis = _text(status.get("basis"))
    ksec_display = _text(status.get("ksec_display"))

    if basis == "manual_override" and ksec_display:
        ksec_display = f"{ksec_display}\nmanual override"
    elif basis == "manual_override_required":
        ksec_display = "NULL — manual override\nrequired"

    source_text = _text(
        status.get("source_text")
        or p.get("scanner_source")
        or p.get("ksec_source")
    )

    ksec_status_display = source_text
    if not ksec_status_display:
        if basis == "database":
            ksec_status_display = "Database ksec"
        elif basis == "manual_override":
            ksec_status_display = "Manual ksec override"
        elif basis == "manual_override_required":
            ksec_status_display = "NULL ksec — manual override required"

    if basis == "database" and ksec_energy_display and "kvp" not in ksec_status_display.lower():
        ksec_status_display = f"{ksec_status_display} @ {ksec_energy_display}"

    scanner_debug_display = " | ".join(
        part for part in (scanner_vendor, scanner_model, scanner_family) if part
    )

    if is_ct:
        if ksec_energy_display:
            energy_basis_display = f"CT ksec energy basis: {ksec_energy_display}"
        else:
            energy_basis_display = "CT source ksec energy / scanner kVp"
    else:
        energy_basis_display = ""

    return CTSourceDisplayState(
        is_ct_scatter=is_ct,
        scanner_family=scanner_family,
        scanner_vendor=scanner_vendor,
        scanner_model=scanner_model,
        scanner_label=scanner_label,
        ksec_display=ksec_display,
        ksec_energy_display=ksec_energy_display or "not specified",
        ksec_status_display=ksec_status_display,
        scanner_debug_display=scanner_debug_display,
        energy_basis_display=energy_basis_display,
        basis=basis,
        status=_text(status.get("status")),
        requires_manual_override=(basis == "manual_override_required"),
        is_manual_override=(basis == "manual_override"),
        audit_complete=bool(status.get("audit_complete")),
    )


def build_ct_source_display_state_from_source(
    src: Any,
    *,
    fallback_energy_kvp: Any = "",
) -> CTSourceDisplayState:
    return build_ct_source_display_state(
        getattr(src, "source_type", ""),
        getattr(src, "params", {}) or {},
        fallback_energy_kvp=fallback_energy_kvp,
    )


def format_ksec_energy(value: Any) -> str:
    raw = _text(value)
    if raw in {"", "NULL", "null", "None", "none", "nan", "NaN"}:
        return ""

    if raw.lower().endswith("kvp"):
        raw = raw[:-3].strip()

    try:
        return f"{float(raw):g} kVp"
    except Exception:
        return f"{raw} kVp" if raw else ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""
