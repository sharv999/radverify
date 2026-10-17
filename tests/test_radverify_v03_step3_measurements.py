from __future__ import annotations

import pytest

from app import RadVerifyApp
from radverify.models import MeasurementPoint, MeasurementRecord, RadVerifyProject
from radverify.radtwin import project_from_radtwin, project_to_radtwin


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset_app(app):
    project = RadVerifyProject()
    project.details.inspection_date = "2026-10-17"
    project.measurements.append(
        MeasurementPoint(
            point_id="MP01",
            x_m=1.25,
            y_m=2.10,
            height_m=1.0,
            location="West control position",
            instrument="Fluke 451P",
            instrument_id="HP-DOSE-01",
            serial_number="451P-1234",
            calibration_date="2026-01-15",
            calibration_due_date="2027-01-15",
            calibration_reference="CAL-2026-0042",
            field_conditions="Room unoccupied; CT idle",
        )
    )
    app.project = project
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()


def test_measurement_record_corrected_reading_and_calibration_status():
    record = MeasurementRecord(
        record_id="MP01-M01",
        measured_at="2026-10-17T10:15",
        calibration_due_date="2027-01-15",
        reading_uSv_h=1.25,
        background_uSv_h=0.20,
    )
    record.recalculate()
    assert record.corrected_uSv_h == pytest.approx(1.05)
    assert record.calibration_status() == "Current"
    record.calibration_due_date = "2026-09-30"
    assert record.calibration_status() == "Expired"


def test_point_history_updates_latest_snapshot_without_losing_history():
    point = MeasurementPoint(
        point_id="MP01",
        x_m=1.0,
        y_m=1.0,
        instrument="Fluke 451P",
        instrument_id="HP-DOSE-01",
        serial_number="451P-1234",
        calibration_due_date="2027-01-15",
    )
    first = MeasurementRecord(
        record_id="MP01-M01",
        measured_at="2026-10-17T09:00",
        instrument=point.instrument,
        instrument_id=point.instrument_id,
        serial_number=point.serial_number,
        calibration_due_date=point.calibration_due_date,
        field_conditions="CT idle",
        reading_uSv_h=0.80,
        background_uSv_h=0.10,
        status="Pass",
    )
    second = MeasurementRecord(
        record_id="MP01-M02",
        measured_at="2026-10-17T11:00",
        instrument="Thermo FH 40 G",
        instrument_id="HP-DOSE-02",
        serial_number="FH40-999",
        calibration_due_date="2026-12-01",
        field_conditions="CT scanning abdomen protocol",
        reading_uSv_h=2.40,
        background_uSv_h=0.15,
        status="Review",
    )
    point.add_measurement_record(first)
    point.add_measurement_record(second)

    assert [r.record_id for r in point.measurement_history] == ["MP01-M01", "MP01-M02"]
    assert point.corrected_uSv_h == pytest.approx(2.25)
    assert point.instrument == "Thermo FH 40 G"
    assert point.field_conditions == "CT scanning abdomen protocol"
    assert point.status == "Review"


def test_native_project_and_digital_twin_preserve_measurement_history():
    project = RadVerifyProject()
    point = MeasurementPoint(
        point_id="MP01",
        x_m=2.2,
        y_m=1.4,
        location="Outside west wall",
        instrument="Fluke 451P",
        instrument_id="HP-DOSE-01",
        serial_number="451P-1234",
        calibration_date="2026-01-15",
        calibration_due_date="2027-01-15",
        calibration_reference="CAL-2026-0042",
    )
    point.add_measurement_record(
        MeasurementRecord(
            record_id="MP01-M01",
            measured_at="2026-10-17T10:15",
            instrument=point.instrument,
            instrument_id=point.instrument_id,
            serial_number=point.serial_number,
            calibration_date=point.calibration_date,
            calibration_due_date=point.calibration_due_date,
            calibration_reference=point.calibration_reference,
            measurement_type="Ambient dose rate",
            field_conditions="CT idle",
            reading_uSv_h=1.2,
            background_uSv_h=0.2,
            status="Pass",
            notes="Initial survey reading",
        )
    )
    project.measurements.append(point)

    native = project.to_dict()
    assert native["measurement_points"][0]["measurement_history"][0]["field_conditions"] == "CT idle"
    assert native["radstatus_payload"]["measurement_points"][0]["measurement_history"][0]["instrument_id"] == "HP-DOSE-01"

    restored_native = RadVerifyProject.from_dict(native)
    assert len(restored_native.measurements[0].measurement_history) == 1
    assert restored_native.measurements[0].corrected_uSv_h == pytest.approx(1.0)

    twin = project_to_radtwin(project)
    assert twin["measurement_points"][0]["measurement_history"][0]["calibration_reference"] == "CAL-2026-0042"
    restored_twin = project_from_radtwin(twin)
    assert restored_twin.measurements[0].measurement_history[0].notes == "Initial survey reading"
    assert restored_twin.measurements[0].instrument_id == "HP-DOSE-01"


def test_measurement_tab_adds_traceable_record_and_updates_table(app):
    record = MeasurementRecord(
        record_id="MP01-M01",
        measured_at="2026-10-17T14:05",
        instrument="Fluke 451P",
        instrument_id="HP-DOSE-01",
        serial_number="451P-1234",
        calibration_date="2026-01-15",
        calibration_due_date="2027-01-15",
        calibration_reference="CAL-2026-0042",
        measurement_type="Ambient dose rate",
        field_conditions="CT scanning chest protocol; door closed",
        reading_uSv_h=1.6,
        background_uSv_h=0.2,
        status="Pass",
        notes="Stable reading over 30 s",
    )
    assert app.measurement_tab.add_measurement_record("MP01", record) is True
    point = app.project.measurements[0]
    assert len(point.measurement_history) == 1
    assert point.corrected_uSv_h == pytest.approx(1.4)
    assert app._dirty is True

    assert app.measurement_tab.select_point("MP01") is True
    selected = app.measurement_tab.tree.selection()
    values = app.measurement_tab.tree.item(selected[0], "values")
    columns = dict(zip(app.measurement_tab.COLUMNS, values))
    assert columns["calibration"] == "Current"
    assert str(columns["history"]) == "1"
    assert str(columns["corrected"]) == "1.4"


def test_measurement_point_legacy_payload_remains_backward_compatible():
    payload = {
        "schema_version": "radverify-0.1",
        "details": {},
        "geometry": {},
        "barrier_inspection": [],
        "measurement_points": [
            {
                "point_id": "MP01",
                "x_m": 1.0,
                "y_m": 1.0,
                "instrument": "Legacy meter",
                "reading_uSv_h": 0.9,
                "background_uSv_h": 0.1,
                "status": "Pass",
            }
        ],
    }
    restored = RadVerifyProject.from_dict(payload)
    assert len(restored.measurements) == 1
    assert restored.measurements[0].measurement_history == []
    assert restored.measurements[0].corrected_uSv_h == pytest.approx(0.8)
