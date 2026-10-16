import pytest

from engine.xray_ncrp147_project_geometry import (
    FIG52_BARRIER_ROLES, PROJECT_FIG52_VERSION, scenario_for_project_barrier,
    solve_project_barrier,
)
from geometry.geometry_model import RadiationSourceGeometry, RoomGeometry
from models.shielding_models import Barrier, Project, Room, Source
from tabs.barrier_inline_values import xray_barrier_role_values


def _fixture(role="fig52_cross_table_wall", distance=2.4, material="Pb"):
    g = RoomGeometry(room_name="GXR 1", length_m=6.0, width_m=5.0, height_m=3.0,
                     source=RadiationSourceGeometry(label="General Radiography", x_m=2.0, y_m=2.5))
    b = Barrier(name="E wall", material=material, thickness_mm=1.0, barrier_role=role,
                distance_m=distance, occupancy_factor=1.0, design_goal_uSv_per_week=20.0)
    room = Room(name="GXR 1", modality="X-ray", barriers=[b], geometry=g)
    src = Source(name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp",
                 room_name="GXR 1", params={"xray_method":"ncrp_simplified", "exam_room_type":"general_radiography", "exams_per_week":125, "tube_potential_kvp":120})
    return Project(project_name="XR08C", modality="X-ray", rooms=[room], sources=[src]), room, b


def test_xr08c_ui_roles_are_fig52_scenarios_only():
    assert tuple(xray_barrier_role_values()) == FIG52_BARRIER_ROLES


@pytest.mark.parametrize("role,section", [
    ("fig52_floor_under_table", "5.3.1"), ("fig52_ceiling", "5.3.2"),
    ("fig52_chest_bucky_wall", "5.3.3"), ("fig52_darkroom_wall", "5.3.4"),
    ("fig52_cross_table_wall", "5.3.5"), ("fig52_control_wall", "5.3.6"),
    ("fig52_secondary_wall", "5.3"), ("fig52_door", "5.3"),
])
def test_xr08c_all_project_barrier_scenarios_are_explicit(role, section):
    p,r,b=_fixture(role)
    assert scenario_for_project_barrier(p,r,b).section == section


def test_xr08c_actual_barrier_distance_changes_source_terms_by_inverse_square():
    p1,r1,b1=_fixture("fig52_control_wall", 2.0)
    p2,r2,b2=_fixture("fig52_control_wall", 4.0)
    k1=scenario_for_project_barrier(p1,r1,b1).components[0].unshielded_mGy_week
    k2=scenario_for_project_barrier(p2,r2,b2).components[0].unshielded_mGy_week
    assert k2 == pytest.approx(k1/4.0)


def test_xr08c_cross_table_uses_joint_primary_secondary_with_project_distance():
    p,r,b=_fixture("fig52_cross_table_wall", 2.4)
    result=solve_project_barrier(p,r,b)
    assert result["combination"] == "joint"
    assert result["project_fig52_version"] == PROJECT_FIG52_VERSION
    assert result["distance_m"] == pytest.approx(2.4)
    assert result["required_structural_mm"] > max(result["individual_required_mm"].values())


def test_xr08c_target_uses_project_design_goal_and_occupancy():
    p,r,b=_fixture("fig52_control_wall", 2.0)
    b.design_goal_uSv_per_week=20.0; b.occupancy_factor=0.25
    result=solve_project_barrier(p,r,b)
    assert result["target_occupied_mGy_week"] == pytest.approx(0.08)


def test_xr08c_floor_and_ceiling_use_persisted_vertical_barrier_distances():
    p,r,b=_fixture("fig52_floor_under_table", 1.15, "Concrete")
    floor=solve_project_barrier(p,r,b)
    b.barrier_role="fig52_ceiling"; b.distance_m=2.35
    ceiling=solve_project_barrier(p,r,b)
    assert floor["distance_m"] == pytest.approx(1.15)
    assert ceiling["distance_m"] == pytest.approx(2.35)


def test_xr08c_fail_closed_for_legacy_role():
    p,r,b=_fixture("primary_bucky_wall")
    with pytest.raises(ValueError, match="not qualified"):
        scenario_for_project_barrier(p,r,b)


def test_xr08c_fail_closed_for_nonqualified_source_configuration():
    p,r,b=_fixture("fig52_secondary_wall")
    p.sources[0].params["exam_room_type"]="chest_room"
    with pytest.raises(ValueError, match="qualified General Radiography"):
        scenario_for_project_barrier(p,r,b)
