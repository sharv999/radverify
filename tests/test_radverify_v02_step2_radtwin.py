from __future__ import annotations

import json
from pathlib import Path

import pytest

from geometry.geometry_model import BuckyShield, ControlWall, Opening, WallBucky
from radverify.models import MeasurementPoint, RadVerifyProject
from radverify.radtwin import (
    RADTWIN_SCHEMA,
    RadTwinValidationError,
    project_from_radtwin,
    project_to_radtwin,
    radtwin_to_radshield_geometry,
    validate_radtwin,
)


def _sample_project() -> RadVerifyProject:
    project = RadVerifyProject()
    project.details.project_id = "RV-TWIN-001"
    project.details.site_name = "Example Hospital"
    project.details.building = "Main / Level 1"
    project.details.room_name = "CT 1"
    project.details.room_number = "1.023"
    project.details.room_type = "CT"
    project.details.inspector = "Inspector A"
    project.details.inspection_date = "2026-10-16"
    project.details.drawing_reference = "A-401 Rev C"
    project.details.notes = "Digital twin test room"
    project.geometry.length_m = 5.4
    project.geometry.width_m = 7.2
    project.geometry.height_m = 2.9
    project.geometry.source.label = "CT scanner"
    project.geometry.source.x_m = 3.4
    project.geometry.source.y_m = 2.1
    project.geometry.source.rotation_deg = 90
    project.geometry.openings.append(
        Opening(
            wall="S",
            opening_type="door",
            offset_m=1.3,
            width_m=1.0,
            label="D1",
            id="D1",
            material="Lead-lined door",
            pb_equiv_mm=1.5,
            sill_height_above_ffl_m=0.0,
            head_height_above_ffl_m=2.1,
            kvp_basis=150.0,
        )
    )
    project.geometry.wall_bucky = WallBucky(wall="E", offset_m=2.2, id="WB1")
    project.geometry.bucky_shield = BuckyShield(wall="E", offset_m=2.2, id="BS1")
    project.geometry.control_wall = ControlWall(center_x_m=1.2, center_y_m=1.1, orientation_deg=90, id="CW1")
    project.sync_opening_inspections()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    north.expected_construction = "1.5 mm Pb to 2.1 m"
    north.expected_pb_mm = 1.5
    north.observed_construction = "Lead sheet behind plasterboard"
    north.observed_pb_mm = 1.5
    north.status = "Pass"
    north.evidence_ref = "IMG_0042"
    north.notes = "Continuous at accessible junctions"
    mp = MeasurementPoint(
        point_id="MP01",
        x_m=1.0,
        y_m=4.8,
        height_m=1.0,
        location="Outside N wall",
        instrument="Survey meter 01",
        reading_uSv_h=1.1,
        background_uSv_h=0.2,
        status="Pass",
    )
    mp.recalculate()
    project.measurements.append(mp)
    return project


def test_radtwin_export_has_neutral_schema_and_coordinate_contract():
    twin = project_to_radtwin(_sample_project())
    validate_radtwin(twin)
    assert twin["schema"] == RADTWIN_SCHEMA
    assert twin["room"]["site_name"] == "Example Hospital"
    assert twin["geometry"]["dimensions_m"] == {
        "south_north": 5.4,
        "west_east": 7.2,
        "height": 2.9,
    }
    assert twin["geometry"]["coordinate_system"]["x_axis"] == "west_to_east"
    assert twin["equipment"][0]["position_m"] == {"x": 3.4, "y": 2.1}
    north = next(b for b in twin["barriers"] if b["id"] == "N wall")
    assert north["design_specification"]["pb_equivalent_mm"] == 1.5
    assert north["as_built"]["pb_equivalent_mm"] == 1.5
    assert north["verification"]["status"] == "Pass"


def test_radtwin_round_trip_preserves_field_record():
    original = _sample_project()
    restored = project_from_radtwin(project_to_radtwin(original))
    assert restored.details.project_id == "RV-TWIN-001"
    assert restored.details.drawing_reference == "A-401 Rev C"
    assert restored.geometry.length_m == 5.4
    assert restored.geometry.width_m == 7.2
    assert restored.geometry.source.rotation_deg == 90
    assert restored.geometry.openings[0].id == "D1"
    assert restored.geometry.openings[0].kvp_basis == 150.0
    assert restored.geometry.wall_bucky is not None
    assert restored.geometry.bucky_shield is not None
    assert restored.geometry.control_wall is not None
    north = next(b for b in restored.barriers if b.barrier_id == "N wall")
    assert north.expected_pb_mm == 1.5
    assert north.observed_pb_mm == 1.5
    assert north.evidence_ref == "IMG_0042"
    assert restored.measurements[0].corrected_uSv_h == pytest.approx(0.9)


def test_radtwin_maps_to_current_radshield_room_geometry_shape():
    original = _sample_project()
    mapped = radtwin_to_radshield_geometry(project_to_radtwin(original))
    assert mapped["room_name"] == "CT 1"
    assert mapped["length_m"] == 5.4
    assert mapped["width_m"] == 7.2
    assert mapped["height_m"] == 2.9
    assert mapped["source"] == {
        "label": "CT scanner",
        "x_m": 3.4,
        "y_m": 2.1,
        "rotation_deg": 90,
    }
    assert mapped["openings"][0]["id"] == "D1"
    assert mapped["wall_bucky"]["id"] == "WB1"
    assert mapped["bucky_shield"]["id"] == "BS1"
    assert mapped["control_wall"]["id"] == "CW1"


def test_radtwin_runtime_validation_rejects_wrong_schema_and_invalid_dimensions():
    twin = project_to_radtwin(_sample_project())
    twin["schema"] = "something-else"
    with pytest.raises(RadTwinValidationError):
        validate_radtwin(twin)

    twin = project_to_radtwin(_sample_project())
    twin["geometry"]["dimensions_m"]["height"] = 0
    with pytest.raises(RadTwinValidationError):
        validate_radtwin(twin)


def test_machine_readable_schema_document_exists_and_matches_runtime_schema():
    schema_path = Path(__file__).parents[1] / "docs" / "radtwin" / "radiation-room-digital-twin.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema"]["const"] == RADTWIN_SCHEMA
