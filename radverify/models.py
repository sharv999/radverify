from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List

from geometry.geometry_model import Opening, RadiationSourceGeometry, RoomGeometry


BARRIER_IDS = ("N wall", "E wall", "S wall", "W wall", "Floor", "Ceiling")
STATUS_OPTIONS = ("Not inspected", "Pass", "Review", "Fail", "N/A")


@dataclass
class RoomDetails:
    project_id: str = "RV-001"
    site_name: str = ""
    building: str = ""
    room_name: str = "Imaging Room 1"
    room_type: str = "CT"
    room_number: str = ""
    inspector: str = ""
    inspection_date: str = field(default_factory=lambda: date.today().isoformat())
    drawing_reference: str = ""
    notes: str = ""


@dataclass
class BarrierInspection:
    barrier_id: str
    barrier_type: str = "Wall"
    expected_construction: str = ""
    observed_construction: str = ""
    expected_pb_mm: float | None = None
    observed_pb_mm: float | None = None
    status: str = "Not inspected"
    evidence_ref: str = ""
    notes: str = ""

    def risk_state(self) -> str:
        mapping = {
            "pass": "pass",
            "review": "review",
            "fail": "fail",
            "not inspected": "not_inspected",
            "n/a": "n_a",
        }
        return mapping.get(self.status.strip().lower(), "not_inspected")


@dataclass
class MeasurementPoint:
    point_id: str
    x_m: float
    y_m: float
    height_m: float = 1.0
    location: str = ""
    instrument: str = ""
    measurement_type: str = "Ambient dose rate"
    reading_uSv_h: float | None = None
    background_uSv_h: float | None = None
    corrected_uSv_h: float | None = None
    status: str = "Not assessed"
    notes: str = ""

    def recalculate(self) -> None:
        if self.reading_uSv_h is None:
            self.corrected_uSv_h = None
            return
        background = self.background_uSv_h or 0.0
        self.corrected_uSv_h = max(0.0, self.reading_uSv_h - background)


@dataclass
class RadVerifyProject:
    schema_version: str = "radverify-0.1"
    details: RoomDetails = field(default_factory=RoomDetails)
    geometry: RoomGeometry = field(
        default_factory=lambda: RoomGeometry(
            room_name="Imaging Room 1",
            length_m=4.0,
            width_m=6.0,
            height_m=2.7,
            source=RadiationSourceGeometry(label=""),
        )
    )
    barriers: List[BarrierInspection] = field(default_factory=list)
    measurements: List[MeasurementPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.barriers:
            self.barriers = [
                BarrierInspection(barrier_id=bid, barrier_type=("Slab" if bid in {"Floor", "Ceiling"} else "Wall"))
                for bid in BARRIER_IDS
            ]
        self.sync_opening_inspections()

    def sync_opening_inspections(self) -> None:
        existing = {b.barrier_id: b for b in self.barriers}
        desired_ids = list(BARRIER_IDS)
        for index, opening in enumerate(self.geometry.openings, start=1):
            oid = opening.id.strip() if getattr(opening, "id", "") else f"{opening.wall}-{opening.opening_type}-{index}"
            desired_ids.append(oid)
            if oid not in existing:
                kind = "Viewing panel" if opening.opening_type in {"viewing_panel", "lead_glass", "vp", "pb_glass"} else "Door"
                self.barriers.append(
                    BarrierInspection(
                        barrier_id=oid,
                        barrier_type=kind,
                        expected_construction=str(getattr(opening, "material", "") or ""),
                        expected_pb_mm=float(getattr(opening, "pb_equiv_mm", 0.0) or 0.0) or None,
                    )
                )
        # Retain wall/slab records and only current opening records.
        self.barriers = [b for b in self.barriers if b.barrier_id in desired_ids]

    def to_dict(self) -> Dict[str, Any]:
        self.sync_opening_inspections()
        return {
            "schema_version": self.schema_version,
            "details": asdict(self.details),
            "geometry": self.geometry.to_dict(),
            "barrier_inspection": [asdict(b) for b in self.barriers],
            "measurement_points": [asdict(m) for m in self.measurements],
            "radstatus_payload": self.to_radstatus_payload(),
        }

    def to_radstatus_payload(self) -> Dict[str, Any]:
        """Stable hand-off boundary for the future RadStatus application."""
        counts = {"pass": 0, "review": 0, "fail": 0, "not_inspected": 0}
        for barrier in self.barriers:
            key = barrier.status.strip().lower().replace(" ", "_")
            if key in counts:
                counts[key] += 1
        return {
            "schema": "radstatus-ingest-0.1-draft",
            "project_id": self.details.project_id,
            "site_name": self.details.site_name,
            "room_name": self.details.room_name,
            "room_type": self.details.room_type,
            "inspection_date": self.details.inspection_date,
            "barrier_summary": counts,
            "barriers": [
                {
                    "barrier_id": b.barrier_id,
                    "barrier_type": b.barrier_type,
                    "status": b.status,
                    "observed_construction": b.observed_construction,
                    "observed_pb_mm": b.observed_pb_mm,
                    "evidence_ref": b.evidence_ref,
                    "notes": b.notes,
                }
                for b in self.barriers
            ],
            "measurement_points": [asdict(m) for m in self.measurements],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RadVerifyProject":
        details = RoomDetails(**{k: v for k, v in (data.get("details") or {}).items() if k in RoomDetails.__dataclass_fields__})
        geom = RoomGeometry.from_dict(data.get("geometry") or {})
        barriers = []
        for raw in data.get("barrier_inspection", data.get("barriers", [])) or []:
            cleaned = {k: v for k, v in raw.items() if k in BarrierInspection.__dataclass_fields__}
            if cleaned.get("barrier_id"):
                barriers.append(BarrierInspection(**cleaned))
        measurements = []
        for raw in data.get("measurement_points", data.get("measurements", [])) or []:
            cleaned = {k: v for k, v in raw.items() if k in MeasurementPoint.__dataclass_fields__}
            if cleaned.get("point_id"):
                mp = MeasurementPoint(**cleaned)
                mp.recalculate()
                measurements.append(mp)
        project = cls(
            schema_version=str(data.get("schema_version", "radverify-0.1")),
            details=details,
            geometry=geom,
            barriers=barriers,
            measurements=measurements,
        )
        project.sync_opening_inspections()
        return project
