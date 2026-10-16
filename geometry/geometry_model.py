from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, List, Dict, Any, Optional

from geometry.room_defaults import get_barrier_default
from config.geometry_constants import *

WallOrientation = Literal["N", "E", "S", "W"]
OpeningType = Literal["door", "lead_glass", "viewing_panel"]

@dataclass
class Opening:
    wall: WallOrientation = "N"
    opening_type: OpeningType = "door"
    offset_m: float = 1.0
    width_m: float = 0.9
    label: str = ""
    pb_equiv_mm: float = 0.88
    material: str = "Pb"
    sill_height_above_ffl_m: float = 0.0
    head_height_above_ffl_m: float = 2.1
    kvp_basis: Optional[float] = None
    id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Opening":
        raw_type = data.get("opening_type", data.get("type", "door"))
        opening_type = "viewing_panel" if raw_type in {"lead_glass", "viewing_panel", "vp"} else "door"
        default = get_barrier_default("CT", "viewing_panel" if opening_type == "viewing_panel" else "door")
        return Opening(
            wall=data.get("wall", data.get("wall_id", "N")),
            opening_type=opening_type,
            offset_m=float(data.get("offset_m", data.get("position_m", 1.0))),
            width_m=float(data.get("width_m", 0.9)),
            label=str(data.get("label", "")),
            pb_equiv_mm=float(data.get("pb_equiv_mm", data.get("pb_mm", default.get("pb_mm", 0.0)) or 0.0)),
            material=str(data.get("material", default.get("material", "")) or ""),
            sill_height_above_ffl_m=float(data.get("sill_height_above_ffl_m", data.get("sill_height_m", default.get("sill_height_above_ffl_m", 0.0))) or 0.0),
            head_height_above_ffl_m=float(data.get("head_height_above_ffl_m", data.get("head_height_m", default.get("head_height_above_ffl_m", 2.1))) or 2.1),
            kvp_basis=(float(data.get("kvp_basis")) if data.get("kvp_basis", None) not in (None, "") else default.get("kvp_basis")),
            id=str(data.get("id", "") or ""),
        )


@dataclass
class WallBucky:
    wall: WallOrientation = "N"
    offset_m: float = 1.0
    width_m: float = 0.6
    height_m: float = 1.2
    sill_height_above_ffl_m: float = 0.9
    head_height_above_ffl_m: float = 2.1
    material: str = "Wall bucky / vertical image receptor"
    id: str = "WB1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "WallBucky":
        d = get_barrier_default("X-ray", "wall_bucky")
        return WallBucky(
            wall=data.get("wall", data.get("wall_id", "N")),
            offset_m=float(data.get("offset_m", data.get("position_m", 1.0))),
            width_m=float(data.get("width_m", d.get("width_m", 0.6))),
            height_m=float(data.get("height_m", d.get("height_m", 1.2))),
            sill_height_above_ffl_m=float(data.get("sill_height_above_ffl_m", d.get("sill_height_above_ffl_m", 0.9))),
            head_height_above_ffl_m=float(data.get("head_height_above_ffl_m", d.get("head_height_above_ffl_m", 2.1))),
            material=str(data.get("material", d.get("material", "Wall bucky / vertical image receptor"))),
            id=str(data.get("id", "WB1")),
        )


@dataclass
class BuckyShield:
    """Fixed shielding panel associated with a General X-ray Chest Bucky.

    XR-19B credits this fixed panel to the primary Chest Bucky component when
    its persisted geometry exactly matches the canonical 1.2 m / 2.2 mm Pb shield.
    """
    wall: WallOrientation = "N"
    offset_m: float = 1.0
    width_m: float = 1.2
    material: str = "Pb"
    thickness_mm: float = 2.2
    id: str = "BS1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BuckyShield":
        return BuckyShield(
            wall=str(data.get("wall", "N") or "N").upper(),
            offset_m=float(data.get("offset_m", 1.0)),
            width_m=1.2,
            material="Pb",
            thickness_mm=2.2,
            id=str(data.get("id", "BS1") or "BS1"),
        )


