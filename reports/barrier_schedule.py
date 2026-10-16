from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from reports.results_text import (
    dominant_reason_text,
    dominant_source_text,
)
from reports.solver_reasoning_text import solver_reasoning_text
from services.opening_physics import (
    opening_display_material,
    opening_live_result,
    opening_parent_barrier,
    opening_type_normalized,
)



def build_canonical_barrier_schedule_payload(
    app: Any,
    room: Any,
    room_results: Optional[Iterable[Dict[str, Any]]] = None,
    risk_by_name: Optional[Dict[str, Any]] = None,
    allow_generic_fallback: bool = True,
) -> List[Dict[str, Any]]:
    """Return the single canonical barrier schedule used by UI and PDF.

    The rows contain both the Barriers-tab columns and the report/export fields.
    This keeps the visible table and generated PDF on the same payload instead
    of maintaining separate wall/opening row builders.
    """
    room_results_list = list(room_results or [])
    if not room_results_list:
        if not allow_generic_fallback:
            raise ValueError("Canonical PET/SPECT report schedule requires supplied modality Results; generic recalculation is disabled.")
        try:
            room_results_list = list(app.get_room_barrier_results(room) or [])
        except Exception:
            room_results_list = []

    risk_by_name = risk_by_name or {}
    rows: List[Dict[str, Any]] = []

    # XR-20C: modality Results may contain finite sub-barriers (for example the
    # Chest Bucky Shield) in addition to persisted structural barriers. Match
    # structural rows by name rather than positional index so an inserted
    # sub-barrier cannot shift every following wall onto the wrong Result.
    live_by_name = {
        str(item.get("barrier") or item.get("barrier_name") or item.get("name") or "").strip(): item
        for item in room_results_list
        if isinstance(item, dict) and not bool(item.get("sub_barrier", False))
    }

    for idx, barrier in enumerate(list(getattr(room, "barriers", []) or [])):
        barrier_name = str(getattr(barrier, "name", "") or "").strip()
        live = live_by_name.get(barrier_name, {})
        if not live and idx < len(room_results_list) and isinstance(room_results_list[idx], dict):
            live = room_results_list[idx]
        if not live:
            if not allow_generic_fallback:
                raise ValueError(f"Missing supplied modality Result for barrier {getattr(barrier, 'name', idx)!r}; generic recalculation is disabled.")
            try:
                from engine.shielding_engine import calc_barrier_result
                live = calc_barrier_result(
                    room,
                    barrier,
                    app.project,
                    app.global_energy_var.get(),
                    solver_mode=app.solver_mode_var.get(),
                )
            except Exception as exc:
                live = {"compliance_status": "ERROR", "notes": f"Barrier calculation failed: {exc}"}
        rows.append(_canonical_row_from_barrier(app, room, barrier, live, risk_by_name=risk_by_name))

    # XR-20C: append finite Bucky Shield regions as first-class canonical
    # schedule rows. They are not persisted room.barriers because they are
    # geometry-owned sub-barriers, but Results/PDF must expose their distinct
    # dose and compliance state.
    barriers_by_name = {str(getattr(b, "name", "") or "").strip(): b for b in list(getattr(room, "barriers", []) or [])}
    for live in room_results_list:
        if not isinstance(live, dict) or not bool(live.get("sub_barrier", False)):
            continue
        if str(live.get("barrier_role", "") or "") != "fig52_chest_bucky_subbarrier":
            continue
        parent_name = str(live.get("parent_barrier", "") or "").strip()
        parent = barriers_by_name.get(parent_name)
        if parent is None:
            continue
        rows.append(_canonical_row_from_bucky_shield(app, room, parent, live))

    geom = getattr(room, "geometry", None)
    openings = list(getattr(geom, "openings", []) or []) if geom else []
    if openings and not allow_generic_fallback:
        raise ValueError("PET/SPECT report openings require validated modality Results; generic opening recalculation is disabled.")
    for opening_index, opening in enumerate(openings, start=1):
        try:
            opening_barrier, live = opening_live_result(app, room, opening, opening_index)
        except Exception as exc:
            opening_barrier, live = None, {"compliance_status": "ERROR", "notes": f"Opening calculation failed: {exc}"}

        if opening_barrier is None:
            continue

        rows.append(_canonical_row_from_opening(app, room, opening, opening_barrier, live, opening_index))

    return rows



