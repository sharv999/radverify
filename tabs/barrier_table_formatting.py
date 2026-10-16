from __future__ import annotations

from typing import Any, Mapping


def _number(value: Any, decimals: int, *, trim: bool = False, min_decimals: int = 0) -> str:
    """Format a numeric barrier-table value without changing calculation precision."""
    if value in (None, ""):
        return ""
    try:
        text = f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)

    if trim and "." in text:
        integer, fraction = text.split(".", 1)
        fraction = fraction.rstrip("0")
        if len(fraction) < min_decimals:
            fraction += "0" * (min_decimals - len(fraction))
        return integer if not fraction else f"{integer}.{fraction}"
    return text


def format_barrier_table_cell(row: Mapping[str, Any], column: str) -> str:
    """Return the common CT-style display precision for a Barriers table cell.

    This is presentation-only. Canonical PET/SPECT/CT result payloads retain
    their full-precision numeric values.
    """
    value = row.get(column, "")
    if column == "compliance_status":
        value = row.get("compliance_status") or row.get("status") or ""
    if value in (None, ""):
        return ""

    material = str(row.get("material", "") or "").strip().lower()

    if column == "thickness_mm":
        # CT convention: commercial Pb is normally shown to hundredths while
        # construction thicknesses such as concrete retain one decimal place.
        if "concrete" in material:
            return _number(value, 1)
        return _number(value, 3, trim=True)

    if column == "occupancy_factor":
        # Preserve clinically meaningful small occupancy factors in the
        # presentation layer (e.g. 0.05, 0.025) instead of rounding them to
        # one decimal place. Keep at least one decimal for values such as 1.0.
        return _number(value, 3, trim=True, min_decimals=1)

    if column in {"distance_m", "design_goal_uSv_per_week"}:
        return _number(value, 1)

    if column in {"unshielded_weekly_dose_uSv", "transmitted_dose_uSv_per_week"}:
        return _number(value, 2, trim=True, min_decimals=1)

    if column == "barrier_transmission_factor_B":
        return _number(value, 6, trim=True)

    if column in {"display_required_thickness_mm", "display_recommended_thickness_mm"}:
        return _number(value, 3, trim=True)

    if column == "linear_attenuation_coefficient_cm_inv":
        return _number(value, 2, trim=True, min_decimals=1)

    return str(value)