@dataclass
class ControlWall:
    center_x_m: float = 1.0
    center_y_m: float = 1.0
    length_m: float = 1.5
    orientation_deg: int = 0
    nib_length_m: float = 0.75
    material: str = "Pb"
    thickness_mm: float = 0.88
    occupancy_factor: float = 1.0
    design_goal_uSv_per_week: float = 100.0
    id: str = "CW1"

    def source_distance_m(self, source_x_m: float, source_y_m: float) -> float:
        """Shortest plan-view distance from a source point to the finite main wall segment.

        XR-15B deliberately uses the main control-wall barrier only; the 45-degree
        nibs are drawing/return geometry and are not separate shielding barriers.
        Orientations 0/180 share the same horizontal segment and 90/270 the same
        vertical segment, while retaining the full orientation for rendering.
        """
        half = max(0.05, float(self.length_m) / 2.0)
        x = float(source_x_m)
        y = float(source_y_m)
        orientation = int(float(self.orientation_deg or 0)) % 360
        if orientation in (0, 180):
            nearest_x = min(max(x, float(self.center_x_m) - half), float(self.center_x_m) + half)
            nearest_y = float(self.center_y_m)
        elif orientation in (90, 270):
            nearest_x = float(self.center_x_m)
            nearest_y = min(max(y, float(self.center_y_m) - half), float(self.center_y_m) + half)
        else:
            raise ValueError("Control wall orientation must be 0, 90, 180, or 270 degrees.")
        dx = x - nearest_x
        dy = y - nearest_y
        return (dx * dx + dy * dy) ** 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ControlWall":
        return ControlWall(
            center_x_m=float(data.get("center_x_m", 1.0)),
            center_y_m=float(data.get("center_y_m", 1.0)),
            length_m=max(0.1, float(data.get("length_m", 1.5))),
            orientation_deg=int(float(data.get("orientation_deg", 0) or 0)) % 360,
            nib_length_m=max(0.0, float(data.get("nib_length_m", 0.75) or 0.0)),
            material=str(data.get("material", "Pb") or "Pb"),
            thickness_mm=max(0.0, float(data.get("thickness_mm", 0.88) or 0.0)),
            occupancy_factor=max(0.0, min(1.0, float(data.get("occupancy_factor", 1.0) or 0.0))),
            design_goal_uSv_per_week=max(0.0, float(data.get("design_goal_uSv_per_week", 100.0) or 0.0)),
            id=str(data.get("id", "CW1") or "CW1"),
        )


@dataclass
class RadiationSourceGeometry:
    label: str = "CT"
    x_m: float = DEFAULT_SOURCE_X_M
    y_m: float = DEFAULT_SOURCE_Y_M
    rotation_deg: int = 0
    # Transient, modality-owned values used only by renderers.  Keeping them
    # in a generic mapping prevents scanner, ksec, or radionuclide fields from
    # becoming part of the shared geometry/domain schema.  Deliberately omitted
    # from to_dict()/from_dict() so project files and report payloads are stable.
    render_metadata: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "x_m": self.x_m,
            "y_m": self.y_m,
            "rotation_deg": self.rotation_deg,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RadiationSourceGeometry":
        return RadiationSourceGeometry(
            label=str(data.get("label", "CT")),
            x_m=float(data.get("x_m", DEFAULT_SOURCE_X_M)),
            y_m=float(data.get("y_m", DEFAULT_SOURCE_Y_M)),
            rotation_deg=int(float(data.get("rotation_deg", 0) or 0)) % 360,
        )


