"""Read-only SPECT development-preview overlay for the Geometry canvas.

SPECT Step 10 is presentation-only.  The overlay consumes the already-computed
Step 5 schedule plus existing RoomGeometry coordinates; it performs no shielding
calculation and never mutates geometry, project state, Results, or reports.
"""
from __future__ import annotations

from typing import Any

from geometry.source_marker_layout import resolve_source_marker_points

from engine.spect_barrier_schedule import SpectBarrierScheduleResult


SPECT_GEOMETRY_OVERLAY_CONTRACT_VERSION = 1
SPECT_GEOMETRY_OVERLAY_BASELINE = "spect-ui-preview-v5-geometry-overlay"

_WALL_ALIASES = {
    "n": "N", "north": "N", "n wall": "N", "north wall": "N",
    "e": "E", "east": "E", "e wall": "E", "east wall": "E",
    "s": "S", "south": "S", "s wall": "S", "south wall": "S",
    "w": "W", "west": "W", "w wall": "W", "west wall": "W",
}


def wall_key_for_spect_preview_name(name: str) -> str | None:
    """Return a cardinal wall key only for an unambiguous barrier name."""

    return _WALL_ALIASES.get(str(name or "").strip().lower())


def build_spect_geometry_overlay(
    result: SpectBarrierScheduleResult,
    room_geometry: Any,
    *,
    source_x_m: float | None = None,
    source_y_m: float | None = None,
) -> dict[str, Any]:
    """Build a transient geometry-overlay payload from Step 5 presentation data."""

    if not isinstance(result, SpectBarrierScheduleResult):
        raise TypeError("result must be a SpectBarrierScheduleResult.")

    source = getattr(room_geometry, "source", None)
    source_x_m = float(getattr(source, "x_m", 0.0)) if source_x_m is None else float(source_x_m)
    source_y_m = float(getattr(source, "y_m", 0.0)) if source_y_m is None else float(source_y_m)

    rows = tuple(
        {
            "barrier_name": str(row.barrier_name),
            "wall_key": wall_key_for_spect_preview_name(row.barrier_name),
            "material_key": str(row.material_key),
            "required_thickness_mm": float(row.required_thickness_mm),
            "provided_thickness_mm": (
                None if row.provided_thickness_mm is None
                else float(row.provided_thickness_mm)
            ),
            "compliance_status": str(row.compliance_status),
            "room_scatter_caution": bool(
                row.required_room_scatter_caution
                or row.provided_room_scatter_caution is True
            ),
        }
        for row in result.rows
    )

    return {
        "contract_version": SPECT_GEOMETRY_OVERLAY_CONTRACT_VERSION,
        "baseline": SPECT_GEOMETRY_OVERLAY_BASELINE,
        "production_eligible": False,
        "radionuclide": str(result.source_physics.radionuclide),
        "weekly_dose_uSv_at_1m": float(result.source_physics.weekly_dose_uSv_at_1m),
        "source_x_m": source_x_m,
        "source_y_m": source_y_m,
        "room_name": str(getattr(room_geometry, "room_name", "") or ""),
        "rows": rows,
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
        "gypsum": "Gypsum",
        "concrete_1600kg_m3": "LW concrete",
        "concrete_2300kg_m3": "Concrete",
        "steel_a514": "Steel",
        "glass": "Glass",
    }.get(str(material_key or ""), str(material_key or ""))


def draw_spect_geometry_preview_overlay(
    canvas,
    geom,
    room_bbox,
    overlay: dict[str, Any] | None,
    layout_rendering: dict[str, Any] | None = None,
) -> None:
    """Render source/barrier context without obscuring production geometry."""

    canvas.delete("spect_preview_overlay")
    if not overlay:
        return
    if str(overlay.get("room_name", "")) != str(getattr(geom, "room_name", "") or ""):
        return

    x0, y0, x1, y1 = room_bbox
    width_m = float(getattr(geom, "width_m", 0.0) or 0.0)
    length_m = float(getattr(geom, "length_m", 0.0) or 0.0)
    if width_m <= 0.0 or length_m <= 0.0:
        return

    px_per_m = min((x1 - x0) / width_m, (y1 - y0) / length_m)
    # RoomGeometry owns SPECT patient/source position in the unified workflow.
    # Legacy preview state can carry an older what-if position, so never let
    # that payload create a second apparent source on the production canvas.
    source = getattr(geom, "source", None)
    sx_m = float(getattr(source, "x_m", width_m / 2.0) if source is not None else width_m / 2.0)
    sy_m = float(getattr(source, "y_m", length_m / 2.0) if source is not None else length_m / 2.0)
    sx_m = min(max(sx_m, 0.0), width_m)
    sy_m = min(max(sy_m, 0.0), length_m)
    sx = x0 + sx_m * px_per_m
    sy = y1 - sy_m * px_per_m
    rotation = int(getattr(getattr(geom, "source", None), "rotation_deg", 0) or 0) % 360
    marker_points = resolve_source_marker_points(sx, sy, px_per_m, rotation, layout_rendering)
    marker_x, marker_y = marker_points.source

    tag = "spect_preview_overlay"
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
            tags=(tag, "spect_one_m_dose_label"),
        )

    # Barrier PASS/REVIEW/FAIL text is rendered by the canonical Geometry
    # barrier labels from the live production risk map. Keep this preview
    # overlay limited to the 1 m dose annotation so PET/SPECT/CT canvas
    # status presentation cannot drift.

    canvas.tag_raise(tag)
