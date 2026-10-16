"""XR-21F focused GXR Control Wall parent-wall design immutability regression."""
from dataclasses import dataclass
from itertools import product
from tools.xray_opening_ui_crash import (
    CUSTOM, assert_parent_barrier_design_immutability,
    write_pdf_report as _write_report,
)
from tools.xray_ui_state_stress import _reset_to_new_gxr, wall_snapshot

BASELINES = ('default', 'north_pb_glass', 'mixed_custom')
SELECTED = ('N', 'E', 'S', 'W', 'Floor', 'Ceiling')
POSITIONS = ('north_west', 'centre', 'south_east')

@dataclass(frozen=True)
class Case:
    name: str
    baseline: str
    selected: str
    position: str

CASES = tuple(Case(f'control_{i:03d}_{b}_{s}_{p}', b, s, p)
              for i, (b, s, p) in enumerate(product(BASELINES, SELECTED, POSITIONS), 1))

def _baseline(app, kind):
    room = app.project.rooms[0]
    for barrier in room.barriers:
        if kind == 'mixed_custom' and barrier.name in CUSTOM:
            (barrier.material, barrier.thickness_mm, barrier.occupancy_factor,
             barrier.design_goal_uSv_per_week) = CUSTOM[barrier.name]
            barrier.material_legacy = barrier.material
        elif kind == 'north_pb_glass' and barrier.name == 'N wall':
            barrier.material = 'Pb glass'
            barrier.material_legacy = 'Pb glass'
            barrier.thickness_mm = 2.2
            barrier.occupancy_factor = 1.0
            barrier.design_goal_uSv_per_week = 10.0
    app.geometry_tab.load_selected_barrier_fields()
    app.geometry_tab.draw_room_with_risk()
    app.update_idletasks()
    return wall_snapshot(room)

def run_case(app, case):
    _reset_to_new_gxr(app)
    g = app.geometry_tab
    baseline = _baseline(app, case.baseline)
    def check(action):
        app.update()
        assert_parent_barrier_design_immutability(app, baseline, case.name, action)
    check('initial')
    g.barrier_wall_var.set(case.selected)
    check('select-barrier-editor')
    coords = {'north_west': ('1.0', '1.0'), 'centre': ('2.0', '2.0'),
              'south_east': ('3.0', '3.0')}
    x, y = coords[case.position]
    g.xray_control_x_var.set(x)
    g.xray_control_y_var.set(y)
    check('set-control-wall-position-fields')
    g.add_or_update_xray_control_wall()
    check('add-control-wall')
    for axis, delta in (('x', 0.1), ('y', 0.1), ('x', -0.1), ('y', -0.1)):
        g.nudge_xray_control_wall(axis, delta)
        check(f'nudge-{axis}-{delta}')
    for i in range(4):
        g.rotate_xray_control_wall_cw()
        check(f'rotate-{i+1}')
    for field, value in (
        ('xray_control_length_var', '1.8'),
        ('xray_control_nib_length_var', '0.5'),
        ('xray_control_material_var', 'Concrete'),
        ('xray_control_thickness_var', '150'),
        ('xray_control_t_var', '0.5'),
        ('xray_control_p_var', '20 µSv/wk'),
        ('xray_control_material_var', 'Pb'),
        ('xray_control_thickness_var', '0.88'),
    ):
        getattr(g, field).set(value)
        g.add_or_update_xray_control_wall()
        check(f'edit-{field}-{value}')
    g.remove_xray_control_wall()
    check('remove-control-wall')
    g.add_or_update_xray_control_wall()
    check('re-add-control-wall')
    g.remove_xray_control_wall()
    check('remove-control-wall-again')

def write_pdf_report(results, path):
    return _write_report(results, path)
