from geometry.geometry_model import BuckyShield
from services.xray_results_model import build_xray_results_model
from tests.test_xray_xr08d_results_report_requalification import _project


def _shielded_project():
    project = _project()
    room = project.rooms[0]
    room.geometry.bucky_shield = BuckyShield(wall="N", offset_m=2.0)
    room.barriers[0].name = "N wall"
    return project, room


def test_xr20a_wall_and_bucky_shield_are_separate_physics_results():
    project, room = _shielded_project()
    rows = build_xray_results_model(project, room)
    by_name = {row["barrier"]: row for row in rows}
    wall = by_name["N wall"]
    shield = by_name["Bucky shield"]
    assert wall["bucky_shield_attenuation_applied"] is False
    assert shield["sub_barrier"] is True
    assert shield["parent_barrier"] == "N wall"
    assert shield["sub_barrier_width_m"] == 1.2
    assert shield["bucky_shield_attenuation_applied"] is True
    assert shield["bucky_shield_material"] == "Pb"
    assert shield["bucky_shield_thickness_mm"] == 2.2
    assert shield["transmitted_dose_uSv_per_week"] < wall["transmitted_dose_uSv_per_week"]


def test_xr20a_canvas_draws_independent_bucky_subbarrier_status_and_label():
    text = open("geometry/geometry_canvas.py", encoding="utf-8").read()
    assert '_risk_colour_for_barrier(risk_map, "Bucky shield")' in text
    assert '"PRIMARY — shielded sub-barrier"' in text
    assert '"Width 1.20 m"' in text
    assert '"Pb 2.20 mm"' in text
    assert 'dose_labels.get("Bucky shield")' in text


def test_xr20a_control_wall_label_is_forced_above_complete_symbol():
    text = open("geometry/geometry_canvas.py", encoding="utf-8").read()
    assert 'top_y = min(point[1] for point in nib_points)' in text
    assert 'start_y = top_y - 12 - (line_spacing * (len(lines) - 1))' in text