def _canonical_row_from_barrier(
    app: Any,
    room: Any,
    barrier: Any,
    live: Dict[str, Any],
    *,
    risk_by_name: Dict[str, Any],
) -> Dict[str, Any]:
    live = dict(live or {})
    name = str(getattr(barrier, "name", "") or "")
    material = str(getattr(barrier, "material", "") or "").strip()
    live["material"] = material
    live["display_required_thickness_mm"] = _display_required_thickness_mm(live)
    live["display_recommended_thickness_mm"] = _display_recommended_thickness_mm(live)
    status = _user_facing_status(app, name, live)
    risk_obj = risk_by_name.get(name)
    dominant_source = dominant_source_text(room, barrier, live)
    row = _base_row_from_live(app, barrier, live, status=status)
    row.update({
        "barrier_id": name,
        "name": name,
        "barrier_element_type": "Wall",
        "parent_barrier": "",
        "construction_note": "",
        "qa_issues": "",
        "adjacent_area": str(getattr(barrier, "adjacent_area", "") or ""),
        "barrier_role": str(getattr(barrier, "barrier_role", "") or ""),
        "material": material,
        "dominant_source": dominant_source,
        "dominant_reason": dominant_reason_text(live.get("source_contributions", "")),
        "solver_reasoning": solver_reasoning_text(room, barrier, live),
        "risk_visual_state": str(getattr(risk_obj, "visual_state", status) or status),
        "risk_colour": str(getattr(risk_obj, "colour", "") or ""),
        "risk_confidence": getattr(risk_obj, "confidence", row.get("confidence")),
        "primary_issue": str(getattr(risk_obj, "primary_issue", "") or ""),
    })
    return row


def _canonical_row_from_bucky_shield(
    app: Any,
    room: Any,
    parent_barrier: Any,
    live: Dict[str, Any],
) -> Dict[str, Any]:
    """Canonical schedule row for the finite 1.2 m Chest Bucky Shield region."""
    live = dict(live or {})
    parent_name = str(getattr(parent_barrier, "name", "") or "").strip()
    name = f"{parent_name.replace(' wall', '')} Bucky shield" if parent_name else "Bucky shield"
    status = str(live.get("compliance_status") or "").strip().upper() or "PASS"

    # The row represents the additional fixed shield itself. T/P, distance and
    # dose are inherited from the parent-wall sub-barrier calculation. Required
    # structural thickness remains available in provenance but is intentionally
    # not presented as a required thickness for the fixed 2.20 mm shield.
    row = _base_row_from_live(app, parent_barrier, live, status=status)
    row.update({
        "barrier_id": name,
        "name": name,
        "barrier_element_type": "bucky_shield",
        "parent_barrier": parent_name,
        "barrier_role": "fig52_chest_bucky_subbarrier",
        "material": "Pb (additional)",
        "thickness_mm": 2.2,
        "provided_thickness_mm": 2.2,
        "distance_m": _float_or_none(live.get("distance_m")),
        "occupancy_factor": _float_or_none(live.get("occupancy_factor")),
        "design_goal_uSv_per_week": _float_or_none(live.get("design_goal_uSv_per_week")),
        "display_required_thickness_mm": "",
        "display_recommended_thickness_mm": "",
        "adjacent_area": str(getattr(parent_barrier, "adjacent_area", "") or ""),
        "dominant_source": str(live.get("dominant_source_name", "") or "Chest Bucky primary"),
        "dominant_reason": dominant_reason_text(live.get("source_contributions", "")),
        "solver_reasoning": "Finite 1.2 m Chest Bucky sub-barrier: parent structural wall plus fixed additional 2.20 mm Pb Bucky Shield.",
        "construction_note": f"1.2 m region of {parent_name}: structural wall plus additional Pb 2.20 mm Bucky Shield",
        "qa_issues": "",
        "risk_visual_state": status,
        "risk_colour": "",
        "risk_confidence": row.get("confidence"),
        "primary_issue": "",
        "compliance_status": status,
        "status": status,
        "status_text": _status_text(status),
    })
    return row


