"""XR-05 canonical in-app Results and deterministic replay for General X-ray.

This adapter is deliberately limited to qualified NCRP 147 General Radiography
working projects.  It opens in-app Results/replay only; issued report/PDF paths are enabled only when the release-gate readiness contract also passes.
"""
from __future__ import annotations

import copy
from typing import Any


XRAY_RESULTS_MODEL_VERSION = "xr20d-serial-bucky-subbarrier-v1"
XRAY_RESULTS_ENERGY_LABEL = "xray_120kvp"
XRAY_CANONICAL_RESULTS_SOURCE = "xray_xr08e_project_fig52"


def xray_results_issueable(rows: list[dict[str, Any]]) -> bool:
    """True only for the released project-specific XR-08E Fig. 5.2 result set."""
    return bool(rows) and all(
        str(row.get("results_source", "")) == XRAY_CANONICAL_RESULTS_SOURCE
        and str(row.get("fig52_section", ""))
        and row.get("issued_output_enabled") is True
        for row in rows
    )


def _qualified_room_copy(project: Any, room: Any) -> Any:
    if str(getattr(room, "modality", "") or "").strip().upper() != "X-RAY":
        raise ValueError("XR-05 Results requires an X-ray room.")

    room_copy = copy.deepcopy(room)
    room_name = str(getattr(room, "name", "") or "").strip()
    room_copy.sources = [
        copy.deepcopy(src)
        for src in list(getattr(project, "sources", []) or [])
        if str(getattr(src, "room_name", "") or "").strip() == room_name
    ]
    qualified = [
        src for src in room_copy.sources
        if str(getattr(src, "source_type", "") or "").strip() == "xray_primary"
        and str(getattr(src, "params", {}).get("xray_method", "") or "").strip() == "ncrp_simplified"
    ]
    if len(qualified) != 1 or len(room_copy.sources) != 1:
        raise ValueError("XR-05 Results requires exactly one qualified General Radiography source.")
    return room_copy



def _validate_internal_control_wall_release(room: Any) -> None:
    """Fail closed unless persisted control-wall geometry matches its canonical barrier."""
    geometry = getattr(room, "geometry", None)
    control = getattr(geometry, "control_wall", None) if geometry is not None else None
    if control is None:
        return
    orientation = int(float(getattr(control, "orientation_deg", 0) or 0)) % 360
    if orientation not in (0, 90, 180, 270):
        raise ValueError("Control wall release requires orientation 0, 90, 180, or 270 degrees.")
    if float(getattr(control, "length_m", 0.0) or 0.0) <= 0.0:
        raise ValueError("Control wall release requires a positive wall length.")
    source = getattr(geometry, "source", None)
    if source is None:
        raise ValueError("Control wall release requires persisted X-ray source geometry.")
    expected_distance = float(control.source_distance_m(source.x_m, source.y_m))
    if expected_distance <= 0.0:
        raise ValueError("Control wall release requires a positive source-to-wall distance.")
    barriers = [
        b for b in list(getattr(room, "barriers", []) or [])
        if str(getattr(b, "barrier_role", "") or "") == "fig52_control_wall"
    ]
    if len(barriers) != 1:
        raise ValueError("Control wall release requires exactly one canonical fig52_control_wall barrier.")
    barrier = barriers[0]
    if abs(float(getattr(barrier, "distance_m", 0.0) or 0.0) - expected_distance) > 1e-6:
        raise ValueError("Control wall barrier distance does not match persisted geometry.")
    pairs = (
        (str(getattr(barrier, "material", "") or ""), str(getattr(control, "material", "") or ""), "material"),
        (float(getattr(barrier, "thickness_mm", 0.0) or 0.0), float(getattr(control, "thickness_mm", 0.0) or 0.0), "thickness"),
        (float(getattr(barrier, "occupancy_factor", 0.0) or 0.0), float(getattr(control, "occupancy_factor", 0.0) or 0.0), "occupancy"),
        (float(getattr(barrier, "design_goal_uSv_per_week", 0.0) or 0.0), float(getattr(control, "design_goal_uSv_per_week", 0.0) or 0.0), "design goal"),
    )
    for actual, expected, label in pairs:
        if actual != expected:
            raise ValueError(f"Control wall barrier {label} does not match persisted geometry.")

