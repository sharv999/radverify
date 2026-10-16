"""XR-21B deterministic Tk UI state-isolation stress harness for General X-ray."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

WALLS = ("N wall", "E wall", "S wall", "W wall")
EXPECTED = ("Pb", 0.88, 1.0, 10.0)

@dataclass(frozen=True)
class Scenario:
    name: str
    actions: tuple[str, ...]

SCENARIOS = (
    Scenario("door_then_bucky", ("door_add", "door_move", "bucky_w")),
    Scenario("bucky_then_door", ("bucky_w", "door_add", "door_move")),
    Scenario("door_control_bucky", ("door_add", "control_add", "door_move", "bucky_w")),
    Scenario("control_door_bucky", ("control_add", "door_add", "door_move", "bucky_w")),
    Scenario("bucky_control_door", ("bucky_w", "control_add", "door_add", "door_move")),
    Scenario("selection_churn", ("select_floor", "select_w", "select_n", "door_add", "bucky_w")),
    Scenario("control_rotation", ("control_add", "control_rotate", "door_add", "door_move", "bucky_w")),
    Scenario("bucky_move", ("bucky_n", "bucky_e", "bucky_s", "bucky_w")),
    Scenario("door_wall_move", ("door_add", "door_e", "door_s", "door_n", "bucky_w")),
)

def wall_snapshot(room):
    out = {}
    for b in room.barriers:
        if b.name in WALLS:
            out[b.name] = (
                str(b.material), round(float(b.thickness_mm), 6),
                round(float(b.occupancy_factor), 6),
                round(float(b.design_goal_uSv_per_week), 6),
            )
    return out

def assert_wall_design_isolated(room, scenario: str, action: str):
    snap = wall_snapshot(room)
    expected = {name: EXPECTED for name in WALLS}
    if snap != expected:
        raise AssertionError(f"{scenario}: after {action}: expected {expected}, got {snap}")

def _reset_to_new_gxr(app):
    app.room_modality_var.set("CT")
    app.on_room_form_change()
    app.room_modality_var.set("X-ray")
    app.on_room_form_change()
    app.update()

def _act(g, action):
    if action == "door_add":
        g.opening_wall_var.set("N"); g.opening_offset_var.set("1.0"); g.add_opening()
    elif action == "door_move":
        g.opening_offset_var.set("3.0"); g.on_opening_selector_field_change()
    elif action.startswith("door_") and action[-1].upper() in "NESW":
        g.opening_wall_var.set(action[-1].upper()); g.on_opening_selector_field_change()
    elif action.startswith("bucky_"):
        g.xray_bucky_wall_var.set(action[-1].upper()); g.xray_bucky_offset_var.set("1.0"); g.add_or_update_xray_chest_receptor()
    elif action == "control_add":
        g.add_or_update_xray_control_wall()
    elif action == "control_rotate":
        g.rotate_xray_control_wall_cw()
    elif action.startswith("select_"):
        key = action.split("_", 1)[1]
        g.barrier_wall_var.set({"floor":"Floor", "n":"N", "w":"W"}[key])
    else:
        raise ValueError(action)

def run_scenarios(scenarios: Iterable[Scenario] = SCENARIOS):
    from app import ShieldingDesktopApp
    app = ShieldingDesktopApp()
    app.withdraw()
    completed = 0
    try:
        for scenario in scenarios:
            _reset_to_new_gxr(app)
            room = app.project.rooms[0]
            assert_wall_design_isolated(room, scenario.name, "initial")
            for action in scenario.actions:
                _act(app.geometry_tab, action)
                app.update()
                assert_wall_design_isolated(room, scenario.name, action)
            completed += 1
    finally:
        app.destroy()
    return completed

def main():
    count = run_scenarios()
    print(f"XR-21B UI state-isolation stress: PASS ({count} scenarios)")

if __name__ == "__main__":
    main()
