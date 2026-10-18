from __future__ import annotations

"""Radiation Room Digital Twin interchange contract.

This module is intentionally small and product-neutral at the JSON boundary.
RadVerify keeps its native ``*.radverify.json`` project file; ``*.radtwin.json``
is the portable room record intended to be shared with RadShield and RadStatus.
"""

from dataclasses import asdict
from typing import Any, Dict, Iterable

from geometry.geometry_model import (
    BuckyShield,
    ControlWall,
    Opening,
    RadiationSourceGeometry,
    RoomGeometry,
    WallBucky,
)
from radverify.models import BARRIER_IDS, BarrierInspection, EvidenceItem, MeasurementPoint, MeasurementRecord, RadVerifyProject, RoomDetails


RADTWIN_SCHEMA = "radiation-room-digital-twin-0.1"
RADTWIN_EXTENSION = ".radtwin.json"
RADTWIN_PRODUCER = "RadVerify"
RADTWIN_PRODUCER_VERSION = "0.3-step4"


class RadTwinValidationError(ValueError):
    """Raised when a portable room-twin payload cannot be safely interpreted."""


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _wall_orientation(barrier_id: str) -> str | None:
    lookup = {"N wall": "N", "E wall": "E", "S wall": "S", "W wall": "W"}
    return lookup.get(barrier_id)


def _geometry_ref(barrier_id: str) -> str:
    wall = _wall_orientation(barrier_id)
    if wall:
        return f"wall:{wall}"
    if barrier_id == "Floor":
        return "surface:floor"
    if barrier_id == "Ceiling":
        return "surface:ceiling"
    return f"opening:{barrier_id}"


def _opening_to_twin(opening: Opening) -> Dict[str, Any]:
    return {
        "id": opening.id or opening.label,
        "wall": opening.wall,
        "opening_type": opening.opening_type,
        "offset_m": float(opening.offset_m),
        "width_m": float(opening.width_m),
        "label": opening.label,
        "vertical_extent_m": {
            "sill": float(opening.sill_height_above_ffl_m),
            "head": float(opening.head_height_above_ffl_m),
        },
        "physical_specification": {
            "material": opening.material,
            "pb_equivalent_mm": float(opening.pb_equiv_mm),
            "kvp_basis": opening.kvp_basis,
        },
    }


def _opening_from_twin(data: Dict[str, Any]) -> Opening:
    vertical = data.get("vertical_extent_m") or {}
    physical = data.get("physical_specification") or {}
    return Opening(
        wall=str(data.get("wall", "N") or "N").upper(),
        opening_type=str(data.get("opening_type", "door") or "door"),
        offset_m=float(data.get("offset_m", 1.0)),
        width_m=float(data.get("width_m", 0.9)),
        label=str(data.get("label", "") or ""),
        pb_equiv_mm=float(physical.get("pb_equivalent_mm", data.get("pb_equiv_mm", 0.0)) or 0.0),
        material=str(physical.get("material", data.get("material", "")) or ""),
        sill_height_above_ffl_m=float(vertical.get("sill", data.get("sill_height_above_ffl_m", 0.0)) or 0.0),
        head_height_above_ffl_m=float(vertical.get("head", data.get("head_height_above_ffl_m", 2.1)) or 2.1),
        kvp_basis=_as_float(physical.get("kvp_basis", data.get("kvp_basis"))),
        id=str(data.get("id", "") or ""),
    )


def _fixed_features_to_twin(geometry: RoomGeometry) -> list[Dict[str, Any]]:
    features: list[Dict[str, Any]] = []
    if geometry.wall_bucky is not None:
        features.append({"feature_type": "wall_bucky", **geometry.wall_bucky.to_dict()})
    if geometry.bucky_shield is not None:
        features.append({"feature_type": "bucky_shield", **geometry.bucky_shield.to_dict()})
    if geometry.control_wall is not None:
        features.append({"feature_type": "control_wall", **geometry.control_wall.to_dict()})
    return features


def _fixed_features_from_twin(features: Iterable[Dict[str, Any]]) -> tuple[WallBucky | None, BuckyShield | None, ControlWall | None]:
    wall_bucky = None
    bucky_shield = None
    control_wall = None
    for raw in features:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("feature_type", "") or "").strip().lower()
        data = {k: v for k, v in raw.items() if k != "feature_type"}
        if kind == "wall_bucky":
            wall_bucky = WallBucky.from_dict(data)
        elif kind == "bucky_shield":
            bucky_shield = BuckyShield.from_dict(data)
        elif kind == "control_wall":
            control_wall = ControlWall.from_dict(data)
    return wall_bucky, bucky_shield, control_wall


def _primary_equipment(project: RadVerifyProject) -> list[Dict[str, Any]]:
    source = project.geometry.source
    label = source.label or project.details.room_type or "Primary source"
    return [
        {
            "id": "primary-source",
            "role": "primary_radiation_source",
            "equipment_type": project.details.room_type,
            "label": label,
            "position_m": {"x": float(source.x_m), "y": float(source.y_m)},
            "rotation_deg": int(source.rotation_deg),
        }
    ]


