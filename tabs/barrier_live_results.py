from __future__ import annotations

from typing import Any, Dict

from engine.shielding_engine import calc_barrier_result
from models.shielding_models import Barrier, Room
from tabs.results_tab_text import dominant_source_text

ERROR_RESULT: Dict[str, Any] = {
    "unshielded_weekly_dose_uSv": "",
    "linear_attenuation_coefficient_cm_inv": "",
    "barrier_transmission_factor_B": "",
    "required_lead_mm": "",
    "required_concrete_mm": "",
    "recommended_commercial_lead_mm": "",
    "compliance_status": "ERROR",
    "margin_mm": "",
    "notes": "",
}


def _first_display_value(*values) -> object:
    for value in values:
        if value not in (None, "", "-"):
            return value
    return ""


def display_required_thickness_mm(live: dict) -> object:
    material = str(live.get("material", "") or "").strip().lower()

    if "concrete" in material:
        return _first_display_value(
            live.get("required_concrete_mm"),
            live.get("required_thickness_mm"),
        )

    return _first_display_value(
        live.get("required_lead_mm"),
        live.get("required_thickness_mm"),
    )


def display_recommended_thickness_mm(live: dict) -> object:
    material = str(live.get("material", "") or "").strip().lower()

    if "concrete" in material:
        return _first_display_value(
            live.get("recommended_concrete_mm"),
            live.get("required_concrete_mm"),
            live.get("required_thickness_mm"),
        )

    return _first_display_value(
        live.get("recommended_commercial_lead_mm"),
        live.get("required_lead_mm"),
        live.get("required_thickness_mm"),
    )


def get_barrier_live_result(app, room: Room, barrier: Barrier) -> Dict[str, Any]:
    """Return the live calculated result for a single barrier.

    This is a display/helper boundary used by live tables and overlays. It
    intentionally catches calculation exceptions and returns the same ERROR
    payload shape app.py previously returned.
    """
    try:
        live = calc_barrier_result(
            room,
            barrier,
            app.project,
            app.global_energy_var.get(),
        )

        live["material"] = getattr(barrier, "material", "")
        live["display_required_thickness_mm"] = display_required_thickness_mm(live)
        live["display_recommended_thickness_mm"] = display_recommended_thickness_mm(live)

        return live
    except Exception:
        live = dict(ERROR_RESULT)
        live["material"] = getattr(barrier, "material", "")
        live["display_required_thickness_mm"] = ""
        live["display_recommended_thickness_mm"] = ""
        return live


def dominant_source_for_barrier(app, barrier_name: str) -> str:
    """Resolve the dominant source/component for a barrier from live room results."""
    for room in getattr(app.project, "rooms", []) or []:
        try:
            room_results = app.get_room_barrier_results(room)
        except Exception:
            continue

        for barrier, live in zip(getattr(room, "barriers", []) or [], room_results):
            if str(getattr(barrier, "name", "") or "").strip() == str(barrier_name or "").strip():
                return dominant_source_text(room, barrier, live)

    return ""
