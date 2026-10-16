from types import SimpleNamespace

from tools.xray_ui_state_stress import EXPECTED, SCENARIOS, WALLS, assert_wall_design_isolated, wall_snapshot


def _room():
    return SimpleNamespace(barriers=[
        SimpleNamespace(name=name, material="Pb", thickness_mm=0.88,
                        occupancy_factor=1.0, design_goal_uSv_per_week=10.0)
        for name in WALLS
    ])


def test_xr21b_harness_covers_opening_bucky_control_and_selection_orderings():
    actions = {action for scenario in SCENARIOS for action in scenario.actions}
    assert {"door_add", "door_move", "bucky_w", "control_add", "control_rotate", "select_floor", "select_w"} <= actions
    assert len(SCENARIOS) >= 9


def test_xr21b_wall_design_invariant_detects_cross_control_leakage():
    room = _room()
    assert wall_snapshot(room) == {name: EXPECTED for name in WALLS}
    assert_wall_design_isolated(room, "clean", "initial")

    room.barriers[-1].material = "Concrete"
    room.barriers[-1].thickness_mm = 150.0
    try:
        assert_wall_design_isolated(room, "leak", "door_move")
    except AssertionError as exc:
        assert "W wall" in str(exc)
        assert "Concrete" in str(exc)
    else:
        raise AssertionError("XR-21B harness failed to detect W-wall construction leakage")
