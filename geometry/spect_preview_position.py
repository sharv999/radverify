"""Session-only geometry helpers for the SPECT development preview.

Step 11 performs geometry adaptation only.  It validates a transient source
position and derives cardinal source-to-wall distances without mutating the
saved RoomGeometry or performing shielding physics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SPECT_PREVIEW_POSITION_CONTRACT_VERSION = 1
SPECT_PREVIEW_POSITION_BASELINE = "spect-ui-preview-v6-source-position-edit"


class SpectPreviewPositionError(ValueError):
    """Raised when a preview-only source position is invalid."""


@dataclass(frozen=True)
class SpectPreviewPosition:
    source_x_m: float
    source_y_m: float


def build_spect_preview_position(
    room_geometry: Any, *, source_x_m: Any, source_y_m: Any
) -> SpectPreviewPosition:
    if room_geometry is None:
        raise SpectPreviewPositionError("Selected SPECT room has no geometry.")
    try:
        x = float(source_x_m)
        y = float(source_y_m)
        width = float(getattr(room_geometry, "width_m"))
        length = float(getattr(room_geometry, "length_m"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SpectPreviewPositionError(f"Invalid SPECT preview source position: {exc}") from exc
    if width <= 0.0 or length <= 0.0:
        raise SpectPreviewPositionError("Room width and length must be positive.")
    if not (0.0 <= x <= width):
        raise SpectPreviewPositionError(
            f"Preview source X must be between 0 and room width {width:g} m."
        )
    if not (0.0 <= y <= length):
        raise SpectPreviewPositionError(
            f"Preview source Y must be between 0 and room length {length:g} m."
        )
    return SpectPreviewPosition(source_x_m=x, source_y_m=y)


def cardinal_distances_for_spect_preview(
    room_geometry: Any, *, source_x_m: Any, source_y_m: Any
) -> dict[str, float]:
    position = build_spect_preview_position(
        room_geometry, source_x_m=source_x_m, source_y_m=source_y_m
    )
    width = float(room_geometry.width_m)
    length = float(room_geometry.length_m)
    return {
        "N": length - position.source_y_m,
        "S": position.source_y_m,
        "E": width - position.source_x_m,
        "W": position.source_x_m,
    }