@dataclass
class RoomGeometry:
    room_name: str = "CT Room 1"
    length_m: float = DEFAULT_ROOM_LENGTH_M
    width_m: float = DEFAULT_ROOM_WIDTH_M
    height_m: float = DEFAULT_ROOM_HEIGHT_M
    source: RadiationSourceGeometry = field(default_factory=RadiationSourceGeometry)
    openings: List[Opening] = field(default_factory=list)
    wall_bucky: Optional[WallBucky] = None
    bucky_shield: Optional[BuckyShield] = None
    control_wall: Optional[ControlWall] = None

    def source_to_barrier_distances(self) -> Dict[str, float]:
        self.clamp_source_inside_room()
        return {
            "N": max(0.0, self.length_m - self.source.y_m),
            "S": max(0.0, self.source.y_m),
            "E": max(0.0, self.width_m - self.source.x_m),
            "W": max(0.0, self.source.x_m),
        }

    def external_wall_ray(self, wall: WallOrientation) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return the deterministic plan-view source ray to an external wall.

        XR-17A uses the perpendicular point on the selected room boundary, matching
        the source-to-wall distance convention already used by the GXR barrier
        schedule.  This is geometry only; no attenuation credit is applied here.
        """
        self.clamp_source_inside_room()
        wall = str(wall or "").upper()
        sx, sy = float(self.source.x_m), float(self.source.y_m)
        targets = {
            "N": (sx, float(self.length_m)),
            "S": (sx, 0.0),
            "E": (float(self.width_m), sy),
            "W": (0.0, sy),
        }
        if wall not in targets:
            raise ValueError("External wall must be N, E, S, or W.")
        return (sx, sy), targets[wall]

    def opening_center_point(self, opening: Opening) -> tuple[float, float]:
        """Return the deterministic plan-view centre point of a wall opening.

        ``Opening.offset_m`` is the centre distance along its parent wall.
        """
        wall = str(getattr(opening, "wall", "") or "").strip().upper()
        offset = float(getattr(opening, "offset_m", 0.0) or 0.0)
        if wall == "N":
            return offset, float(self.length_m)
        if wall == "S":
            return offset, 0.0
        if wall == "E":
            return float(self.width_m), offset
        if wall == "W":
            return 0.0, offset
        raise ValueError("Opening wall must be N, E, S, or W.")

    def source_to_opening_distance_m(self, opening: Opening) -> float:
        """Plan-view source-to-centre distance for an opening sub-barrier."""
        self.clamp_source_inside_room()
        tx, ty = self.opening_center_point(opening)
        dx = tx - float(self.source.x_m)
        dy = ty - float(self.source.y_m)
        return (dx * dx + dy * dy) ** 0.5

    def control_wall_intercepts_opening_ray(self, opening: Opening) -> bool:
        """Whether the source-to-opening-centre ray crosses the finite Control Wall.

        This is intentionally opening-specific: an opening may be intercepted even
        when another point on its parent wall is not, and vice versa.  As for the
        qualified external-wall geometry, only the finite main Control Wall segment
        receives shielding credit; the 45-degree nibs are excluded.
        """
        control = self.control_wall
        if control is None:
            return False
        self.clamp_source_inside_room()
        sx, sy = float(self.source.x_m), float(self.source.y_m)
        tx, ty = self.opening_center_point(opening)
        half = max(0.05, float(control.length_m) / 2.0)
        orientation = int(float(control.orientation_deg or 0)) % 360
        eps = 1e-9
        if orientation in (0, 180):
            cy = float(control.center_y_m)
            dy = ty - sy
            if abs(dy) <= eps:
                return False
            u = (cy - sy) / dy
            if u <= eps or u > 1.0 + eps:
                return False
            x = sx + u * (tx - sx)
            return float(control.center_x_m) - half - eps <= x <= float(control.center_x_m) + half + eps
        if orientation in (90, 270):
            cx = float(control.center_x_m)
            dx = tx - sx
            if abs(dx) <= eps:
                return False
            u = (cx - sx) / dx
            if u <= eps or u > 1.0 + eps:
                return False
            y = sy + u * (ty - sy)
            return float(control.center_y_m) - half - eps <= y <= float(control.center_y_m) + half + eps
        raise ValueError("Control wall orientation must be 0, 90, 180, or 270 degrees.")

    def control_wall_intercepts_external_wall_ray(self, wall: WallOrientation) -> bool:
        """Whether the finite main Control Wall segment intercepts the wall ray.

        End-point contact counts as interception.  The 45-degree nibs remain
        excluded from shielding geometry, consistent with XR-15B.
        """
        control = self.control_wall
        if control is None:
            return False

        (sx, sy), (tx, ty) = self.external_wall_ray(wall)
        half = max(0.05, float(control.length_m) / 2.0)
        orientation = int(float(control.orientation_deg or 0)) % 360
        eps = 1e-9

        if orientation in (0, 180):
            # Horizontal finite segment: y = cy, x in [cx-half, cx+half].
            cy = float(control.center_y_m)
            dy = ty - sy
            if abs(dy) <= eps:
                return False
            u = (cy - sy) / dy
            if u <= eps or u > 1.0 + eps:
                return False
            x = sx + u * (tx - sx)
            return float(control.center_x_m) - half - eps <= x <= float(control.center_x_m) + half + eps

        if orientation in (90, 270):
            # Vertical finite segment: x = cx, y in [cy-half, cy+half].
            cx = float(control.center_x_m)
            dx = tx - sx
            if abs(dx) <= eps:
                return False
            u = (cx - sx) / dx
            if u <= eps or u > 1.0 + eps:
                return False
            y = sy + u * (ty - sy)
            return float(control.center_y_m) - half - eps <= y <= float(control.center_y_m) + half + eps

        raise ValueError("Control wall orientation must be 0, 90, 180, or 270 degrees.")

    def clamp_source_inside_room(self) -> None:
        self.length_m = max(0.01, float(self.length_m))
        self.width_m = max(0.01, float(self.width_m))
        self.source.x_m = min(max(float(self.source.x_m), 0.0), self.width_m)
        self.source.y_m = min(max(float(self.source.y_m), 0.0), self.length_m)


    def set_source_centre(self) -> None:
        self.source.x_m = self.width_m / 2.0
        self.source.y_m = self.length_m / 2.0


    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_name": self.room_name,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "source": self.source.to_dict(),
            "openings": [o.to_dict() for o in self.openings],
            "wall_bucky": self.wall_bucky.to_dict() if self.wall_bucky else None,
            "bucky_shield": self.bucky_shield.to_dict() if self.bucky_shield else None,
            "control_wall": self.control_wall.to_dict() if self.control_wall else None,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RoomGeometry":
        source_data = data.get("source", {}) or {}
        openings_data = data.get("openings", []) or []
        wall_bucky_data = data.get("wall_bucky", None)
        bucky_shield_data = data.get("bucky_shield", None)
        control_wall_data = data.get("control_wall", None)
        wall_bucky = WallBucky.from_dict(wall_bucky_data) if isinstance(wall_bucky_data, dict) else None
        bucky_shield = BuckyShield.from_dict(bucky_shield_data) if isinstance(bucky_shield_data, dict) else None
        return RoomGeometry(
            room_name=str(data.get("room_name", "CT Room 1")),
            length_m=float(data.get("length_m", DEFAULT_ROOM_LENGTH_M)),
            width_m=float(data.get("width_m", DEFAULT_ROOM_WIDTH_M)),
            height_m=float(data.get("height_m", DEFAULT_ROOM_HEIGHT_M)),
            source=RadiationSourceGeometry.from_dict(source_data),
            openings=[Opening.from_dict(o) for o in openings_data if isinstance(o, dict)],
            wall_bucky=wall_bucky,
            bucky_shield=bucky_shield,
            control_wall=ControlWall.from_dict(control_wall_data) if isinstance(control_wall_data, dict) else None,
        )
