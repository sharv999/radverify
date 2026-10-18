from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
import hashlib
from pathlib import Path
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
class EvidenceItem:
    evidence_id: str
    evidence_type: str = "Photo"
    reference: str = ""
    file_path: str = ""
    sha256: str = ""
    inspection_date: str = ""
    inspector: str = ""
    description: str = ""

    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        path = Path(file_path)
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def refresh_hash(self) -> str:
        if not self.file_path:
            self.sha256 = ""
            return self.sha256
        self.sha256 = self.calculate_sha256(self.file_path)
        return self.sha256

    def integrity_status(self) -> str:
        if not self.file_path:
            return "Reference only"
        path = Path(self.file_path)
        if not path.exists():
            return "File missing"
        if not self.sha256:
            return "Hash not recorded"
        try:
            current = self.calculate_sha256(self.file_path)
        except OSError:
            return "File unreadable"
        return "Verified" if current == self.sha256 else "File changed"


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
    evidence_items: List[EvidenceItem] = field(default_factory=list)
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
class MeasurementRecord:
    record_id: str
    measured_at: str = ""
    instrument: str = ""
    instrument_id: str = ""
    serial_number: str = ""
    calibration_date: str = ""
    calibration_due_date: str = ""
    calibration_reference: str = ""
    measurement_type: str = "Ambient dose rate"
    field_conditions: str = ""
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

    def calibration_status(self, reference_date: str | None = None) -> str:
        if not self.calibration_due_date:
            return "Not recorded"
        try:
            due = date.fromisoformat(self.calibration_due_date[:10])
            reference = date.fromisoformat((reference_date or self.measured_at or date.today().isoformat())[:10])
        except (TypeError, ValueError):
            return "Invalid date"
        return "Current" if reference <= due else "Expired"