def _canonical_row_from_opening(
    app: Any,
    room: Any,
    opening: Any,
    opening_barrier: Any,
    live: Dict[str, Any],
    opening_index: int,
) -> Dict[str, Any]:
    live = dict(live or {})
    name = str(getattr(opening_barrier, "name", "") or "").strip()
    otype = opening_type_normalized(opening)
    element = "viewing_panel" if otype == "viewing_panel" else "door"
    parent = opening_parent_barrier(room, opening)
    parent_name = str(getattr(parent, "name", "") or getattr(opening_barrier, "adjacent_area", "") or "").strip()
    display_material = opening_display_material(opening)
    live["material"] = display_material
    live["display_required_thickness_mm"] = _display_required_thickness_mm(live)
    live["display_recommended_thickness_mm"] = _display_recommended_thickness_mm(live)
    status = _user_facing_status(app, name, live)
    row = _base_row_from_live(app, opening_barrier, live, status=status)
    row.update({
        "barrier_id": name,
        "name": name,
        "barrier_element_type": element,
        "parent_barrier": parent_name,
        "adjacent_area": str(getattr(opening_barrier, "adjacent_area", "") or parent_name),
        "barrier_role": str(getattr(opening_barrier, "barrier_role", "") or element),
        "material": display_material,
        "dominant_source": "Secondary / Scatter",
        "dominant_reason": "",
        "solver_reasoning": f"Opening/sub-barrier {name} calculated from Geometry using the canonical barrier schedule payload.",
        "construction_note": f"{element.replace('_', ' ').title()} in {parent_name}" if parent_name else element.replace("_", " ").title(),
        "qa_issues": "",
        "risk_visual_state": status,
        "risk_colour": "",
        "risk_confidence": row.get("confidence"),
        "primary_issue": "",
    })
    return row


def _base_row_from_live(app: Any, barrier: Any, live: Dict[str, Any], *, status: str) -> Dict[str, Any]:
    name = str(getattr(barrier, "name", "") or "")
    confidence = _row_confidence(app, name, live)
    margin_mm = _float_or_none(live.get("margin_mm"))
    try:
        shortfall = abs(float(margin_mm)) if margin_mm is not None and margin_mm < 0 else 0.0
    except Exception:
        shortfall = 0.0

    return {
        "name": name,
        "material": str(live.get("material", getattr(barrier, "material", "")) or ""),
        "thickness_mm": _float_or_none(getattr(barrier, "thickness_mm", None)),
        "provided_thickness_mm": _float_or_none(getattr(barrier, "thickness_mm", None)),
        "barrier_role": str(getattr(barrier, "barrier_role", "") or ""),
        "distance_m": _float_or_none(getattr(barrier, "distance_m", None)),
        "occupancy_factor": _float_or_none(getattr(barrier, "occupancy_factor", None)),
        "design_goal_uSv_per_week": _float_or_none(getattr(barrier, "design_goal_uSv_per_week", None)),
        "unshielded_weekly_dose_uSv": _float_or_none(live.get("unshielded_weekly_dose_uSv")),
        "transmitted_dose_uSv_per_week": _first_exposed_transmitted_dose(live),
        "barrier_transmission_factor_B": _float_or_none(live.get("barrier_transmission_factor_B")),
        "required_lead_mm": _float_or_none(live.get("required_lead_mm")),
        "required_concrete_mm": _float_or_none(live.get("required_concrete_mm")),
        "required_thickness_mm": _float_or_none(live.get("required_thickness_mm")),
        "recommended_commercial_lead_mm": _float_or_none(live.get("recommended_commercial_lead_mm")),
        "recommended_concrete_mm": _float_or_none(live.get("recommended_concrete_mm")),
        "display_required_thickness_mm": live.get("display_required_thickness_mm", ""),
        "display_recommended_thickness_mm": live.get("display_recommended_thickness_mm", ""),
        "linear_attenuation_coefficient_cm_inv": live.get("linear_attenuation_coefficient_cm_inv", ""),
        "solver_used": str(live.get("solver_used") or live.get("solver_mode") or ""),
        "ct_solver_used": str(live.get("ct_solver_used", "") or ""),
        "compliance_status": status,
        "status": status,
        "status_text": _status_text(status),
        "confidence": confidence,
        "mm_shortfall": round(shortfall, 3),
        "margin_mm": margin_mm,
        "source_contributions": str(live.get("source_contributions", "") or ""),
        "notes": str(live.get("notes", "") or "").strip(),
        # XR-15C: preserve Fig. 5.2 provenance through Results -> report/PDF.
        "results_source": str(live.get("results_source", "") or ""),
        "results_model_version": str(live.get("results_model_version", "") or ""),
        "fig52_section": str(live.get("fig52_section", "") or ""),
        "fig52_combination": str(live.get("fig52_combination", "") or ""),
        "fig52_components": live.get("fig52_components", []),
        "fig52": live.get("fig52", {}),
        # XR-19C: carry Chest Bucky Shield primary attenuation provenance through
        # the same canonical Results -> report adapter used for Control Wall credit.
        "bucky_shield_attenuation_applied": bool(live.get("bucky_shield_attenuation_applied", False)),
        "bucky_shield_primary_transmission": _float_or_none(live.get("bucky_shield_primary_transmission")),
        "bucky_shield_material": str(live.get("bucky_shield_material", "") or ""),
        "bucky_shield_thickness_mm": _float_or_none(live.get("bucky_shield_thickness_mm")),
        "bucky_shield_provenance": str(live.get("bucky_shield_provenance", "") or ""),
        # XR-17C intervening Control Wall provenance is carried unchanged into
        # the canonical Results/report payload.
        "control_wall_attenuation_applied": bool(live.get("control_wall_attenuation_applied", False)),
        "control_wall_secondary_transmission": _float_or_none(live.get("control_wall_secondary_transmission")),
        "control_wall_material": str(live.get("control_wall_material", "") or ""),
        "control_wall_thickness_mm": _float_or_none(live.get("control_wall_thickness_mm")),
        "control_wall_provenance": str(live.get("control_wall_provenance", "") or ""),
        "issued_output_enabled": live.get("issued_output_enabled"),
        "replay_verified": live.get("replay_verified"),
        "compliance_statement": "",
        "governing_requirement_text": "",
    }


