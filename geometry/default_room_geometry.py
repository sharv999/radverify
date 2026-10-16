from __future__ import annotations

from geometry.geometry_model import RadiationSourceGeometry, RoomGeometry, WallBucky, BuckyShield, ControlWall
from modalities.registry import geometry_ui_for_modality
from config.geometry_constants import (
    DEFAULT_ROOM_HEIGHT_M,
    DEFAULT_ROOM_LENGTH_M,
    DEFAULT_ROOM_WIDTH_M,
)


def create_default_room_geometry(room_name: str, modality: str = "CT") -> RoomGeometry:
    """Create default room geometry for a new room.

    Numeric defaults remain centralised in ``config.geometry_constants``.
    """
    geometry_ui = geometry_ui_for_modality(modality)
    label = geometry_ui.source_label or str(modality or "Source")

    geometry = RoomGeometry(
        room_name=room_name,
        length_m=DEFAULT_ROOM_LENGTH_M,
        width_m=DEFAULT_ROOM_WIDTH_M,
        height_m=DEFAULT_ROOM_HEIGHT_M,
        source=RadiationSourceGeometry(label=label),
    )
    geometry.set_source_centre()
    if str(modality or "").strip().upper() == "X-RAY":
        geometry.source.x_m = geometry.width_m / 2.0
        geometry.source.y_m = 2.4

    # XR-10: a new General Radiography room starts with an explicit chest
    # image receptor.  This lets barrier synchronisation establish a sensible
    # NCRP 147 Fig. 5.2 scenario set instead of treating every wall as
    # secondary.  N is only a deterministic starting orientation; the user can
    # move the receptor to the actual wall in Geometry.
    if str(modality or "").strip().upper() == "X-RAY":
        geometry.wall_bucky = WallBucky(
            wall="W",
            offset_m=1.2,
        )
        geometry.bucky_shield = BuckyShield(wall="W", offset_m=1.2)
        geometry.control_wall = ControlWall(
            center_x_m=2.0, center_y_m=geometry.length_m - 1.5,
            length_m=1.5, nib_length_m=0.75, orientation_deg=0,
        )

    return geometry
