"""Read-only PET development-preview overlay for the Geometry canvas.

The overlay consumes only UI-preview data. It never mutates RoomGeometry,
project sources, production barriers, or report payloads.
"""

from __future__ import annotations

from typing import Any

from geometry.source_marker_layout import resolve_source_marker_points

from geometry.pet_preview_position import PetPreviewPosition

PET_GEOMETRY_OVERLAY_CONTRACT_VERSION = 3
PET_GEOMETRY_OVERLAY_BASELINE = "pet-ui-preview-v8"

_WALL_ALIASES = {
    "n": "N", "north": "N", "n wall": "N", "north wall": "N",
    "e": "E", "east": "E", "e wall": "E", "east wall": "E",
    "s": "S", "south": "S", "s wall": "S", "south wall": "S",
    "w": "W", "west": "W", "w wall": "W", "west wall": "W",
}


def wall_key_for_preview_name(name: str) -> str | None:
    """Return a cardinal wall key when a preview barrier name clearly identifies one."""
    return _WALL_ALIASES.get(str(name or "").strip().lower())


def build_pet_geometry_overlay(
    preview: dict[str, Any],
    schedule: dict[str, Any],
    position: PetPreviewPosition,
) -> dict[str, Any]:
    """Build a compact immutable-style payload for Geometry-tab rendering."""
    rows = []
    for row in schedule.get("rows", ()):
        rows.append({
            "source_name": str(row["source_name"]),
            "wall_key": wall_key_for_preview_name(row["source_name"]),
            "material_key": str(row["material_key"]),
            "required_thickness_mm": float(row["required_thickness_mm"]),
            "provided_thickness_mm": (
                None if row["provided_thickness_mm"] is None
                else float(row["provided_thickness_mm"])
            ),
            "compliance_status": str(row["compliance_status"]),
        })
    return {
        "contract_version": PET_GEOMETRY_OVERLAY_CONTRACT_VERSION,
        "baseline": PET_GEOMETRY_OVERLAY_BASELINE,
        "production_eligible": False,
        "radionuclide": str(preview["radionuclide"]),
        "weekly_dose_uSv_at_1m": float(preview["weekly_dose_uSv_at_1m"]),
        "replay_verified": bool(schedule["replay_verified"]),
        "source_x_m": float(position.x_from_west_m),
        "source_y_m": float(position.y_from_south_m),
        "source_height_m": float(position.height_above_ffl_m),
        "rows": tuple(rows),
    }



def build_pet_input_geometry_overlay(
    radionuclide: str,
    position: PetPreviewPosition,
    *,
    weekly_dose_uSv_at_1m: float | None = None,
) -> dict[str, Any]:
    """Build a marker-only overlay for persisted PET input/provenance preview.

    Canonical barrier calculations now flow through the normal Results model,
    so the Sources-tab preview deliberately supplies no barrier-result rows.
    """
    return {
        "contract_version": PET_GEOMETRY_OVERLAY_CONTRACT_VERSION,
        "baseline": PET_GEOMETRY_OVERLAY_BASELINE,
        "production_eligible": False,
        "radionuclide": str(radionuclide),
        "weekly_dose_uSv_at_1m": (
            None if weekly_dose_uSv_at_1m is None
            else float(weekly_dose_uSv_at_1m)
        ),
        "replay_verified": False,
        "source_x_m": float(position.x_from_west_m),
        "source_y_m": float(position.y_from_south_m),
        "source_height_m": float(position.height_above_ffl_m),
        "rows": (),
    }

def _status_colour(status: str) -> str:
    value = str(status or "").upper()
    if value == "PASS":
        return "#15803d"
    if value == "FAIL":
        return "#b91c1c"
    return "#a16207"


def _material_display_name(material_key: str) -> str:
    return {
        "lead": "Pb",
        "concrete_2350kg_m3": "Concrete",
        "iron": "Iron",
    }.get(str(material_key or ""), str(material_key or ""))


def draw_pet_geometry_preview_overlay(
    canvas, geom, room_bbox, overlay: dict[str, Any] | None,
    layout_rendering: dict[str, Any] | None = None,
) -> None:
    """Draw a compact PET preview overlay without obscuring production geometry."""
    canvas.delete("pet_preview_overlay")
    if not overlay:
        return

    x0, y0, x1, y1 = room_bbox
    width_m = float(getattr(geom, "width_m", 0.0) or 0.0)
    length_m = float(getattr(geom, "length_m", 0.0) or 0.0)
    if width_m <= 0 or length_m <= 0:
        return

    px_per_m = min((x1 - x0) / width_m, (y1 - y0) / length_m)
    # RoomGeometry owns PET source position in the unified workflow. An older
    # preview payload may carry a stale position, so draw at the canonical point.
    source = getattr(geom, "source", None)
    sx_m = float(getattr(source, "x_m", width_m / 2.0) if source is not None else width_m / 2.0)
    sy_m = float(getattr(source, "y_m", length_m / 2.0) if source is not None else length_m / 2.0)
    sx = x0 + sx_m * px_per_m
    sy = y1 - sy_m * px_per_m
    rotation = int(getattr(getattr(geom, "source", None), "rotation_deg", 0) or 0) % 360
    marker_points = resolve_source_marker_points(sx, sy, px_per_m, rotation, layout_rendering)
    marker_x, marker_y = marker_points.source

    tag = "pet_preview_overlay"
    weekly_dose = overlay.get("weekly_dose_uSv_at_1m")
    try:
        weekly_dose_value = float(weekly_dose)
    except (TypeError, ValueError):
        weekly_dose_value = 0.0
    if weekly_dose_value > 0.0:
        reference_x, reference_y = marker_points.reference_circle
        circle_radius_px = float((layout_rendering or {}).get("reference_circle_radius_m", 1.0) or 1.0) * px_per_m
        label_gap_px = float((layout_rendering or {}).get("reference_circle_label_gap_px", 10.0) or 0.0)
        canvas.create_text(
            reference_x, reference_y - circle_radius_px - label_gap_px,
            text=f"{weekly_dose_value:.2f} µSv/wk @ 1 m",
            fill="#dc2626", font=("Segoe UI", 8, "bold"), anchor="center",
            tags=(tag, "pet_one_m_dose_label"),
        )

    # Barrier PASS/REVIEW/FAIL text is rendered by the canonical Geometry
    # barrier labels from the live production risk map. Keep this preview
    # overlay limited to the 1 m dose annotation so PET/SPECT/CT canvas
    # status presentation cannot drift.

    canvas.tag_raise(tag)
