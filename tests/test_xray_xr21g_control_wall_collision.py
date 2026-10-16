"""XR-21G: source movement must not cross GXR Control Wall or nibs."""
import pytest
from geometry.geometry_model import ControlWall
from geometry.control_wall_collision import (control_wall_segments, point_on_control_wall,
                                              source_path_crosses_control_wall)

@pytest.fixture
def wall():
    return ControlWall(center_x_m=2, center_y_m=4.2, length_m=1.5,
                       orientation_deg=0, nib_length_m=0.75)

def test_source_cannot_cross_main_wall(wall):
    assert source_path_crosses_control_wall((2,3), (2,5), wall)
    assert source_path_crosses_control_wall((2,5), (2,3), wall)

def test_source_cannot_land_on_wall(wall):
    assert point_on_control_wall((2,4.2), wall)
    assert source_path_crosses_control_wall((2,3), (2,4.2), wall)

def test_source_can_move_parallel_without_collision(wall):
    assert not source_path_crosses_control_wall((2,3), (2.5,3), wall)

def test_large_step_cannot_jump_wall(wall):
    assert source_path_crosses_control_wall((2,2), (2,5.5), wall)

def test_nib_collision(wall):
    _, (a,b), _ = control_wall_segments(wall)
    midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    assert point_on_control_wall(midpoint, wall)
    assert source_path_crosses_control_wall((midpoint[0],midpoint[1]-0.5),
                                             (midpoint[0],midpoint[1]+0.5),wall)

def test_rotation_changes_collision_direction(wall):
    wall.orientation_deg = 90
    assert source_path_crosses_control_wall((1,4.2),(3,4.2),wall)

def test_saved_source_is_on_wall_but_can_escape(wall):
    assert point_on_control_wall((1.9,4.2),wall)
    assert not source_path_crosses_control_wall((1.9,4.2),(1.9,3.9),wall)
