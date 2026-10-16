"""Frozen normal-Results presentation contract for persisted PET calculations.

This module governs only the in-app Results presentation.  It is intentionally
not imported by report, export, certification, or payload-generation modules.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

PET_RESULTS_PRESENTATION_CONTRACT_VERSION = 1
PET_RESULTS_PRESENTATION_BASELINE = "pet-normal-results-v1"

PET_RESULTS_ROOM_HEADING = "PET patient-source shielding results"
PET_RESULTS_NON_ISSUEABLE_NOTE = (
    "IN-APP RESULTS ONLY — PET report, export and certification generation remain blocked."
)
PET_RESULTS_ASSUMPTION_NOTE = (
    "Single PET patient/source position per room; all exposure periods occur at that position. "
    "Physical decay is integrated by phase, followed by inverse-square distance scaling, "
    "occupancy and approved 511 keV attenuation."
)
PET_RESULTS_ERROR_PREFIX = "PET Results unavailable"
PET_RESULTS_RISK_ERROR_PREFIX = "PET barrier risk unavailable"

PET_RESULTS_FIELD_ORDER = (
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
    "unshielded_weekly_dose_uSv",
    "occupied_unshielded_weekly_dose_uSv",
    "barrier_transmission_factor_B",
    "required_tvl_count",
    "required_thickness_mm",
    "provided_thickness_mm",
    "margin_mm",
    "transmitted_dose_uSv_per_week",
    "compliance_status",
)

PET_RESULTS_FIELD_LABELS = {
    "distance_m": "Source-to-barrier distance",
    "occupancy_factor": "Occupancy factor T",
    "design_goal_uSv_per_week": "Design goal",
    "unshielded_weekly_dose_uSv": "Unshielded weekly dose at barrier",
    "occupied_unshielded_weekly_dose_uSv": "Occupied weekly dose before shielding",
    "barrier_transmission_factor_B": "Required transmission B",
    "required_tvl_count": "Required attenuation",
    "required_thickness_mm": "Required shielding",
    "provided_thickness_mm": "Provided shielding",
    "margin_mm": "Shielding margin",
    "transmitted_dose_uSv_per_week": "Transmitted weekly dose",
    "compliance_status": "Compliance status",
}

PET_RESULTS_FIELD_UNITS = {
    "distance_m": "m",
    "occupancy_factor": "",
    "design_goal_uSv_per_week": "µSv/week",
    "unshielded_weekly_dose_uSv": "µSv/week",
    "occupied_unshielded_weekly_dose_uSv": "µSv/week",
    "barrier_transmission_factor_B": "",
    "required_tvl_count": "TVL",
    "required_thickness_mm": "mm",
    "provided_thickness_mm": "mm",
    "margin_mm": "mm",
    "transmitted_dose_uSv_per_week": "µSv/week",
    "compliance_status": "",
}

PET_RESULTS_PROVENANCE_ORDER = (
    "provenance_manifest_id",
    "provenance_manifest_revision",
    "radionuclide_dataset_id",
    "radionuclide_dataset_revision",
    "radionuclide_records_sha256",
    "attenuation_dataset_id",
    "attenuation_dataset_revision",
    "attenuation_records_sha256",
    "physics_contract_version",
    "solver_contract_version",
    "replay_verified",
)

PET_RESULTS_PROVENANCE_LABELS = {
    "provenance_manifest_id": "Provenance manifest",
    "provenance_manifest_revision": "Manifest revision",
    "radionuclide_dataset_id": "Radionuclide dataset",
    "radionuclide_dataset_revision": "Radionuclide revision",
    "radionuclide_records_sha256": "Radionuclide records SHA-256",
    "attenuation_dataset_id": "Attenuation dataset",
    "attenuation_dataset_revision": "Attenuation revision",
    "attenuation_records_sha256": "Attenuation records SHA-256",
    "physics_contract_version": "PET physics contract",
    "solver_contract_version": "PET solver contract",
    "replay_verified": "Deterministic replay verified",
}


def _number(value: Any, decimals: int) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "unavailable"


def format_pet_results_field(key: str, value: Any) -> str:
    if key == "distance_m":
        rendered = _number(value, 3)
    elif key == "occupancy_factor":
        rendered = _number(value, 3)
    elif key in {"design_goal_uSv_per_week", "unshielded_weekly_dose_uSv", "occupied_unshielded_weekly_dose_uSv", "transmitted_dose_uSv_per_week"}:
        rendered = _number(value, 3)
    elif key == "barrier_transmission_factor_B":
        rendered = _number(value, 6)
    elif key == "required_tvl_count":
        rendered = _number(value, 3)
    elif key in {"required_thickness_mm", "provided_thickness_mm", "margin_mm"}:
        rendered = _number(value, 3)
    else:
        rendered = str(value or "").strip() or "unavailable"
    unit = PET_RESULTS_FIELD_UNITS.get(key, "")
    return f"{rendered} {unit}".rstrip()


def pet_results_error_text(exc: BaseException) -> str:
    detail = str(exc or "").strip() or exc.__class__.__name__
    return f"{PET_RESULTS_ERROR_PREFIX}: {detail}"


def pet_results_risk_error_text(exc: BaseException) -> str:
    detail = str(exc or "").strip() or exc.__class__.__name__
    return f"{PET_RESULTS_RISK_ERROR_PREFIX}: {detail}"


def pet_results_room_lines(room_name: str, rows: Iterable[Dict[str, Any]]) -> List[Tuple[str, str | None]]:
    rows = list(rows)
    lines: List[Tuple[str, str | None]] = [
        (f"{room_name} — {PET_RESULTS_ROOM_HEADING}", "result_heading"),
        (PET_RESULTS_NON_ISSUEABLE_NOTE, "result_review"),
        (PET_RESULTS_ASSUMPTION_NOTE, "muted"),
        ("", None),
    ]
    if not rows:
        lines.append((f"{PET_RESULTS_ERROR_PREFIX}: no canonical barrier rows were returned.", "result_fail"))
        return lines

    first = rows[0]
    lines.append(("  Frozen provenance", "muted"))
    for key in PET_RESULTS_PROVENANCE_ORDER:
        value = first.get(key, "")
        if key == "replay_verified":
            value = "yes" if value is True else "no"
        lines.append((f"  {PET_RESULTS_PROVENANCE_LABELS[key]}: {value}", "muted"))
    lines.append(("", None))

    for row in rows:
        barrier_name = str(row.get("barrier_name", "Barrier") or "Barrier")
        status = str(row.get("compliance_status", "") or "").upper()
        tag = "result_pass" if status == "PASS" else "result_fail" if status == "FAIL" else "result_review"
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        lines.append((f"{symbol} {room_name} / {barrier_name} -> {status or 'ERROR'}", tag))
        for key in PET_RESULTS_FIELD_ORDER:
            lines.append((f"  {PET_RESULTS_FIELD_LABELS[key]}: {format_pet_results_field(key, row.get(key))}", tag if key == "compliance_status" else None))
        reasoning = str(row.get("calculation_reasoning", "") or "").strip()
        if reasoning:
            lines.append((f"  Calculation reasoning: {reasoning}", "muted"))
        lines.append(("", None))
    return lines