def _user_facing_status(app: Any, barrier_name: str, live: Dict[str, Any]) -> str:
    status = str(live.get("compliance_status") or live.get("status") or "").strip().upper()
    margin = _float_or_none(live.get("margin_mm"))
    confidence = _row_confidence(app, barrier_name, live)

    if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or (margin is not None and margin < 0):
        return "FAIL"
    if status in {"REVIEW", "WARN", "WARNING"} or (margin is not None and margin < 0.5):
        return "REVIEW"
    return "PASS"


def _row_confidence(app: Any, barrier_name: str, live: Dict[str, Any]) -> float:
    try:
        return float(app._row_confidence_from_live(barrier_name, live))
    except Exception:
        return 1.0


def _status_text(status: str) -> str:
    s = str(status or "").strip().upper()
    if s == "PASS":
        return "Pass"
    if s == "REVIEW":
        return "Requires review"
    if s == "FAIL":
        return "Fail"
    return s or "Unknown"


def _first_exposed_transmitted_dose(live: Dict[str, Any]) -> Optional[float]:
    for key in (
        "transmitted_dose_uSv_per_week",
        "Tx_uSv_per_week",
        "occupied_transmitted_dose_uSv_per_week",
        "transmitted_weekly_dose_uSv",
    ):
        value = _float_or_none(live.get(key))
        if value is not None:
            return value
    return None


def _display_required_thickness_mm(live: Dict[str, Any]) -> Any:
    material = str(live.get("material", "") or "").strip().lower()
    if "concrete" in material:
        return _first_display_value(live.get("required_concrete_mm"), live.get("required_thickness_mm"))
    return _first_display_value(live.get("required_lead_mm"), live.get("required_thickness_mm"))


def _display_recommended_thickness_mm(live: Dict[str, Any]) -> Any:
    material = str(live.get("material", "") or "").strip().lower()
    if "concrete" in material:
        return _first_display_value(live.get("recommended_concrete_mm"), live.get("required_concrete_mm"), live.get("required_thickness_mm"))
    return _first_display_value(live.get("recommended_commercial_lead_mm"), live.get("required_lead_mm"), live.get("required_thickness_mm"))


def _first_display_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", "-"):
            return value
    return ""


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None
