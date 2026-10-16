"""Frozen Step 27 in-app Results presentation contract for production SPECT calculations.

This module is intentionally not imported by report/export/certification modules.
"""
from __future__ import annotations

from typing import Any

SPECT_RESULTS_PRESENTATION_CONTRACT_VERSION = 1
SPECT_RESULTS_PRESENTATION_BASELINE = "spect-production-results-v1"
SPECT_RESULTS_ROOM_HEADING = "SPECT Tc-99m production calculation results"
SPECT_RESULTS_NON_ISSUEABLE_NOTE = (
    "IN-APP RESULTS ONLY — SPECT PDF/report, export and certification generation remain blocked."
)
SPECT_RESULTS_ERROR_PREFIX = "SPECT Results unavailable"


def _fmt(value: Any, decimals: int = 3) -> str:
    if value in (None, ""):
        return "not reportable"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def spect_results_error_text(exc: Exception) -> str:
    return f"{SPECT_RESULTS_ERROR_PREFIX}: {exc}"


def spect_results_room_lines(room_name: str, rows: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    lines: list[tuple[str, str | None]] = [
        (SPECT_RESULTS_ROOM_HEADING, "result_heading"),
        (SPECT_RESULTS_NON_ISSUEABLE_NOTE, "result_review"),
        ("", None),
    ]
    for row in rows:
        status = str(row.get("compliance_status", "") or "").upper()
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        tag = "result_pass" if status == "PASS" else "result_fail" if status == "FAIL" else "result_review"
        lines.extend([
            (f"{symbol} {room_name} / {row.get('barrier_name', 'Barrier')} -> {status}", tag),
            (f"  Material: {row.get('material', '')}", None),
            (f"  Source-to-barrier distance: {_fmt(row.get('distance_m'))} m", None),
            (f"  Occupancy factor T: {_fmt(row.get('occupancy_factor'))}", None),
            (f"  Design goal: {_fmt(row.get('design_goal_uSv_per_week'))} µSv/week", None),
            (f"  Occupied weekly dose before shielding: {_fmt(row.get('occupied_unshielded_weekly_dose_uSv'))} µSv/week", None),
            (f"  Required transmission B: {_fmt(row.get('barrier_transmission_factor_B'), 6)}", None),
            (f"  Required shielding: {_fmt(row.get('required_thickness_mm'))} mm", None),
            (f"  Provided shielding: {_fmt(row.get('provided_thickness_mm'))} mm", None),
            (f"  Shielding margin: {_fmt(row.get('margin_mm'))} mm", None),
            (
                f"  Transmitted weekly dose: {_fmt(row.get('transmitted_dose_uSv_per_week'))}"
                + (" µSv/week" if row.get("transmitted_dose_uSv_per_week") is not None else ""),
                None,
            ),
            (f"  Step 25 production status: {status}", tag),
            (f"  Request SHA-256: {row.get('request_sha256', '')}", "muted"),
            (f"  Practical record: {row.get('practical_record_id', '')}", "muted"),
            (f"  Policy basis: {row.get('policy_decision_basis', '')}", "muted"),
            (f"  Calculation reasoning: {row.get('calculation_reasoning', '')}", "muted"),
            ("", None),
        ])
    return lines
