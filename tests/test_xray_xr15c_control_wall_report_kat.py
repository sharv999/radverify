import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from geometry.geometry_model import ControlWall, RadiationSourceGeometry, RoomGeometry
from models.shielding_models import Barrier, Project, Room, Source
from services.xray_results_model import build_xray_results_model, xray_results_issueable
from reports.results_payload_builder import _room_geometry_dict


def _kat_case():
    expected = json.loads((Path(__file__).parent / "fixtures" / "xray_xr15c_control_wall_kat.json").read_text())
    geometry = RoomGeometry(
        room_name="XR KAT",
        length_m=6.0,
        width_m=6.0,
        source=RadiationSourceGeometry(label="X-ray", x_m=1.0, y_m=1.0),
        control_wall=ControlWall(
            center_x_m=3.0, center_y_m=1.0, length_m=2.0,
            orientation_deg=90, nib_length_m=0.75, material="Pb",
            thickness_mm=0.88, occupancy_factor=1.0,
            design_goal_uSv_per_week=100.0,
        ),
    )
    barrier = Barrier(
        name="Control wall", material="Pb", thickness_mm=0.88,
        adjacent_area="Control booth", barrier_role="fig52_control_wall",
        distance_m=geometry.control_wall.source_distance_m(1.0, 1.0),
        occupancy_factor=1.0, design_goal_uSv_per_week=100.0,
    )
    room = Room(name="XR KAT", modality="X-RAY", barriers=[barrier], geometry=geometry)
    source = Source(
        name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp",
        room_name=room.name,
        params={"xray_method": "ncrp_simplified", "exam_room_type": "general_radiography", "exams_per_week": 125},
    )
    project = Project(project_name="XR-15C KAT", modality="X-RAY", rooms=[room], sources=[source])
    return expected, project, room


def test_xr15c_control_wall_known_answer_result():
    expected, project, room = _kat_case()
    row = build_xray_results_model(project, room)[0]
    assert row["distance_m"] == pytest.approx(expected["distance_m"])
    assert row["unshielded_weekly_dose_uSv"] == pytest.approx(expected["unshielded_weekly_dose_uSv"])
    assert row["required_thickness_mm"] == pytest.approx(expected["required_thickness_mm"], abs=1e-6)
    assert row["transmitted_dose_uSv_per_week"] == pytest.approx(expected["transmitted_dose_uSv_per_week"], abs=1e-6)
    assert row["compliance_status"] == expected["compliance_status"]
    assert row["fig52_section"] == expected["fig52_section"]
    assert row["fig52_combination"] == expected["fig52_combination"]


def test_xr15d_control_wall_results_are_issueable_after_release():
    expected, project, room = _kat_case()
    rows = build_xray_results_model(project, room)
    assert rows[0]["issued_output_enabled"] is expected["issued_output_enabled"]
    assert xray_results_issueable(rows) is True


def test_xr15c_report_geometry_contains_control_wall_inputs():
    expected, project, room = _kat_case()
    payload_geometry = _room_geometry_dict(room.geometry, room.modality)
    cw = payload_geometry["control_wall"]
    assert cw["center_x_m"] == 3.0
    assert cw["center_y_m"] == 1.0
    assert cw["orientation_deg"] == 90.0
    assert cw["material"] == "Pb"
    assert cw["thickness_mm"] == 0.88
    assert cw["occupancy_factor"] == 1.0
    assert cw["design_goal_uSv_per_week"] == 100.0


def test_xr15c_control_wall_provenance_fields_are_available_to_report_adapter():
    expected, project, room = _kat_case()
    row = build_xray_results_model(project, room)[0]
    for key in ("results_source", "results_model_version", "fig52_section", "fig52_combination", "fig52_components", "fig52", "issued_output_enabled", "replay_verified"):
        assert key in row


def test_xr15c_canonical_report_row_preserves_control_wall_result_and_provenance():
    from reports.barrier_schedule import build_canonical_barrier_schedule_payload

    expected, project, room = _kat_case()
    live = build_xray_results_model(project, room)
    app = SimpleNamespace(
        project=project,
        _row_confidence_from_live=lambda name, row: 1.0,
    )
    rows = build_canonical_barrier_schedule_payload(app, room, room_results=live)
    assert len(rows) == 1
    row = rows[0]
    assert row["barrier_role"] == "fig52_control_wall"
    assert row["distance_m"] == pytest.approx(expected["distance_m"])
    assert row["required_thickness_mm"] == pytest.approx(expected["required_thickness_mm"])
    assert row["transmitted_dose_uSv_per_week"] == pytest.approx(expected["transmitted_dose_uSv_per_week"])
    assert row["fig52_section"] == "5.3.6"
    assert row["fig52_combination"] == "governing_max"
    assert row["issued_output_enabled"] is True
    assert row["replay_verified"] is True
