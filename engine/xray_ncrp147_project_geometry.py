"""Project-specific NCRP 147 Section 5.3 / Figure 5.2 radiographic-room adapter.

XR-08C connects the qualified XR-08B physics to persisted RadShield geometry.
It remains independent of issued-output enablement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from engine.xray_ncrp147_fig52 import (
    Fig52Component, Fig52Scenario, solve_fig52_scenario, structural_transmission_factor,
)

PROJECT_FIG52_VERSION = "xr19b-bucky-shield-primary-v1"
SECONDARY_MGY_PER_PATIENT_AT_1M = 0.034
PRIMARY_FLOOR_MGY_PER_PATIENT_AT_1M = 5.2
PRIMARY_CHEST_MGY_PER_PATIENT_AT_1M = 2.3

FIG52_BARRIER_ROLES = (
    "fig52_chest_bucky_wall",
    "fig52_cross_table_wall",
    "fig52_secondary_wall",
    "fig52_control_wall",
    "fig52_door",
    "fig52_darkroom_wall",
    "fig52_floor_under_table",
    "fig52_ceiling",
)


def _positive(value: Any, label: str) -> float:
    x = float(value)
    if x <= 0.0:
        raise ValueError(f"{label} must be positive for NCRP 147 Fig. 5.2 geometry.")
    return x


def _source_for_room(project: Any, room: Any) -> Any:
    sources = [s for s in getattr(project, "sources", []) or [] if str(getattr(s, "room_name", "")) == str(room.name)]
    qualified = [s for s in sources if str(getattr(s, "source_type", "")) == "xray_primary"]
    if len(qualified) != 1:
        raise ValueError("Fig. 5.2 project geometry requires exactly one General Radiography source in the room.")
    source = qualified[0]
    params = getattr(source, "params", {}) or {}
    if params.get("xray_method") != "ncrp_simplified" or params.get("exam_room_type") != "general_radiography":
        raise ValueError("Fig. 5.2 project geometry requires the qualified General Radiography NCRP simplified source.")
    return source


def _kerma(n: float, workload: float, distance_m: float, use_factor: float = 1.0) -> float:
    d = _positive(distance_m, "Barrier distance")
    return float(n) * float(workload) * float(use_factor) / (d * d)


def scenario_for_project_barrier(project: Any, room: Any, barrier: Any) -> Fig52Scenario:
    """Build a qualified Fig. 5.2 scenario using this barrier's actual distance."""
    source = _source_for_room(project, room)
    params = getattr(source, "params", {}) or {}
    n = _positive(params.get("exams_per_week", 0.0), "Exams per week")
    d = _positive(getattr(barrier, "distance_m", 0.0), "Barrier distance")
    role = str(getattr(barrier, "barrier_role", "") or "").strip().lower()

    secondary = lambda name, distribution="all_barriers": Fig52Component(
        name, "secondary", _kerma(n, SECONDARY_MGY_PER_PATIENT_AT_1M, d), distribution
    )

    if role == "fig52_floor_under_table":
        return Fig52Scenario(role, "Floor beneath radiographic table", (
            Fig52Component("primary_floor", "primary", _kerma(n, PRIMARY_FLOOR_MGY_PER_PATIENT_AT_1M, d, 0.89), "floor_or_other", "grid_cassette_support"),
            secondary("secondary_floor"),
        ), "governing_max", "5.3.1")
    if role == "fig52_ceiling":
        return Fig52Scenario(role, "Ceiling", (secondary("secondary_ceiling"),), "governing_max", "5.3.2")
    if role == "fig52_chest_bucky_wall":
        return Fig52Scenario(role, "Wall containing chest image receptor", (
            Fig52Component("primary_chest_bucky", "primary", _kerma(n, PRIMARY_CHEST_MGY_PER_PATIENT_AT_1M, d, 1.0), "chest_bucky", "grid_cassette_support"),
            secondary("secondary_chest_bucky", "chest_bucky"),
        ), "governing_max", "5.3.3")
    if role == "fig52_darkroom_wall":
        return Fig52Scenario(role, "Darkroom wall (legacy film workflow)", (secondary("secondary_darkroom"),), "governing_max", "5.3.4")
    if role == "fig52_cross_table_wall":
        return Fig52Scenario(role, "Cross-table lateral / 2% primary wall", (
            Fig52Component("primary_cross_table", "primary", _kerma(n, PRIMARY_FLOOR_MGY_PER_PATIENT_AT_1M, d, 0.02), "floor_or_other", "grid_cassette"),
            secondary("secondary_cross_table", "floor_or_other"),
        ), "joint", "5.3.5")
    if role == "fig52_control_wall":
        return Fig52Scenario(role, "Control wall", (secondary("secondary_control"),), "governing_max", "5.3.6")
    if role in {"fig52_secondary_wall", "fig52_door"}:
        return Fig52Scenario(role, "Secondary barrier", (secondary("secondary_barrier"),), "governing_max", "5.3")
    raise ValueError(f"Barrier role {role!r} is not qualified for project-specific NCRP 147 Fig. 5.2 calculation.")


def _external_wall_orientation(barrier: Any) -> str | None:
    """Return N/E/S/W only for canonical external room-wall barriers."""
    name = str(getattr(barrier, "name", "") or "").strip().upper()
    for wall in ("N", "E", "S", "W"):
        if name == f"{wall} WALL":
            return wall
    return None


