from __future__ import annotations

import re
from typing import Any


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


def fmt_delta(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return ""

    sign = "+" if numeric >= 0 else ""
    return f"{sign}{numeric:.2f} mm"


def fmt_material_with_mm(material: Any, value: Any) -> str:
    material_text = str(material or "").strip()
    mm_text = fmt_mm(value)

    if material_text and mm_text:
        return f"{material_text}: {mm_text}"

    if material_text:
        return material_text

    return mm_text


def canonical_source_label(value: Any) -> str:
    text = str(value or "").strip()

    if not text:
        return ""

    normalised = text.lower().replace("_", " ").replace("-", " ")
    normalised = " ".join(normalised.split())

    aliases = {
        "ct": "CT Secondary Scatter",
        "ct scatter": "CT Secondary Scatter",
        "ct secondary scatter": "CT Secondary Scatter",
        "secondary scatter": "CT Secondary Scatter",
        "nm": "NM Patient",
        "nuclear medicine": "NM Patient",
        "nm patient": "NM Patient",
        "patient": "NM Patient",
        "spect": "NM Patient",
        "spect ct": "NM Patient",
        "xray": "X-ray Primary",
        "x ray": "X-ray Primary",
        "x-ray": "X-ray Primary",
        "radiographic": "X-ray Primary",
    }

    return aliases.get(normalised, text)


def parse_source_contribution_parts(contributions: Any) -> list[tuple[str, float, str]]:
    text = str(contributions or "").strip()
    if not text:
        return []

    parsed: list[tuple[str, float, str]] = []

    for raw_part in text.split(";"):
        part = raw_part.strip()
        if not part:
            continue

        match = re.search(
            r"^(?P<label>.*?):\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>.*)$",
            part,
        )

        if not match:
            continue

        label = match.group("label").strip()
        value = float(match.group("value"))
        parsed.append((label, value, part))

    return parsed


def largest_contribution_label(contributions: Any) -> str:
    parsed = parse_source_contribution_parts(contributions)

    if not parsed:
        return ""

    label, _value, _raw = max(parsed, key=lambda item: item[1])
    return label


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


def dominant_source_text(room: Any, barrier: Any, live: dict[str, Any]) -> str:
    contributions = live.get("source_contributions", "")
    largest_label = largest_contribution_label(contributions)

    if largest_label:
        return canonical_source_label(largest_label)

    solver_used = str(live.get("solver_used", "") or "").strip()
    if solver_used:
        return "Auto-selected from solver path"

    return ""


def status_summary_text(status: Any) -> str:
    text = str(status or "").strip().upper()

    if text == "PASS":
        return "PASS (meets design goal)"

    if text == "REVIEW":
        return "REVIEW (requires physicist review)"

    if text == "FAIL":
        return "FAIL (exceeds design goal)"

    if text:
        return text

    return ""


def build_generation_summary_lines(*args: Any, **kwargs: Any) -> list[str]:
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


def result_block_header(room_name: Any, barrier_name: Any, status: Any = "") -> str:
    room_text = str(room_name or "").strip()
    barrier_text = str(barrier_name or "").strip()
    status_text = str(status or "").strip()

    if room_text and barrier_text and status_text:
        return f"{room_text} — {barrier_text} — {status_text}"

    if room_text and barrier_text:
        return f"{room_text} — {barrier_text}"

    if barrier_text:
        return barrier_text

    return room_text

def safe_float_or_none(value: Any):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


__all__ = [
    "build_generation_summary_lines",
    "canonical_source_label",
    "dominant_reason_text",
    "dominant_source_text",
    "fmt_delta",
    "fmt_material_with_mm",
    "fmt_mm",
    "largest_contribution_label",
    "parse_source_contribution_parts",
    "status_summary_text",
    "result_block_header",
    "safe_float_or_none",
]
