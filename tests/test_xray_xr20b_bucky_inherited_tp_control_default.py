from geometry.geometry_model import BuckyShield, ControlWall
from services.xray_results_model import build_xray_results_model
from tests.test_xray_xr08d_results_report_requalification import _project


def test_xr20b_bucky_subbarrier_inherits_parent_t_and_p():
    project = _project()
    room = project.rooms[0]
    room.geometry.bucky_shield = BuckyShield(wall="N", offset_m=2.0)
    parent = room.barriers[0]
    parent.name = "N wall"
    parent.occupancy_factor = 0.5
    parent.design_goal_uSv_per_week = 20.0
    rows = build_xray_results_model(project, room)
    shield = next(row for row in rows if row["barrier"] == "Bucky shield")
    assert shield["parent_barrier"] == "N wall"
    assert shield["occupancy_factor"] == 0.5
    assert shield["design_goal_uSv_per_week"] == 20.0
    assert shield["bucky_shield_thickness_mm"] == 2.2


def test_xr20b_canvas_map_explicitly_displays_inherited_t_and_p():
    text = open("tabs/results_barrier_maps.py", encoding="utf-8").read()
    assert 'inherited.append(f"T={float(bucky_live.get(\'occupancy_factor\')):g}")' in text
    assert 'inherited.append(f"P={float(bucky_live.get(\'design_goal_uSv_per_week\')):g} µSv/wk")' in text
    canvas = open("geometry/geometry_canvas.py", encoding="utf-8").read()
    assert 'dose_labels.get("Bucky shield")' in canvas


def test_xr20b_control_wall_new_empty_state_is_t1_p100():
    control = ControlWall()
    assert control.occupancy_factor == 1.0
    assert control.design_goal_uSv_per_week == 100.0
    text = open("tabs/geometry_tab.py", encoding="utf-8").read()
    new_block = text[text.index("if is_new_control_wall:"):text.index("x = min(max(float(self.xray_control_x_var.get())")]
    assert 'self.xray_control_t_var.set("1.0")' in new_block
    assert 'self.xray_control_p_var.set("100 µSv/wk")' in new_block
    assert text.count('self.xray_control_p_var.set("100 µSv/wk")') >= 3