def build_xray_results_model(project: Any, room: Any) -> list[dict[str, Any]]:
    """Recompute canonical XR-08D Results from persisted project/Fig. 5.2 state."""
    room_copy = _qualified_room_copy(project, room)
    _validate_internal_control_wall_release(room_copy)
    # Preserve deterministic replay for pre-XR-08C saved projects. New production
    # projects use only explicit fig52_* roles; legacy roles retain their frozen
    # XR-05 calculation until migrated by the geometry synchronisation layer.
    if any(not str(getattr(b, "barrier_role", "") or "").startswith("fig52_") for b in room_copy.barriers):
        from engine.shielding_engine import calc_barrier_result
        legacy = [calc_barrier_result(room_copy, b, project, XRAY_RESULTS_ENERGY_LABEL) for b in room_copy.barriers]
        for row in legacy:
            row["results_model_version"] = XRAY_RESULTS_MODEL_VERSION
            row["replay_verified"] = True
            row["issued_output_enabled"] = False
        return legacy

    from engine.xray_ncrp147_fig52 import component_transmitted_mGy_week
    from engine.xray_ncrp147_project_geometry import solve_project_barrier

    rows: list[dict[str, Any]] = []
    for barrier in room_copy.barriers:
        # XR-20A: the structural wall is assessed independently of the finite
        # Bucky Shield. The shielded 1.2 m region is appended as a separate
        # sub-barrier result below.
        solved = solve_project_barrier(project, room_copy, barrier, include_bucky_shield=False)
        existing = float(getattr(barrier, "thickness_mm", 0.0) or 0.0)
        occupancy = float(solved["occupancy_factor"])
        p_usv = float(solved["design_goal_uSv_per_week"])
        project_geometry = __import__(
            "engine.xray_ncrp147_project_geometry",
            fromlist=["scenario_for_project_barrier", "_scenario_with_bucky_shield", "_scenario_with_intervening_control_wall"],
        )
        scenario = project_geometry.scenario_for_project_barrier(project, room_copy, barrier)
        bucky_applied, bucky_factor = False, 1.0
        scenario, control_applied, control_factor = project_geometry._scenario_with_intervening_control_wall(room_copy, barrier, scenario)
        unshielded_mgy = sum(c.unshielded_mGy_week for c in scenario.components)
        transmitted_mgy = sum(
            component_transmitted_mGy_week(c, existing, getattr(barrier, "material", ""))
            for c in scenario.components
        )
        occupied_usv = transmitted_mgy * occupancy * 1000.0
        required = float(solved["required_structural_mm"])
        if occupied_usv >= p_usv:
            status = "FAIL"
        elif occupied_usv >= 0.8 * p_usv:
            status = "REVIEW"
        else:
            status = "PASS"
        material = str(getattr(barrier, "material", "") or "")
        is_pb = material == "Pb" or material.startswith("Pb ")
        is_concrete = material.startswith("Concrete")
        rows.append({
            "room": room_copy.name, "room_modality": room_copy.modality,
            "barrier": barrier.name, "adjacent_area": barrier.adjacent_area,
            "distance_m": round(float(solved["distance_m"]), 3),
            "occupancy_factor": round(occupancy, 4),
            "design_goal_uSv_per_week": round(p_usv, 3),
            "unshielded_weekly_dose_uSv": round(unshielded_mgy * 1000.0, 3),
            "transmitted_dose_uSv_per_week": round(occupied_usv, 3),
            "source_contributions": "; ".join(
                f"{c.name}: {c.unshielded_mGy_week * 1000.0:.2f} uSv/wk" for c in scenario.components
            ),
            "dominant_source_name": max(scenario.components, key=lambda c: c.unshielded_mGy_week).name,
            "barrier_transmission_factor_B": round(transmitted_mgy / unshielded_mgy, 6) if unshielded_mgy else 1.0,
            "linear_attenuation_coefficient_cm_inv": "",
            "required_lead_mm": round(required, 3) if is_pb else "-",
            "required_concrete_mm": round(required, 1) if is_concrete else "-",
            "recommended_commercial_lead_mm": "-",
            "required_thickness_mm": round(required, 3),
            "actual_thickness_mm": round(existing, 3),
            "compliance_status": status,
            "dose_margin_uSv_per_week": round(p_usv - occupied_usv, 3),
            "margin_mm": round(existing - required, 3),
            "notes": str(getattr(barrier, "notes", "") or ""),
            "solver_used": f"ncrp147_s5.3_{solved['scenario_id']}",
            "results_model_version": XRAY_RESULTS_MODEL_VERSION,
            "replay_verified": True,
            # XR-17D: the intercepted secondary-attenuation pathway is explicitly
            # qualified/released. Geometry/barrier consistency is validated above,
            # and the attenuation factor is recomputed deterministically from the
            # persisted Control Wall construction on every replay.
            "issued_output_enabled": True,
            "results_source": XRAY_CANONICAL_RESULTS_SOURCE,
            "fig52": solved,
            "fig52_section": solved["section"],
            "fig52_combination": solved["combination"],
            "fig52_components": solved["components"],
            # XR-17C: explicit provenance for any intervening Control Wall credit.
            "bucky_shield_attenuation_applied": bool(bucky_applied),
            "bucky_shield_primary_transmission": round(float(bucky_factor), 9),
            "bucky_shield_material": "Pb" if bucky_applied else "",
            "bucky_shield_thickness_mm": 2.2 if bucky_applied else None,
            "bucky_shield_provenance": (f"Chest Bucky Shield primary attenuation credited: Pb 2.2 mm; Bbs={float(bucky_factor):.9f}." if bucky_applied else ""),
            "control_wall_attenuation_applied": bool(control_applied),
            "control_wall_secondary_transmission": round(float(control_factor), 9),
            "control_wall_material": (
                str(getattr(getattr(room_copy.geometry, "control_wall", None), "material", "") or "")
                if control_applied else ""
            ),
            "control_wall_thickness_mm": (
                round(float(getattr(getattr(room_copy.geometry, "control_wall", None), "thickness_mm", 0.0) or 0.0), 3)
                if control_applied else None
            ),
            "control_wall_provenance": (
                f"Intervening Control Wall secondary attenuation credited: "
                f"{str(getattr(room_copy.geometry.control_wall, 'material', '') or '')} "
                f"{float(getattr(room_copy.geometry.control_wall, 'thickness_mm', 0.0) or 0.0):g} mm; "
                f"Bcw={float(control_factor):.9f}."
                if control_applied else ""
            ),
        })

        # XR-20A: a Chest Bucky Shield protects only its finite 1.2 m region.
        # Represent that region as a separate physics result so the remainder
        # of the structural wall retains its own uncredited calculation.
        if str(getattr(barrier, "barrier_role", "") or "") == "fig52_chest_bucky_wall":
            shield_base_scenario = project_geometry.scenario_for_project_barrier(project, room_copy, barrier)
            shield_scenario, shield_applied, shield_factor = project_geometry._scenario_with_bucky_shield(room_copy, barrier, shield_base_scenario)
            if shield_applied:
                from engine.xray_ncrp147_fig52 import structural_transmission_factor
                bucky_component_factors = {
                    c.name: structural_transmission_factor(c.kind, c.distribution, 2.2, "Pb")
                    for c in shield_base_scenario.components
                }
                shield_scenario, shield_control_applied, shield_control_factor = project_geometry._scenario_with_intervening_control_wall(room_copy, barrier, shield_scenario)
                shield_unshielded = sum(c.unshielded_mGy_week for c in shield_scenario.components)
                shield_transmitted = sum(
                    component_transmitted_mGy_week(c, existing, getattr(barrier, "material", ""))
                    for c in shield_scenario.components
                )
                shield_occupied = shield_transmitted * occupancy * 1000.0
                shield_status = "FAIL" if shield_occupied >= p_usv else ("REVIEW" if shield_occupied >= 0.8 * p_usv else "PASS")
                shield_solved = solve_project_barrier(project, room_copy, barrier, include_bucky_shield=True)
                shield_required = float(shield_solved["required_structural_mm"])
                shield_row = copy.deepcopy(rows[-1])
                shield_row.update({
                    "barrier": "Bucky shield",
                    "barrier_name": "Bucky shield",
                    "barrier_role": "fig52_chest_bucky_subbarrier",
                    "sub_barrier": True,
                    "parent_barrier": str(getattr(barrier, "name", "") or ""),
                    "sub_barrier_width_m": 1.2,
                    "unshielded_weekly_dose_uSv": round(shield_unshielded * 1000.0, 3),
                    "transmitted_dose_uSv_per_week": round(shield_occupied, 3),
                    "barrier_transmission_factor_B": round(shield_transmitted / shield_unshielded, 6) if shield_unshielded else 1.0,
                    "required_thickness_mm": round(shield_required, 3),
                    "required_lead_mm": round(shield_required, 3) if is_pb else "-",
                    "required_concrete_mm": round(shield_required, 1) if is_concrete else "-",
                    "compliance_status": shield_status,
                    "dose_margin_uSv_per_week": round(p_usv - shield_occupied, 3),
                    "margin_mm": round(existing - shield_required, 3),
                    "fig52": shield_solved,
                    "fig52_components": shield_solved["components"],
                    "bucky_shield_attenuation_applied": True,
                    "bucky_shield_primary_transmission": round(float(shield_factor), 9),
                    "bucky_shield_component_transmissions": {k: round(float(v), 9) for k, v in bucky_component_factors.items()},
                    "bucky_shield_material": "Pb",
                    "bucky_shield_thickness_mm": 2.2,
                    "bucky_shield_provenance": f"Finite 1.2 m Chest Bucky sub-barrier: all radiation traverses structural wall plus Pb 2.20 mm Bucky Shield; primary Bbs={float(shield_factor):.9f}.",
                    "control_wall_attenuation_applied": bool(shield_control_applied),
                    "control_wall_secondary_transmission": round(float(shield_control_factor), 9),
                })
                rows.append(shield_row)
    return rows
