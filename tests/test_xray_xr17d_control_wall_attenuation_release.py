from copy import deepcopy

import pytest

from models.shielding_models import project_to_dict
from reports.barrier_schedule import build_canonical_barrier_schedule_payload
from reports.results_payload_builder import build_results_payload
from services.project_io import load_project_from_file, write_project_payload
from services.xray_results_model import build_xray_results_model, xray_results_issueable
from tests.test_xray_xr15d_control_wall_release import _App
from tests.test_xray_xr17b_control_wall_attenuation import _case


RELEASE_ID = "xr17d-issueable-intervening-control-wall-v1"


def _north_row(project, room):
    return next(r for r in build_xray_results_model(project, room) if r["barrier"] == "N wall")


def test_xr17d_intercepted_known_answer_is_frozen_and_issueable():
    project, room, _ = _case(True)
    row = _north_row(project, room)
    assert row["control_wall_attenuation_applied"] is True
    assert row["control_wall_secondary_transmission"] == pytest.approx(0.006604533, abs=5e-10)
    assert row["unshielded_weekly_dose_uSv"] == pytest.approx(1.754, abs=5e-4)
    assert row["transmitted_dose_uSv_per_week"] == pytest.approx(0.012, abs=5e-4)
    assert row["required_thickness_mm"] == pytest.approx(0.0)
    assert row["issued_output_enabled"] is True
    assert xray_results_issueable(build_xray_results_model(project, room)) is True


def test_xr17d_nonintercepted_known_answer_matches_no_control_wall_baseline():
    project, room, _ = _case(False)
    control_barrier = next(b for b in room.barriers if b.barrier_role == "fig52_control_wall")
    control_barrier.distance_m = room.geometry.control_wall.source_distance_m(
        room.geometry.source.x_m, room.geometry.source.y_m
    )
    row = _north_row(project, room)
    baseline_project, baseline_room = deepcopy((project, room))
    baseline_room.geometry.control_wall = None
    baseline_room.barriers = [b for b in baseline_room.barriers if b.barrier_role != "fig52_control_wall"]
    baseline_project.rooms[0] = baseline_room
    baseline = _north_row(baseline_project, baseline_room)
    assert row["control_wall_attenuation_applied"] is False
    assert row["control_wall_secondary_transmission"] == pytest.approx(1.0)
    assert row["unshielded_weekly_dose_uSv"] == baseline["unshielded_weekly_dose_uSv"]
    assert row["transmitted_dose_uSv_per_week"] == baseline["transmitted_dose_uSv_per_week"]
    assert row["required_thickness_mm"] == baseline["required_thickness_mm"]


def test_xr17d_all_four_control_wall_rotations_are_deterministic():
    factors = []
    for orientation in (0, 180, 90, 270):
        project, room, barrier = _case(True)
        control = room.geometry.control_wall
        if orientation in (0, 180):
            control.orientation_deg = orientation
            control.center_x_m, control.center_y_m = 3.0, 4.0
            barrier.name = "N wall"
            barrier.distance_m = 4.0
        else:
            control.orientation_deg = orientation
            control.center_x_m, control.center_y_m = 4.0, 2.0
            barrier.name = "E wall"
            barrier.distance_m = 3.0
        canonical = next(b for b in room.barriers if b.barrier_role == "fig52_control_wall")
        canonical.distance_m = control.source_distance_m(room.geometry.source.x_m, room.geometry.source.y_m)
        rows = build_xray_results_model(project, room)
        row = next(r for r in rows if r["barrier"] == barrier.name)
        assert row["control_wall_attenuation_applied"] is True
        factors.append(row["control_wall_secondary_transmission"])
    assert factors == pytest.approx([factors[0]] * 4)


def test_xr17d_save_reopen_replay_is_exact(tmp_path):
    project, room, _ = _case(True)
    before = build_xray_results_model(project, room)
    path = write_project_payload(tmp_path / "xr17d.json", project_to_dict(project))
    restored = load_project_from_file(path)
    after = build_xray_results_model(restored, restored.rooms[0])
    assert project_to_dict(restored) == project_to_dict(project)
    assert after == before


def test_xr17d_results_report_equivalence_and_release_gate():
    project, room, _ = _case(True)
    results = build_xray_results_model(project, room)
    schedule = build_canonical_barrier_schedule_payload(_App(project), room, room_results=results)
    result = next(r for r in results if r["barrier"] == "N wall")
    report = next(r for r in schedule if r["name"] == "N wall")
    for key in (
        "control_wall_attenuation_applied", "control_wall_secondary_transmission",
        "control_wall_material", "control_wall_thickness_mm", "control_wall_provenance",
    ):
        assert report[key] == result[key]
    payload = build_results_payload(_App(project), report_status="Draft")
    qualification = payload["rooms"][0]["xray_report_qualification"]
    assert qualification["fig52_requalification_version"] == RELEASE_ID
    assert qualification["issued_output_enabled"] is True
    assert payload["export_eligibility"]["can_export_pdf"] is True
