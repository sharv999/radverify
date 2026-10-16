from __future__ import annotations


def classify_barrier_visual_state(status: str) -> str:
    text = str(status or "").strip().upper()

    if text == "PASS":
        return "PASS"

    if text == "REVIEW":
        return "REVIEW"

    if text == "FAIL":
        return "FAIL"

    return text or "UNKNOWN"


def barrier_heatmap_color(status: str) -> str:
    state = classify_barrier_visual_state(status)

    if state == "PASS":
        return "#2e7d32"

    if state == "REVIEW":
        return "#d49a00"

    if state == "FAIL":
        return "#c62828"

    return ""