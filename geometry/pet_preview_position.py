"""Transient PET patient/source position for the non-production preview.

This module deliberately sits outside the shared RoomGeometry and project
serialization contracts.  It supplies a validated point inside the selected
room and derives PET-only source-to-barrier distances from that point.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class PetPreviewPosition:
    """Independent PET preview point in room coordinates."""

    x_from_west_m: float
    y_from_south_m: float
    height_above_ffl_m: float

    def validate_for_room(self, room_geometry: Any) -> "PetPreviewPosition":
        coordinates = {
            "from West": float(self.x_from_west_m),
            "from South": float(self.y_from_south_m),
            "height": float(self.height_above_ffl_m),
        }
        for label, value in coordinates.items():
            if not isfinite(value):
                raise ValueError(f"PET position {label} must be finite.")
        width_m = float(getattr(room_geometry, "width_m", 0.0) or 0.0)
        length_m = float(getattr(room_geometry, "length_m", 0.0) or 0.0)
        height_m = float(getattr(room_geometry, "height_m", 0.0) or 0.0)
        if width_m <= 0 or length_m <= 0 or height_m <= 0:
            raise ValueError("Selected room geometry must have positive width, length and height.")
        if not 0.0 <= self.x_from_west_m <= width_m:
            raise ValueError(f"PET position from West must be between 0 and {width_m:g} m.")
        if not 0.0 <= self.y_from_south_m <= length_m:
            raise ValueError(f"PET position from South must be between 0 and {length_m:g} m.")
        if not 0.0 <= self.height_above_ffl_m <= height_m:
            raise ValueError(f"PET position height must be between 0 and {height_m:g} m AFFL.")
        return self

    def barrier_distances(self, room_geometry: Any) -> dict[str, float]:
        """Return PET-only distances to the six room boundary planes."""
        self.validate_for_room(room_geometry)
        width_m = float(room_geometry.width_m)
        length_m = float(room_geometry.length_m)
        height_m = float(room_geometry.height_m)
        return {
            "N": max(0.1, length_m - self.y_from_south_m),
            "E": max(0.1, width_m - self.x_from_west_m),
            "S": max(0.1, self.y_from_south_m),
            "W": max(0.1, self.x_from_west_m),
            "Floor": max(0.1, self.height_above_ffl_m),
            "Ceiling": max(0.1, height_m - self.height_above_ffl_m),
        }


def default_pet_preview_position(room_geometry: Any) -> PetPreviewPosition:
    """Return a PET-specific default independent of the CT source isocentre."""
    width_m = float(getattr(room_geometry, "width_m", 0.0) or 0.0)
    length_m = float(getattr(room_geometry, "length_m", 0.0) or 0.0)
    height_m = float(getattr(room_geometry, "height_m", 0.0) or 0.0)
    return PetPreviewPosition(
        x_from_west_m=width_m / 2.0,
        y_from_south_m=length_m / 2.0,
        height_above_ffl_m=min(1.0, height_m),
    ).validate_for_room(room_geometry)