def _barrier_to_twin(barrier: BarrierInspection) -> Dict[str, Any]:
    return {
        "id": barrier.barrier_id,
        "barrier_type": barrier.barrier_type,
        "geometry_ref": _geometry_ref(barrier.barrier_id),
        "design_specification": {
            "construction": barrier.expected_construction,
            "pb_equivalent_mm": barrier.expected_pb_mm,
        },
        "as_built": {
            "construction": barrier.observed_construction,
            "pb_equivalent_mm": barrier.observed_pb_mm,
        },
        "verification": {
            "status": barrier.status,
            "evidence_ref": barrier.evidence_ref,
            "evidence": [asdict(item) for item in barrier.evidence_items],
            "notes": barrier.notes,
        },
    }


def project_to_radtwin(project: RadVerifyProject) -> Dict[str, Any]:
    """Return the neutral Radiation Room Digital Twin representation."""
    project.sync_opening_inspections()
    details = project.details
    geometry = project.geometry
    return {
        "schema": RADTWIN_SCHEMA,
        "twin_id": details.project_id or details.room_name or "radiation-room",
        "provenance": {
            "producer": RADTWIN_PRODUCER,
            "producer_version": RADTWIN_PRODUCER_VERSION,
        },
        "room": {
            "project_id": details.project_id,
            "site_name": details.site_name,
            "building": details.building,
            "level": "",
            "room_name": details.room_name,
            "room_number": details.room_number,
            "room_type": details.room_type,
        },
        "geometry": {
            "coordinate_system": {
                "origin": "south-west floor corner",
                "x_axis": "west_to_east",
                "y_axis": "south_to_north",
                "z_axis": "up_from_finished_floor_level",
                "units": "m",
            },
            "dimensions_m": {
                "south_north": float(geometry.length_m),
                "west_east": float(geometry.width_m),
                "height": float(geometry.height_m),
            },
            "openings": [_opening_to_twin(o) for o in geometry.openings],
            "fixed_features": _fixed_features_to_twin(geometry),
        },
        "equipment": _primary_equipment(project),
        "barriers": [_barrier_to_twin(b) for b in project.barriers],
        "inspection": {
            "inspector": details.inspector,
            "inspection_date": details.inspection_date,
            "drawing_reference": details.drawing_reference,
            "notes": details.notes,
        },
        "measurement_points": [asdict(m) for m in project.measurements],
        "verification_summary": project.verification_summary(),
    }


def validate_radtwin(data: Dict[str, Any]) -> None:
    """Perform the dependency-free minimum validation used by the applications.

    The full machine-readable JSON Schema lives under ``docs/radtwin``.  This
    runtime validator intentionally checks only the interoperability-critical
    fields so neither RadVerify nor RadShield needs a JSON Schema dependency.
    """
    if not isinstance(data, dict):
        raise RadTwinValidationError("Digital twin must be a JSON object.")
    if data.get("schema") != RADTWIN_SCHEMA:
        raise RadTwinValidationError(
            f"Unsupported digital twin schema: {data.get('schema')!r}. Expected {RADTWIN_SCHEMA!r}."
        )
    room = data.get("room")
    geometry = data.get("geometry")
    if not isinstance(room, dict):
        raise RadTwinValidationError("Digital twin is missing the room object.")
    if not isinstance(geometry, dict):
        raise RadTwinValidationError("Digital twin is missing the geometry object.")
    dimensions = geometry.get("dimensions_m")
    if not isinstance(dimensions, dict):
        raise RadTwinValidationError("Digital twin geometry is missing dimensions_m.")
    for key in ("south_north", "west_east", "height"):
        value = _as_float(dimensions.get(key))
        if value is None or value <= 0:
            raise RadTwinValidationError(f"Digital twin dimension {key!r} must be greater than zero.")
    openings = geometry.get("openings", [])
    if not isinstance(openings, list):
        raise RadTwinValidationError("Digital twin geometry.openings must be an array.")
    for index, opening in enumerate(openings, start=1):
        if not isinstance(opening, dict):
            raise RadTwinValidationError(f"Opening {index} must be an object.")
        if str(opening.get("wall", "")).upper() not in {"N", "E", "S", "W"}:
            raise RadTwinValidationError(f"Opening {index} has an invalid wall orientation.")


