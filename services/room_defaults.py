from __future__ import annotations

from models.shielding_models import Room
from engine.design_constraints import (
    build_room_constraint_summary,
    get_barrier_design_defaults,
    get_room_constraint_profile,
)


def apply_room_constraint_defaults(app, room: Room) -> None:
    """Apply modality-specific room/barrier defaults for newly-created/default barriers."""
    profile = get_room_constraint_profile(room.modality)
    app.room_constraint_summary[room.name] = build_room_constraint_summary(room.modality)

    if hasattr(app, "global_energy_var") and not str(app.global_energy_var.get()).strip():
        app.global_energy_var.set(profile.default_energy_label)
    if hasattr(app, "solver_mode_var") and not str(app.solver_mode_var.get()).strip():
        app.solver_mode_var.set(profile.default_solver_mode)

    is_xray = str(getattr(room, "modality", "") or "").strip().upper() == "X-RAY"
    for barrier in room.barriers:
        barrier_name = str(getattr(barrier, "name", "") or "").strip().lower()
        # XR-19C1: GXR external-wall T/P defaults are modality-specific and
        # must not be overwritten by the generic adjacent-area profile.
        # This is deliberately limited to N/E/S/W; Floor/Ceiling retain the
        # normal room-constraint defaults and persisted projects are untouched.
        if is_xray and barrier_name in {"n wall", "e wall", "s wall", "w wall"}:
            continue
        defaults = get_barrier_design_defaults(room.modality, barrier.adjacent_area)
        looks_default = (
            float(barrier.distance_m) == 2.0
            and str(getattr(barrier, "material", "")) == "Pb"
            and abs(float(getattr(barrier, "thickness_mm", 0.88)) - 0.88) < 1e-9
            and float(barrier.design_goal_uSv_per_week) in (10.0, 20.0, 50.0, 100.0)
        )
        if looks_default:
            barrier.occupancy_factor = float(defaults["occupancy_factor"])
            barrier.design_goal_uSv_per_week = float(defaults["design_goal_uSv_per_week"])


def apply_new_xray_wall_defaults(room: Room) -> None:
    """Seed canonical external-wall inputs on an explicit transition to GXR.

    This is intentionally not a load-time migration: persisted projects keep
    their saved barrier construction/design inputs.
    """
    if str(getattr(room, "modality", "") or "").strip().upper() != "X-RAY":
        return
    for barrier in getattr(room, "barriers", []) or []:
        name = str(getattr(barrier, "name", "") or "").strip().lower()
        if name not in {"n wall", "e wall", "s wall", "w wall"}:
            continue
        barrier.material = "Pb"
        barrier.thickness_mm = 0.88
        barrier.material_legacy = "Pb 0.88 mm (10 kg/m2)"
        barrier.occupancy_factor = 1.0
        barrier.design_goal_uSv_per_week = 10.0


def apply_new_xray_geometry_defaults(room: Room) -> None:
    """Seed GXR geometry on an explicit modality transition, not project reopen."""
    if str(getattr(room, "modality", "") or "").strip().upper() != "X-RAY":
        return
    from geometry.default_room_geometry import create_default_room_geometry

    previous = getattr(room, "geometry", None)
    geometry = create_default_room_geometry(room.name, room.modality)
    if previous is not None:
        geometry.width_m = previous.width_m
        geometry.length_m = previous.length_m
        geometry.height_m = previous.height_m
        # Preserve dimensions while positioning the default Control Wall
        # relative to the actual North boundary.
        geometry.control_wall.center_y_m = geometry.length_m - 1.5
    room.geometry = geometry
