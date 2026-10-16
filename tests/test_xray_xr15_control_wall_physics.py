import math

import pytest

from geometry.default_room_geometry import create_default_room_geometry
from geometry.geometry_model import ControlWall, RoomGeometry
from models.shielding_models import Project, Room, Source


def _project_room():
    g = create_default_room_geometry("X-ray Room 1", "X-ray")
    room = Room(name="X-ray Room 1", modality="X-ray", geometry=g, barriers=[])
    project = Project(project_name="XR15B", modality="X-ray", rooms=[room], sources=[
        Source(name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp", room_name=room.name,
               params={"xray_method":"ncrp_simplified", "exam_room_type":"general_radiography",
                       "exams_per_week":125, "tube_potential_kvp":120})
    ])
    return project, room


def _sync(project, room):
    from geometry.barrier_sync import apply_geometry_to_selected_room_barriers
    class App:
        def __init__(self): self.project = project
        def create_default_room_geometry(self, name, modality): return create_default_room_geometry(name, modality)
        def _coerce_barrier_schema(self, b): return b
        def enforce_room_source_types(self, r): return None
    apply_geometry_to_selected_room_barriers(App(), room)
    return next(b for b in room.barriers if b.barrier_role == "fig52_control_wall")


def test_xr15a_control_wall_shielding_inputs_round_trip():
    wall = ControlWall(material="Concrete", thickness_mm=125.0, occupancy_factor=0.2, design_goal_uSv_per_week=20.0)
    restored = ControlWall.from_dict(wall.to_dict())
    assert restored.material == "Concrete"
    assert restored.thickness_mm == 125.0
    assert restored.occupancy_factor == 0.2
    assert restored.design_goal_uSv_per_week == 20.0


def test_xr15b_horizontal_control_wall_uses_perpendicular_segment_distance():
    wall = ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=2.0, orientation_deg=0)
    assert wall.source_distance_m(3.0, 1.0) == pytest.approx(2.0)
    assert wall.source_distance_m(3.0, 5.0) == pytest.approx(2.0)


def test_xr15b_vertical_control_wall_uses_perpendicular_segment_distance():
    wall = ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=2.0, orientation_deg=90)
    assert wall.source_distance_m(1.0, 3.0) == pytest.approx(2.0)
    assert wall.source_distance_m(5.0, 3.0) == pytest.approx(2.0)


def test_xr15b_distance_to_finite_wall_uses_endpoint_when_source_is_beyond_segment():
    wall = ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=2.0, orientation_deg=0)
    assert wall.source_distance_m(5.0, 1.0) == pytest.approx(math.sqrt(5.0))


def test_xr15b_all_four_render_orientations_have_correct_physical_distance():
    for orientation in (0, 180):
        assert ControlWall(3, 3, 2, orientation).source_distance_m(3, 1) == pytest.approx(2.0)
    for orientation in (90, 270):
        assert ControlWall(3, 3, 2, orientation).source_distance_m(1, 3) == pytest.approx(2.0)


def test_xr15b_barrier_sync_uses_segment_distance_and_copies_shielding_inputs():
    project, room = _project_room()
    room.geometry.source.x_m = 3.0
    room.geometry.source.y_m = 1.0
    room.geometry.control_wall = ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=4.0, orientation_deg=0,
                                             material="Concrete", thickness_mm=120.0, occupancy_factor=0.2,
                                             design_goal_uSv_per_week=20.0)
    barrier = _sync(project, room)
    assert barrier.distance_m == pytest.approx(2.0)
    assert barrier.material == "Concrete"
    assert barrier.thickness_mm == 120.0
    assert barrier.occupancy_factor == 0.2
    assert barrier.design_goal_uSv_per_week == 20.0


def test_xr15b_zero_distance_is_not_clamped_and_solver_fails_closed():
    from engine.xray_ncrp147_project_geometry import solve_project_barrier
    project, room = _project_room()
    room.geometry.source.x_m = 3.0
    room.geometry.source.y_m = 3.0
    room.geometry.control_wall = ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=2.0, orientation_deg=0)
    barrier = _sync(project, room)
    assert barrier.distance_m == 0.0
    with pytest.raises(ValueError, match="Barrier distance must be positive"):
        solve_project_barrier(project, room, barrier)
