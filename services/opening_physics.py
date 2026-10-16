"""Canonical interpretation and calculation helpers for barrier openings.

Doors and viewing panels are represented in room geometry, but shielding
calculation/reporting needs them interpreted as ``Barrier`` objects.  This
module is the single boundary for that interpretation so UI and report paths
cannot drift on parent-wall resolution, material/Pb-equivalence handling, or
opening live-result construction.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.shielding_engine import (
    calc_barrier_result,
    get_barrier_material_family,
    material_linear_attenuation_coefficient_cm_inv,
    required_thickness_with_buildup,
    required_transmission_factor_from_weekly_dose,
)
from engine.xray_ncrp147_fig52 import structural_transmission_factor
from models.shielding_models import Barrier, Room


def opening_type_normalized(opening: Any) -> str:
    raw = str(
        getattr(opening, "opening_type", getattr(opening, "type", "door"))
        or "door"
    ).strip().lower()
    if raw in {"lead_glass", "viewing_panel", "vp", "pb_glass"}:
        return "viewing_panel"
    return "door"


def opening_parent_barrier(room: Room, opening: Any) -> Optional[Barrier]:
    wall = str(
        getattr(opening, "wall", getattr(opening, "wall_id", "")) or ""
    ).strip().upper()
    if wall in {"N", "E", "S", "W"}:
        target = f"{wall} wall"
    else:
        target = str(getattr(opening, "parent_barrier", "") or "").strip()

    for barrier in getattr(room, "barriers", []) or []:
        if str(getattr(barrier, "name", "") or "").strip().lower() == target.lower():
            return barrier
    return None


def opening_barrier_id(opening: Any, fallback_index: int) -> str:
    explicit = str(getattr(opening, "id", "") or "").strip()
    if explicit:
        return explicit
    label = str(getattr(opening, "label", "") or "").strip()
    if label:
        return label
    prefix = "VP" if opening_type_normalized(opening) == "viewing_panel" else "D"
    return f"{prefix}{fallback_index}"


def opening_display_material(opening: Any) -> str:
    material = str(getattr(opening, "material", "") or "").strip()
    if material:
        return material
    return (
        "Pb equivalent glass"
        if opening_type_normalized(opening) == "viewing_panel"
        else "Solid timber"
    )


def opening_physics_material(opening: Any) -> str:
    return "Pb glass" if opening_type_normalized(opening) == "viewing_panel" else "Pb"


def opening_pb_equiv_mm(opening: Any, default: float = 0.0) -> float:
    try:
        return float(
            getattr(opening, "pb_equiv_mm", getattr(opening, "pb_mm", default))
            or default
        )
    except Exception:
        return float(default)


def make_opening_physics_barrier(
    room: Room,
    opening: Any,
    fallback_index: int,
) -> Optional[Barrier]:
    parent = opening_parent_barrier(room, opening)
    if parent is None:
        return None

    otype = opening_type_normalized(opening)
    oid = opening_barrier_id(opening, fallback_index)
    display_material = opening_display_material(opening)
    physics_material = opening_physics_material(opening)
    pb_mm = opening_pb_equiv_mm(
        opening,
        2.20 if otype == "viewing_panel" else 0.0,
    )

    role = str(getattr(parent, "barrier_role", "") or "secondary_wall")
    if otype == "viewing_panel":
        role = "viewing_panel"
    elif otype == "door":
        role = "door"

    return Barrier(
        name=oid,
        material=physics_material,
        thickness_mm=pb_mm,
        adjacent_area=str(getattr(parent, "name", "") or ""),
        barrier_role=role,
        distance_m=(
            float(room.geometry.source_to_opening_distance_m(opening))
            if str(getattr(room, "modality", "") or "").strip().upper() == "X-RAY"
            and getattr(room, "geometry", None) is not None
            else float(getattr(parent, "distance_m", 2.0) or 2.0)
        ),
        occupancy_factor=float(getattr(parent, "occupancy_factor", 0.2) or 0.2),
        design_goal_uSv_per_week=float(
            getattr(parent, "design_goal_uSv_per_week", 10.0) or 10.0
        ),
        material_legacy=f"{display_material} ({pb_mm:.2f} mm Pb-equivalent)",
        notes=f"{display_material}; sub-barrier in {getattr(parent, 'name', '')}",
    )


def _apply_gxr_control_wall_credit(app: Any, room: Room, opening: Any, barrier: Barrier, live: Dict[str, Any]) -> Dict[str, Any]:
    """Apply finite Control Wall attenuation to an intercepted GXR opening ray.

    Openings are secondary sub-barriers.  Their T and P remain inherited from
    the parent wall, while interception is evaluated at the opening centre.
    """
    if str(getattr(room, "modality", "") or "").strip().upper() != "X-RAY":
        return live
    geometry = getattr(room, "geometry", None)
    control = getattr(geometry, "control_wall", None) if geometry is not None else None
    if control is None or not geometry.control_wall_intercepts_opening_ray(opening):
        live.update({
            "control_wall_attenuation_applied": False,
            "control_wall_secondary_transmission": 1.0,
            "control_wall_material": "",
            "control_wall_thickness_mm": None,
            "control_wall_provenance": "",
        })
        return live

    factor = structural_transmission_factor(
        "secondary", "all_barriers",
        float(getattr(control, "thickness_mm", 0.0) or 0.0),
        str(getattr(control, "material", "") or ""),
    )
    unshielded = float(live.get("unshielded_weekly_dose_uSv", 0.0) or 0.0) * factor
    occupancy = float(getattr(barrier, "occupancy_factor", 1.0) or 1.0)
    design_goal = float(getattr(barrier, "design_goal_uSv_per_week", 10.0) or 10.0)
    old_unshielded = float(live.get("unshielded_weekly_dose_uSv", 0.0) or 0.0)
    old_tx = float(live.get("transmitted_dose_uSv_per_week", 0.0) or 0.0)
    actual_opening_factor = old_tx / (old_unshielded * occupancy) if old_unshielded > 0.0 and occupancy > 0.0 else 1.0
    transmitted = unshielded * occupancy * actual_opening_factor

    required_B = required_transmission_factor_from_weekly_dose(design_goal, occupancy, unshielded)
    family = get_barrier_material_family(barrier)
    energy = app.global_energy_var.get()
    mu = material_linear_attenuation_coefficient_cm_inv(barrier.material, energy)
    required_mm = required_thickness_with_buildup(required_B, mu, family, energy)
    existing_mm = float(getattr(barrier, "thickness_mm", 0.0) or 0.0)
    status = "FAIL" if transmitted >= design_goal else ("REVIEW" if transmitted >= 0.8 * design_goal else "PASS")

    live.update({
        "distance_m": round(float(getattr(barrier, "distance_m", 0.0) or 0.0), 3),
        "unshielded_weekly_dose_uSv": round(unshielded, 3),
        "transmitted_dose_uSv_per_week": round(transmitted, 3),
        "barrier_transmission_factor_B": round(required_B, 6),
        "required_thickness_mm": round(required_mm, 3),
        "required_lead_mm": round(required_mm, 3),
        "ct_required_mm": round(required_mm, 3),
        "compliance_status": status,
        "dose_margin_uSv_per_week": round(design_goal - transmitted, 3),
        "margin_mm": round(existing_mm - required_mm, 3),
        "control_wall_attenuation_applied": True,
        "control_wall_secondary_transmission": round(float(factor), 9),
        "control_wall_material": str(getattr(control, "material", "") or ""),
        "control_wall_thickness_mm": round(float(getattr(control, "thickness_mm", 0.0) or 0.0), 3),
        "control_wall_provenance": (
            f"Intervening Control Wall attenuation credited on source-to-opening-centre ray: "
            f"{str(getattr(control, 'material', '') or '')} "
            f"{float(getattr(control, 'thickness_mm', 0.0) or 0.0):g} mm; Bcw={float(factor):.9f}."
        ),
    })
    return live


def opening_live_result(
    app: Any,
    room: Room,
    opening: Any,
    fallback_index: int,
) -> tuple[Optional[Barrier], Dict[str, Any]]:
    """Calculate an opening through the same shielding engine used for barriers."""
    opening_barrier = make_opening_physics_barrier(room, opening, fallback_index)
    if opening_barrier is None:
        return None, {}

    try:
        live = calc_barrier_result(
            room,
            opening_barrier,
            app.project,
            app.global_energy_var.get(),
            solver_mode=app.solver_mode_var.get(),
        )
    except Exception as exc:
        live = {
            "compliance_status": "ERROR",
            "notes": f"Opening physics failed: {exc}",
            "required_thickness_mm": "",
            "margin_mm": "",
        }

    if str(live.get("compliance_status", "")).upper() != "ERROR":
        live = _apply_gxr_control_wall_credit(app, room, opening, opening_barrier, live)

    otype = opening_type_normalized(opening)
    display_material = opening_display_material(opening)
    parent = opening_parent_barrier(room, opening)

    live["barrier"] = opening_barrier.name
    live["dominant_component"] = live.get("dominant_component") or live.get(
        "dominant_source_name", ""
    )
    live["ct_required_mm"] = live.get("required_thickness_mm", "")
    base_note = (
        f"{display_material}; treated as "
        f"{'viewing panel' if otype == 'viewing_panel' else 'door'} "
        f"sub-barrier in {getattr(parent, 'name', '') if parent else 'parent wall'}; "
        f"inherits T={float(getattr(opening_barrier, 'occupancy_factor', 0.0) or 0.0):g} "
        f"and P={float(getattr(opening_barrier, 'design_goal_uSv_per_week', 0.0) or 0.0):g} uSv/wk from parent."
    )
    provenance = str(live.get("control_wall_provenance", "") or "")
    live["notes"] = f"{base_note} {provenance}".strip()
    return opening_barrier, live