def radtwin_to_radshield_geometry(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map a room twin to the existing RadShield ``RoomGeometry`` JSON shape.

    This function is the executable compatibility contract for the future
    RadShield importer.  It does not invoke any shielding calculations.
    """
    validate_radtwin(data)
    room = data.get("room") or {}
    geometry = data.get("geometry") or {}
    dimensions = geometry.get("dimensions_m") or {}

    equipment = data.get("equipment") or []
    primary = next(
        (
            e
            for e in equipment
            if isinstance(e, dict) and str(e.get("role", "")).lower() == "primary_radiation_source"
        ),
        None,
    )
    if primary is None:
        primary = next((e for e in equipment if isinstance(e, dict)), {})
    position = primary.get("position_m") or {}
    width = float(dimensions["west_east"])
    length = float(dimensions["south_north"])
    source = RadiationSourceGeometry(
        label=str(primary.get("label", room.get("room_type", "")) or ""),
        x_m=float(position.get("x", width / 2.0)),
        y_m=float(position.get("y", length / 2.0)),
        rotation_deg=int(float(primary.get("rotation_deg", 0) or 0)) % 360,
    )

    openings = [_opening_from_twin(o) for o in geometry.get("openings", []) if isinstance(o, dict)]
    wall_bucky, bucky_shield, control_wall = _fixed_features_from_twin(geometry.get("fixed_features", []) or [])
    room_geometry = RoomGeometry(
        room_name=str(room.get("room_name", "Radiation Room") or "Radiation Room"),
        length_m=length,
        width_m=width,
        height_m=float(dimensions["height"]),
        source=source,
        openings=openings,
        wall_bucky=wall_bucky,
        bucky_shield=bucky_shield,
        control_wall=control_wall,
    )
    room_geometry.clamp_source_inside_room()
    return room_geometry.to_dict()


def project_from_radtwin(data: Dict[str, Any]) -> RadVerifyProject:
    """Create a RadVerify working project from a neutral room twin."""
    validate_radtwin(data)
    room = data.get("room") or {}
    inspection = data.get("inspection") or {}
    geometry = RoomGeometry.from_dict(radtwin_to_radshield_geometry(data))

    details = RoomDetails(
        project_id=str(room.get("project_id", data.get("twin_id", "RV-001")) or "RV-001"),
        site_name=str(room.get("site_name", "") or ""),
        building=str(room.get("building", "") or ""),
        room_name=str(room.get("room_name", geometry.room_name) or geometry.room_name),
        room_type=str(room.get("room_type", "CT") or "CT"),
        room_number=str(room.get("room_number", "") or ""),
        inspector=str(inspection.get("inspector", "") or ""),
        inspection_date=str(inspection.get("inspection_date", "") or ""),
        drawing_reference=str(inspection.get("drawing_reference", "") or ""),
        notes=str(inspection.get("notes", "") or ""),
    )
    project = RadVerifyProject(details=details, geometry=geometry)
    project.sync_opening_inspections()

    existing = {b.barrier_id: b for b in project.barriers}
    for raw in data.get("barriers", []) or []:
        if not isinstance(raw, dict):
            continue
        barrier_id = str(raw.get("id", "") or "")
        if not barrier_id:
            continue
        if barrier_id not in existing:
            existing[barrier_id] = BarrierInspection(
                barrier_id=barrier_id,
                barrier_type=str(raw.get("barrier_type", "Wall") or "Wall"),
            )
            project.barriers.append(existing[barrier_id])
        barrier = existing[barrier_id]
        barrier.barrier_type = str(raw.get("barrier_type", barrier.barrier_type) or barrier.barrier_type)
        design = raw.get("design_specification") or {}
        as_built = raw.get("as_built") or {}
        verification = raw.get("verification") or {}
        barrier.expected_construction = str(design.get("construction", "") or "")
        barrier.expected_pb_mm = _as_float(design.get("pb_equivalent_mm"))
        barrier.observed_construction = str(as_built.get("construction", "") or "")
        barrier.observed_pb_mm = _as_float(as_built.get("pb_equivalent_mm"))
        barrier.status = str(verification.get("status", "Not inspected") or "Not inspected")
        barrier.evidence_ref = str(verification.get("evidence_ref", "") or "")
        evidence_items = []
        for item in verification.get("evidence", []) or []:
            if not isinstance(item, dict):
                continue
            cleaned = {k: v for k, v in item.items() if k in EvidenceItem.__dataclass_fields__}
            if cleaned.get("evidence_id"):
                evidence_items.append(EvidenceItem(**cleaned))
        barrier.evidence_items = evidence_items
        barrier.notes = str(verification.get("notes", "") or "")

    measurements: list[MeasurementPoint] = []
    for raw in data.get("measurement_points", []) or []:
        if not isinstance(raw, dict):
            continue
        cleaned = {
            k: v
            for k, v in raw.items()
            if k in MeasurementPoint.__dataclass_fields__ and k != "measurement_history"
        }
        if not cleaned.get("point_id"):
            continue
        history: list[MeasurementRecord] = []
        for item in raw.get("measurement_history", raw.get("history", [])) or []:
            if not isinstance(item, dict):
                continue
            item_cleaned = {k: v for k, v in item.items() if k in MeasurementRecord.__dataclass_fields__}
            if not item_cleaned.get("record_id"):
                continue
            record = MeasurementRecord(**item_cleaned)
            record.recalculate()
            history.append(record)
        point = MeasurementPoint(**cleaned, measurement_history=history)
        point.recalculate()
        if history:
            point.apply_record_as_latest(history[-1])
        measurements.append(point)
    project.measurements = measurements
    project.sync_opening_inspections()
    return project