@dataclass
class MeasurementPoint:
    point_id: str
    x_m: float
    y_m: float
    height_m: float = 1.0
    location: str = ""
    instrument: str = ""
    instrument_id: str = ""
    serial_number: str = ""
    calibration_date: str = ""
    calibration_due_date: str = ""
    calibration_reference: str = ""
    measurement_type: str = "Ambient dose rate"
    field_conditions: str = ""
    measured_at: str = ""
    reading_uSv_h: float | None = None
    background_uSv_h: float | None = None
    corrected_uSv_h: float | None = None
    status: str = "Not assessed"
    notes: str = ""
    measurement_history: List[MeasurementRecord] = field(default_factory=list)

    def recalculate(self) -> None:
        if self.reading_uSv_h is None:
            self.corrected_uSv_h = None
            return
        background = self.background_uSv_h or 0.0
        self.corrected_uSv_h = max(0.0, self.reading_uSv_h - background)

    def next_record_id(self) -> str:
        used = {record.record_id for record in self.measurement_history}
        i = 1
        while f"{self.point_id}-M{i:02d}" in used:
            i += 1
        return f"{self.point_id}-M{i:02d}"

    def calibration_status(self, reference_date: str | None = None) -> str:
        record = MeasurementRecord(
            record_id="_status",
            measured_at=reference_date or self.measured_at,
            calibration_due_date=self.calibration_due_date,
        )
        return record.calibration_status(reference_date=reference_date)

    def add_measurement_record(self, record: MeasurementRecord) -> None:
        if not record.record_id:
            record.record_id = self.next_record_id()
        if not record.measured_at:
            record.measured_at = datetime.now().isoformat(timespec="minutes")
        record.recalculate()
        self.measurement_history.append(record)
        self.apply_record_as_latest(record)

    def apply_record_as_latest(self, record: MeasurementRecord) -> None:
        self.measured_at = record.measured_at
        self.instrument = record.instrument
        self.instrument_id = record.instrument_id
        self.serial_number = record.serial_number
        self.calibration_date = record.calibration_date
        self.calibration_due_date = record.calibration_due_date
        self.calibration_reference = record.calibration_reference
        self.measurement_type = record.measurement_type
        self.field_conditions = record.field_conditions
        self.reading_uSv_h = record.reading_uSv_h
        self.background_uSv_h = record.background_uSv_h
        self.corrected_uSv_h = record.corrected_uSv_h
        self.status = record.status
        self.notes = record.notes

    def latest_record(self) -> MeasurementRecord | None:
        return self.measurement_history[-1] if self.measurement_history else None

    def sync_latest_from_history(self) -> None:
        latest = self.latest_record()
        if latest is not None:
            self.apply_record_as_latest(latest)
            return
        self.measured_at = ""
        self.reading_uSv_h = None
        self.background_uSv_h = None
        self.corrected_uSv_h = None
        self.status = "Not assessed"
        self.notes = ""


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

    def verification_summary(self, reference_date: str | None = None) -> Dict[str, Any]:
        """Return a derived room-level verification/readiness summary.

        This is intentionally a workflow summary, not an independent regulatory
        compliance determination.  ``radstatus_ready`` means the verification
        dataset is complete enough to hand off to RadStatus; it can still be
        ready when the room outcome is Review or Fail.
        """
        self.sync_opening_inspections()
        reference_date = reference_date or self.details.inspection_date or date.today().isoformat()

        barrier_counts = {
            "pass": 0, "review": 0, "fail": 0, "not_inspected": 0, "n_a": 0,
        }
        applicable_barriers = 0
        as_built_complete = 0
        evidence_complete = 0
        evidence_integrity_issues = 0
        issues: List[Dict[str, str]] = []

        def add_issue(severity: str, area: str, item_id: str, issue: str) -> None:
            issues.append({
                "severity": severity,
                "area": area,
                "item_id": item_id,
                "issue": issue,
            })

        for barrier in self.barriers:
            status_key = barrier.status.strip().lower().replace("/", "_").replace(" ", "_")
            if status_key == "n_a":
                barrier_counts["n_a"] += 1
                continue
            applicable_barriers += 1
            if status_key not in barrier_counts:
                status_key = "not_inspected"
            barrier_counts[status_key] += 1

            if status_key == "fail":
                add_issue("Fail", "Barrier", barrier.barrier_id, "Verification status is Fail")
            elif status_key == "review":
                add_issue("Review", "Barrier", barrier.barrier_id, "Verification status requires review")
            elif status_key == "not_inspected":
                add_issue("Incomplete", "Barrier", barrier.barrier_id, "Not inspected")

            has_as_built = bool(barrier.observed_construction.strip()) or barrier.observed_pb_mm is not None
            if has_as_built:
                as_built_complete += 1
            elif status_key != "not_inspected":
                add_issue("Incomplete", "Barrier", barrier.barrier_id, "As-built construction not recorded")

            has_evidence = bool(barrier.evidence_ref.strip()) or bool(barrier.evidence_items)
            if has_evidence:
                evidence_complete += 1
            elif status_key != "not_inspected":
                add_issue("Incomplete", "Evidence", barrier.barrier_id, "No inspection evidence recorded")

            for evidence in barrier.evidence_items:
                integrity = evidence.integrity_status()
                if evidence.file_path and integrity != "Verified":
                    evidence_integrity_issues += 1
                    add_issue("Review", "Evidence", barrier.barrier_id, f"{evidence.evidence_id}: {integrity}")

        measurement_counts = {"pass": 0, "review": 0, "fail": 0, "not_assessed": 0}
        points_recorded = 0
        points_calibration_current = 0
        points_assessed = 0
        if not self.measurements:
            add_issue("Incomplete", "Measurement", "Room", "No measurement points recorded")

        for point in self.measurements:
            has_measurement = bool(point.measurement_history) or point.reading_uSv_h is not None
            if has_measurement:
                points_recorded += 1
            else:
                add_issue("Incomplete", "Measurement", point.point_id, "No measurement reading recorded")

            status_key = point.status.strip().lower().replace(" ", "_")
            if status_key not in measurement_counts:
                status_key = "not_assessed"
            measurement_counts[status_key] += 1
            if status_key != "not_assessed":
                points_assessed += 1
            if status_key == "fail":
                add_issue("Fail", "Measurement", point.point_id, "Latest measurement status is Fail")
            elif status_key == "review":
                add_issue("Review", "Measurement", point.point_id, "Latest measurement requires review")
            elif status_key == "not_assessed":
                add_issue("Incomplete", "Measurement", point.point_id, "Latest measurement is not assessed")

            calibration_reference = point.measured_at or reference_date
            calibration = point.calibration_status(calibration_reference)
            if calibration == "Current":
                points_calibration_current += 1
            elif calibration == "Expired":
                add_issue("Review", "Calibration", point.point_id, "Instrument calibration is expired")
            else:
                add_issue("Incomplete", "Calibration", point.point_id, f"Instrument calibration: {calibration}")

        has_fail = barrier_counts["fail"] > 0 or measurement_counts["fail"] > 0
        has_review = (
            barrier_counts["review"] > 0
            or measurement_counts["review"] > 0
            or evidence_integrity_issues > 0
            or any(issue["area"] == "Calibration" and issue["severity"] == "Review" for issue in issues)
        )
        has_incomplete = any(issue["severity"] == "Incomplete" for issue in issues)

        if has_fail:
            verification_state = "Failed"
        elif has_review:
            verification_state = "Review required"
        elif has_incomplete:
            verification_state = "Incomplete"
        else:
            verification_state = "Verified"

        # Readiness is a data-completeness gate, separate from the room outcome.
        # A fully documented Fail/Review package is still ready for RadStatus.
        radstatus_ready = not has_incomplete and evidence_integrity_issues == 0

        return {
            "verification_state": verification_state,
            "radstatus_ready": radstatus_ready,
            "reference_date": reference_date,
            "barriers": {
                "total": len(self.barriers),
                "applicable": applicable_barriers,
                **barrier_counts,
                "as_built_complete": as_built_complete,
                "evidence_complete": evidence_complete,
                "evidence_integrity_issues": evidence_integrity_issues,
            },
            "measurements": {
                "points_total": len(self.measurements),
                "points_recorded": points_recorded,
                "points_assessed": points_assessed,
                "calibration_current": points_calibration_current,
                **measurement_counts,
            },
            "issues": issues,
        }

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
            "verification_summary": self.verification_summary(),
            "barrier_summary": counts,
            "barriers": [
                {
                    "barrier_id": b.barrier_id,
                    "barrier_type": b.barrier_type,
                    "status": b.status,
                    "observed_construction": b.observed_construction,
                    "observed_pb_mm": b.observed_pb_mm,
                    "evidence_ref": b.evidence_ref,
                    "evidence": [asdict(item) for item in b.evidence_items],
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
            cleaned = {k: v for k, v in raw.items() if k in BarrierInspection.__dataclass_fields__ and k != "evidence_items"}
            evidence_raw = raw.get("evidence_items", raw.get("evidence", [])) or []
            evidence_items = []
            for item in evidence_raw:
                if not isinstance(item, dict):
                    continue
                item_cleaned = {k: v for k, v in item.items() if k in EvidenceItem.__dataclass_fields__}
                if item_cleaned.get("evidence_id"):
                    evidence_items.append(EvidenceItem(**item_cleaned))
            if cleaned.get("barrier_id"):
                barriers.append(BarrierInspection(**cleaned, evidence_items=evidence_items))
        measurements = []
        for raw in data.get("measurement_points", data.get("measurements", [])) or []:
            if not isinstance(raw, dict):
                continue
            cleaned = {
                k: v
                for k, v in raw.items()
                if k in MeasurementPoint.__dataclass_fields__ and k != "measurement_history"
            }
            history = []
            for item in raw.get("measurement_history", raw.get("history", [])) or []:
                if not isinstance(item, dict):
                    continue
                item_cleaned = {k: v for k, v in item.items() if k in MeasurementRecord.__dataclass_fields__}
                if item_cleaned.get("record_id"):
                    record = MeasurementRecord(**item_cleaned)
                    record.recalculate()
                    history.append(record)
            if cleaned.get("point_id"):
                mp = MeasurementPoint(**cleaned, measurement_history=history)
                mp.recalculate()
                if history:
                    mp.apply_record_as_latest(history[-1])
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
