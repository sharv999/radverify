from engine.shielding_engine import default_barriers
from models.shielding_models import Room
from services.room_defaults import apply_new_xray_wall_defaults


def test_xr19c_new_gxr_external_wall_defaults_are_uniform():
    room = Room(name="X-ray Room 1", modality="X-RAY", barriers=default_barriers())
    apply_new_xray_wall_defaults(room)
    walls = [b for b in room.barriers if b.name in {"N wall", "E wall", "S wall", "W wall"}]
    assert len(walls) == 4
    for b in walls:
        assert b.material == "Pb"
        assert b.thickness_mm == 0.88
        assert b.occupancy_factor == 1.0
        assert b.design_goal_uSv_per_week == 10.0


def test_xr19c_control_wall_default_remains_100_usv_per_week():
    from geometry.geometry_model import ControlWall
    wall = ControlWall()
    assert wall.material == "Pb"
    assert wall.thickness_mm == 0.88
    assert wall.design_goal_uSv_per_week == 100.0


def test_xr19c_report_adapter_carries_bucky_shield_provenance():
    text = open("reports/barrier_schedule.py", encoding="utf-8").read()
    for key in (
        "bucky_shield_attenuation_applied",
        "bucky_shield_primary_transmission",
        "bucky_shield_material",
        "bucky_shield_thickness_mm",
        "bucky_shield_provenance",
    ):
        assert key in text


def test_xr19c_canvas_and_pdf_make_bucky_credit_visible():
    maps = open("tabs/results_barrier_maps.py", encoding="utf-8").read()
    report = open("reports/report_generator.py", encoding="utf-8").read()
    assert "Bucky shield Pb 2.20 mm B=" in maps
    assert "Chest Bucky Shield primary attenuation credit:" in report
    assert "bucky_shield_provenance" in report
