from __future__ import annotations

from pathlib import Path
from typing import Any

from modalities.spect import calculate_spect_weekly_dose_at_1m
from serialization.spect_working_project_state import get_room_spect_working_state
from services.project_io import load_project_from_file
from services.spect_results_model import build_spect_production_results_payload


ANNUAL_WEEKS = 52.0


def extract_spect_kat_payload(project_path: str | Path, *, kat_id: str = "SPECT-KAT-001") -> dict[str, Any]:
    """Return the canonical SPECT KAT values from a saved working-project fixture.

    The helper deliberately reuses the production SPECT source-physics and
    production Results paths.  It does not reimplement attenuation or shielding
    calculations.  The annual design dose is the UI presentation conversion
    of weekly P using the application convention of 52 weeks/year.
    """
    project = load_project_from_file(project_path)
    spect_rooms = [
        room
        for room in list(getattr(project, "rooms", []) or [])
        if str(getattr(room, "modality", "") or "").strip().upper() == "SPECT"
    ]
    if len(spect_rooms) != 1:
        raise ValueError(
            f"SPECT KAT fixture must contain exactly one SPECT room; found {len(spect_rooms)}."
        )

    room = spect_rooms[0]
    state = get_room_spect_working_state(room)
    if state is None:
        raise ValueError("SPECT KAT fixture has no persisted SPECT working source state.")

    source_physics = calculate_spect_weekly_dose_at_1m(state.source)
    results = build_spect_production_results_payload(project, room)

    barriers: dict[str, dict[str, Any]] = {}
    for row in results.rows:
        name = str(row["barrier_name"])
        design_goal = float(row["design_goal_uSv_per_week"])
        barriers[name] = {
            "distance_m": float(row["distance_m"]),
            "occupancy_factor": float(row["occupancy_factor"]),
            "design_goal_uSv_per_week": design_goal,
            "annual_design_dose_uSv_per_year": design_goal * ANNUAL_WEEKS,
            "unshielded_uSv_per_week": float(row["unshielded_weekly_dose_uSv"]),
            "occupied_unshielded_uSv_per_week": float(
                row["occupied_unshielded_weekly_dose_uSv"]
            ),
            "required_transmission_B": float(row["barrier_transmission_factor_B"]),
            "required_thickness_mm": float(row["required_thickness_mm"]),
            "provided_thickness_mm": float(row["provided_thickness_mm"]),
            "provided_transmission": float(row["provided_transmission"]),
            "transmitted_uSv_per_week": (
                None
                if row["transmitted_dose_uSv_per_week"] is None
                else float(row["transmitted_dose_uSv_per_week"])
            ),
            "status": str(row["compliance_status"]),
        }

    spec = state.source.radionuclide_spec
    return {
        "kat_id": str(kat_id),
        "room": {
            "name": str(room.name),
            "length_m": float(room.geometry.length_m),
            "width_m": float(room.geometry.width_m),
            "height_m": float(room.geometry.height_m),
            "source_from_west_m": float(room.geometry.source.x_m),
            "source_from_south_m": float(room.geometry.source.y_m),
        },
        "source": {
            "radionuclide": str(source_physics.radionuclide),
            "radiation_type": str(source_physics.radiation_type),
            "dose_rate_constant_uSv_h_per_MBq_at_1m": float(
                spec.dose_rate_constant_uSv_h_per_MBq_at_1m
            ),
            "administered_activity_MBq": float(source_physics.administered_activity_mbq),
            "patients_per_week": float(source_physics.patients_per_week),
            "imaging_duration_h": float(source_physics.imaging_duration_h),
            "decay_integrated_hours": float(source_physics.decay_integrated_hours),
            "weekly_dose_uSv_at_1m": float(source_physics.weekly_dose_uSv_at_1m),
        },
        "barriers": barriers,
    }