def _control_wall_secondary_factor(room: Any, barrier: Any) -> tuple[bool, float]:
    """XR-17B secondary attenuation credit for an intercepted external wall ray.

    The internal Control Wall is qualified as a secondary barrier (§5.3.6), so
    XR-17B credits only secondary components. Primary components are deliberately
    unchanged pending a separate qualification decision.
    """
    geometry = getattr(room, "geometry", None)
    control = getattr(geometry, "control_wall", None) if geometry is not None else None
    wall = _external_wall_orientation(barrier)
    if control is None or wall is None:
        return False, 1.0
    if not geometry.control_wall_intercepts_external_wall_ray(wall):
        return False, 1.0
    factor = structural_transmission_factor(
        "secondary", "all_barriers", float(getattr(control, "thickness_mm", 0.0) or 0.0),
        str(getattr(control, "material", "") or ""),
    )
    return True, factor


def _scenario_with_intervening_control_wall(room: Any, barrier: Any, scenario: Fig52Scenario) -> tuple[Fig52Scenario, bool, float]:
    applied, factor = _control_wall_secondary_factor(room, barrier)
    if not applied:
        return scenario, False, 1.0
    components = tuple(
        Fig52Component(
            c.name, c.kind,
            c.unshielded_mGy_week * factor if c.kind == "secondary" else c.unshielded_mGy_week,
            c.distribution, c.preshield,
        )
        for c in scenario.components
    )
    return Fig52Scenario(scenario.scenario_id, scenario.label, components, scenario.combination, scenario.section), True, factor


def _bucky_shield_primary_factor(room: Any, barrier: Any) -> tuple[bool, float]:
    """Fixed 2.20 mm Pb Bucky Shield credit for the wall containing its Chest Bucky."""
    if str(getattr(barrier, "barrier_role", "") or "").strip().lower() != "fig52_chest_bucky_wall":
        return False, 1.0
    geometry = getattr(room, "geometry", None)
    bucky = getattr(geometry, "wall_bucky", None) if geometry is not None else None
    shield = getattr(geometry, "bucky_shield", None) if geometry is not None else None
    wall = _external_wall_orientation(barrier)
    if bucky is None or shield is None or wall is None:
        return False, 1.0
    if str(getattr(bucky, "wall", "") or "").upper() != wall or str(getattr(shield, "wall", "") or "").upper() != wall:
        return False, 1.0
    if abs(float(getattr(shield, "offset_m", 0.0)) - float(getattr(bucky, "offset_m", 0.0))) > 1e-6:
        return False, 1.0
    if abs(float(getattr(shield, "width_m", 0.0)) - 1.2) > 1e-6:
        return False, 1.0
    if str(getattr(shield, "material", "") or "") != "Pb" or abs(float(getattr(shield, "thickness_mm", 0.0)) - 2.2) > 1e-6:
        return False, 1.0
    return True, structural_transmission_factor("primary", "chest_bucky", 2.2, "Pb")


def _scenario_with_bucky_shield(room: Any, barrier: Any, scenario: Fig52Scenario) -> tuple[Fig52Scenario, bool, float]:
    """Apply the fixed 2.20 mm Pb Bucky Shield to every ray through its finite region.

    The shield is a physical Pb layer behind the Chest Bucky, not merely receptor
    preshielding.  Primary and secondary components therefore both traverse it,
    using their own NCRP 147 workload-distribution transmission fits.  The
    returned scalar remains the primary/chest-bucky factor for compatibility;
    per-component factors are recoverable deterministically from the scenario.
    """
    applied, primary_factor = _bucky_shield_primary_factor(room, barrier)
    if not applied:
        return scenario, False, 1.0
    components = tuple(
        Fig52Component(
            c.name,
            c.kind,
            c.unshielded_mGy_week * structural_transmission_factor(c.kind, c.distribution, 2.2, "Pb"),
            c.distribution,
            c.preshield,
        )
        for c in scenario.components
    )
    return Fig52Scenario(scenario.scenario_id, scenario.label, components, scenario.combination, scenario.section), True, primary_factor

def solve_project_barrier(project: Any, room: Any, barrier: Any, *, include_bucky_shield: bool = True) -> Dict[str, object]:
    scenario = scenario_for_project_barrier(project, room, barrier)
    if include_bucky_shield:
        scenario, bucky_applied, bucky_factor = _scenario_with_bucky_shield(room, barrier, scenario)
    else:
        bucky_applied, bucky_factor = False, 1.0
    scenario, control_applied, control_factor = _scenario_with_intervening_control_wall(room, barrier, scenario)
    occupancy = _positive(getattr(barrier, "occupancy_factor", 0.0), "Occupancy factor")
    p_usv = _positive(getattr(barrier, "design_goal_uSv_per_week", 0.0), "Design goal")
    target_mgy = (p_usv / occupancy) / 1000.0
    result = solve_fig52_scenario(scenario, target_mgy, getattr(barrier, "material", ""))
    result.update({
        "project_fig52_version": PROJECT_FIG52_VERSION,
        "barrier_name": str(getattr(barrier, "name", "")),
        "barrier_role": str(getattr(barrier, "barrier_role", "")),
        "distance_m": float(getattr(barrier, "distance_m", 0.0)),
        "occupancy_factor": occupancy,
        "design_goal_uSv_per_week": p_usv,
        "target_occupied_mGy_week": target_mgy,
        "existing_thickness_mm": float(getattr(barrier, "thickness_mm", 0.0) or 0.0),
        "control_wall_attenuation_applied": control_applied,
        "control_wall_secondary_transmission": control_factor,
        "bucky_shield_attenuation_applied": bucky_applied,
        "bucky_shield_primary_transmission": bucky_factor,
    })
    return result


def solve_project_room(project: Any, room: Any) -> list[Dict[str, object]]:
    return [solve_project_barrier(project, room, b) for b in getattr(room, "barriers", []) or []]
