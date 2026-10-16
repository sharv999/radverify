from __future__ import annotations
from typing import Any

# Paste the existing implementations from tabs/results_tab_text.py here.
# Keep this file free of tkinter, customtkinter, app, and tabs imports.

def parse_source_contribution_parts(contributions: Any) -> list[tuple[str, Optional[float], str]]:
    """
    Parse:
        'CT Secondary Scatter: 362.99 uSv/wk; NM Patient: 496.94 uSv/wk'
    into:
        [(label, numeric_value, original_part), ...]
    """
    parsed = []
    for part in [p.strip() for p in str(contributions or "").split(";") if p.strip()]:
        label, _, rhs = part.partition(":")
        label = label.strip()
        value = None

        if rhs:
            token = rhs.strip().split()[0]
            try:
                value = float(token.replace(",", ""))
            except Exception:
                value = None

        parsed.append((label, value, part))
    return parsed


def largest_contribution_label(contributions: Any) -> str:
    parsed = parse_source_contribution_parts(contributions)
    numeric = [(label, value, original) for label, value, original in parsed if value is not None]
    if not numeric:
        return ""

    label, _, _ = max(numeric, key=lambda x: x[1])
    return label.strip()


def dominant_source_text(room: Room, barrier: Barrier, live: Dict[str, Any]) -> str:
    contributions = live.get("source_contributions", "")
    largest_label = largest_contribution_label(contributions)
    if largest_label:
        return canonical_source_label(largest_label)

    dominant = str(live.get("dominant_component", "") or "").strip()
    solver_used = str(live.get("solver_used", "") or "").strip()
    ct_solver = str(live.get("ct_solver_used", "") or "").strip()
    role = str(getattr(barrier, "barrier_role", "") or "").strip()

    if dominant:
        key = dominant.lower()
        if key in {"ct", "ct_scatter", "ct secondary scatter"}:
            return "CT Secondary Scatter"
        if key in {"nm", "nm_patient", "spect", "spect patient"}:
            return "NM Patient"
        if key in {"primary", "xray_primary", "primary_xray"}:
            return "X-ray Primary"
        if key in {"secondary", "scatter", "leakage"}:
            return "Secondary / Scatter"
        return dominant

    if ct_solver:
        return "CT Secondary Scatter"
    if "ncrp" in solver_used.lower():
        if role.startswith("primary_"):
            return "X-ray Primary"
        return "Secondary / Scatter"

    return "Auto-selected from solver path"


def dominant_reason_text(contributions: Any) -> str:
    parsed = parse_source_contribution_parts(contributions)

    if not parsed:
        return ""

    ordered = sorted(parsed, key=lambda item: item[1], reverse=True)
    top_label, top_value, _top_raw = ordered[0]

    if len(ordered) > 1:
        second_label, second_value, _second_raw = ordered[1]

        if top_value > 0 and second_value / top_value >= 0.9:
            return (
                f"Near-equal contribution to {canonical_source_label(top_label)} "
                f"from {canonical_source_label(second_label)}."
            )

        return (
            f"Higher weekly dose contribution from "
            f"{canonical_source_label(top_label)}."
        )

    return f"Higher weekly dose contribution from {canonical_source_label(top_label)}."


def build_generation_summary_lines(*args, **kwargs) -> list[str]:
    """
    Compatibility helper used by Results tab/report text tests.

    Returns simple text lines describing report/payload generation state.
    Kept here so tabs.results_tab_text can remain a non-UI wrapper.
    """
    lines: list[str] = []

    for arg in args:
        if arg in (None, "", [], {}):
            continue
        if isinstance(arg, (list, tuple)):
            lines.extend(str(item) for item in arg if item not in (None, ""))
        else:
            lines.append(str(arg))

    for key, value in kwargs.items():
        if value in (None, "", [], {}):
            continue
        lines.append(f"{key}: {value}")

    return lines



def canonical_source_label(value) -> str:
    """
    Normalise source labels for report/results text.

    Kept here so tabs.results_tab_text can remain a compatibility wrapper.
    """
    text = str(value or "").strip()

    if not text:
        return ""

    lower = text.lower().replace("_", " ").replace("-", " ")
    lower = " ".join(lower.split())

    aliases = {
        "ct": "CT",
        "ct scatter": "CT scatter",
        "ct secondary scatter": "CT scatter",
        "secondary scatter": "CT scatter",
        "spect": "SPECT",
        "spect ct": "SPECT/CT",
        "nm": "Nuclear medicine",
        "nm patient": "NM patient",
        "patient": "Patient",
        "xray": "X-ray",
        "x ray": "X-ray",
        "radiographic": "X-ray",
    }

    return aliases.get(lower, text)

def fmt_delta(value) -> str:
    try:
        numeric = float(value)
    except Exception:
        return ""

    sign = "+" if numeric >= 0 else ""
    return f"{sign}{numeric:.2f} mm"


def fmt_mm(value: Any, decimals: int = 2) -> str:
    try:
        numeric = float(value)
    except Exception:
        return ""

    try:
        places = int(decimals)
    except Exception:
        places = 2

    return f"{numeric:.{places}f} mm"


def status_summary_text(pass_count=0, review_count=0, fail_count=0) -> str:
    try:
        p = int(pass_count or 0)
    except Exception:
        p = 0

    try:
        r = int(review_count or 0)
    except Exception:
        r = 0

    try:
        f = int(fail_count or 0)
    except Exception:
        f = 0

    parts = [f"{p} PASS"]

    if r:
        parts.append(f"{r} REVIEW")

    if f:
        parts.append(f"{f} FAIL")

    return ", ".join(parts)

def fmt_material_with_mm(material: Any, value: Any) -> str:
    material_text = str(material or "").strip()
    mm_text = fmt_mm(value)

    if material_text and mm_text:
        return f"{material_text}: {mm_text}"

    if material_text:
        return material_text

    return mm_text

def safe_float_or_none(value: Any):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None