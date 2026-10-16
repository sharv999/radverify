from models.shielding_models import Barrier, Project, Room, Source, project_to_dict
from geometry.geometry_model import RadiationSourceGeometry, RoomGeometry, WallBucky
from services.project_io import load_project_from_file, write_project_payload
from services.xray_results_model import build_xray_results_model, XRAY_RESULTS_MODEL_VERSION
from modalities.registry import source_calculation_blocked_reason
from modalities.xray import XRAY_CALCULATION_BLOCK_REASON


def _project():
    geometry = RoomGeometry(
        room_name="General X-ray 1", length_m=6.2, width_m=5.4, height_m=3.0,
        source=RadiationSourceGeometry(label="General Radiography", x_m=2.1, y_m=2.7, rotation_deg=90),
        wall_bucky=WallBucky(wall="N", offset_m=2.2),
    )
    room = Room(name="General X-ray 1", modality="X-ray", geometry=geometry, barriers=[
        Barrier(name="N wall", material="Pb", thickness_mm=1.5, barrier_role="primary_bucky_wall", distance_m=3.5, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        Barrier(name="Floor", material="Concrete", thickness_mm=150.0, barrier_role="primary_floor", distance_m=3.0, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        Barrier(name="E wall", material="Pb", thickness_mm=1.0, barrier_role="secondary_wall", distance_m=2.8, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
    ])
    source = Source(
        name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp", room_name=room.name,
        params={"xray_method":"ncrp_simplified", "exam_room_type":"general_radiography", "exams_per_week":125, "tube_potential_kvp":120},
    )
    return Project(project_name="XR-05 KAT", modality="X-ray", rooms=[room], sources=[source])


def test_xr05_save_reopen_preserves_source_geometry_barriers_and_results(tmp_path):
    project = _project(); room = project.rooms[0]
    before = build_xray_results_model(project, room)
    path = write_project_payload(tmp_path / "xr05.json", project_to_dict(project))
    loaded = load_project_from_file(path); loaded_room = loaded.rooms[0]
    after = build_xray_results_model(loaded, loaded_room)

    assert project_to_dict(loaded) == project_to_dict(project)
    assert loaded_room.geometry.to_dict() == room.geometry.to_dict()
    assert [b.barrier_role for b in loaded_room.barriers] == ["primary_bucky_wall", "primary_floor", "secondary_wall"]
    assert after == before


def test_xr05_canonical_results_are_replay_verified_and_use_xr03_solver():
    project = _project()
    rows = build_xray_results_model(project, project.rooms[0])
    assert len(rows) == 3
    assert [r["solver_used"] for r in rows] == [
        "ncrp147_archer_primary_bucky_wall", "ncrp147_archer_primary_floor", "ncrp147_archer_secondary_wall"
    ]
    assert all(r["results_model_version"] == XRAY_RESULTS_MODEL_VERSION for r in rows)
    assert all(r["replay_verified"] is True for r in rows)
    assert all(r["issued_output_enabled"] is False for r in rows)


def test_xr05_results_equal_direct_xr03_barrier_calculations():
    from engine.shielding_engine import calc_barrier_result
    project = _project(); room = project.rooms[0]
    room.sources = list(project.sources)
    canonical = build_xray_results_model(project, room)
    direct = [calc_barrier_result(room, b, project, "xray_120kvp") for b in room.barriers]
    for c, d in zip(canonical, direct):
        for key, value in d.items():
            assert c[key] == value


def test_xr05_issued_output_gate_remains_closed():
    assert source_calculation_blocked_reason("xray_primary") == XRAY_CALCULATION_BLOCK_REASON
