import copy

import pytest

from engine.xray_ncrp147_project_geometry import solve_project_barrier
from geometry.geometry_model import ControlWall, RadiationSourceGeometry, RoomGeometry
from models.shielding_models import Barrier, Project, Room, Source
from services.xray_results_model import build_xray_results_model, xray_results_issueable


def _case(intercept=True):
    g = RoomGeometry(
        room_name="XR", length_m=6.0, width_m=6.0,
        source=RadiationSourceGeometry(label="X-ray", x_m=3.0, y_m=2.0),
        control_wall=ControlWall(
            center_x_m=3.0 if intercept else 5.0, center_y_m=4.0,
            length_m=2.0, orientation_deg=0, material="Pb", thickness_mm=0.88,
            occupancy_factor=1.0, design_goal_uSv_per_week=100.0,
        ),
    )
    north = Barrier(name="N wall", material="Pb", thickness_mm=0.88,
                    barrier_role="fig52_secondary_wall", distance_m=4.0,
                    occupancy_factor=1.0, design_goal_uSv_per_week=100.0)
    control = Barrier(name="Control wall", material="Pb", thickness_mm=0.88,
                      barrier_role="fig52_control_wall", distance_m=2.0,
                      occupancy_factor=1.0, design_goal_uSv_per_week=100.0)
    room = Room(name="XR", modality="X-RAY", barriers=[north, control], geometry=g)
    source = Source(name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp",
                    room_name="XR", params={"xray_method":"ncrp_simplified", "exam_room_type":"general_radiography", "exams_per_week":125})
    project = Project(project_name="XR17B", modality="X-RAY", rooms=[room], sources=[source])
    return project, room, north


def test_xr17b_intercepted_secondary_wall_gets_control_wall_attenuation():
    p, r, b = _case(True)
    solved = solve_project_barrier(p, r, b)
    assert solved["control_wall_attenuation_applied"] is True
    assert 0.0 < solved["control_wall_secondary_transmission"] < 1.0


def test_xr17b_nonintercepted_wall_is_numerically_unchanged():
    p1, r1, b1 = _case(False)
    solved = solve_project_barrier(p1, r1, b1)
    assert solved["control_wall_attenuation_applied"] is False
    assert solved["control_wall_secondary_transmission"] == 1.0

    p2, r2, b2 = copy.deepcopy((p1, r1, b1))
    r2.geometry.control_wall = None
    p2.rooms[0] = r2
    no_control = solve_project_barrier(p2, r2, b2)
    assert solved["required_structural_mm"] == pytest.approx(no_control["required_structural_mm"])


def test_xr17b_intercepted_wall_result_is_lower_than_same_wall_without_control_wall():
    p, r, b = _case(True)
    intercepted = next(row for row in build_xray_results_model(p, r) if row["barrier"] == "N wall")
    p0, r0, _ = copy.deepcopy((p, r, b))
    r0.geometry.control_wall = None
    r0.barriers = [x for x in r0.barriers if x.barrier_role != "fig52_control_wall"]
    p0.rooms[0] = r0
    baseline = build_xray_results_model(p0, r0)[0]
    assert intercepted["unshielded_weekly_dose_uSv"] < baseline["unshielded_weekly_dose_uSv"]
    assert intercepted["transmitted_dose_uSv_per_week"] < baseline["transmitted_dose_uSv_per_week"]


def test_xr17d_intercepted_result_is_issueable_after_explicit_release():
    p, r, _ = _case(True)
    rows = build_xray_results_model(p, r)
    north = next(row for row in rows if row["barrier"] == "N wall")
    assert north["issued_output_enabled"] is True
    assert xray_results_issueable(rows) is True


def test_xr17b_primary_component_is_not_credited_by_secondary_control_wall_model():
    p, r, b = _case(True)
    b.barrier_role = "fig52_chest_bucky_wall"
    solved = solve_project_barrier(p, r, b)
    comps = {c["name"]: c for c in solved["components"]}
    # Primary remains present; XR-17B only credits the qualified secondary control-wall model.
    assert "primary_chest_bucky" in comps
    assert solved["control_wall_attenuation_applied"] is True
