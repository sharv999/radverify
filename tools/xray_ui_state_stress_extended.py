"""XR-21C extended deterministic Tk UI state-transition stress harness for General X-ray.

Run under a graphical desktop (Windows) or xvfb-run on Linux.  Every case reports
PASS/FAIL independently and the process exits non-zero if any case fails.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Iterable

from models.shielding_models import project_to_dict
from services.project_io import load_project_from_file, write_project_payload
from services.project_ui_state import apply_loaded_project_to_ui
from tools.xray_ui_state_stress import EXPECTED, WALLS, _act, _reset_to_new_gxr, wall_snapshot


@dataclass(frozen=True)
class Case:
    name: str
    actions: tuple[str, ...]


CORE = ("door_add", "door_move", "bucky_w", "control_add", "control_rotate")

# Exhaustive ordering of the three independent GXR feature families, plus targeted
# state/selection and save/reopen transitions.  Continuous numeric entry makes a
# literally infinite UI state space, so XR-21C exhausts the finite feature-order
# combinations and representative boundary/state transitions instead.
CASES = tuple(
    Case("order_" + "_".join(p), p)
    for p in permutations(("door_add", "bucky_w", "control_add"))
) + (
    Case("door_move_before_bucky", ("door_add", "door_move", "bucky_w", "control_add")),
    Case("door_move_after_control", ("door_add", "control_add", "door_move", "bucky_w")),
    Case("selection_churn_before_features", ("select_floor", "select_w", "select_n", "door_add", "bucky_w", "control_add")),
    Case("selection_churn_between_features", ("door_add", "select_w", "bucky_w", "select_n", "control_add", "select_floor")),
    Case("control_rotate_before_door_move", ("control_add", "control_rotate", "door_add", "door_move", "bucky_w")),
    Case("control_four_rotations", ("control_add", "control_rotate", "control_rotate", "control_rotate", "control_rotate", "door_add", "bucky_w")),
    Case("bucky_all_walls_then_door", ("bucky_n", "bucky_e", "bucky_s", "bucky_w", "door_add", "door_move")),
    Case("door_all_walls_then_bucky", ("door_add", "door_e", "door_s", "door_w", "door_n", "bucky_w")),
)


def _assert_equal(actual, expected, case, step):
    if actual != expected:
        raise AssertionError(f"{case}: after {step}: expected {expected}, got {actual}")


def _baseline_expected():
    return {name: EXPECTED for name in WALLS}


def _save_reopen(app, path: Path):
    # Exercise the production save synchronisation before serialising.
    payload = app.prepare_project_for_save()
    write_project_payload(path, payload)
    restored = load_project_from_file(path)
    apply_loaded_project_to_ui(app, restored, path)
    app.update()
    return app.project.rooms[0]


def _set_selected_barrier(g, wall: str, material: str, thickness: str, t: str, p: str):
    g.barrier_wall_var.set(wall)
    g.load_selected_barrier_fields()
    g.barrier_material_var.set(material)
    # material trace supplies a standard thickness; explicit user value follows.
    g.barrier_thickness_var.set(thickness)
    g.barrier_t_var.set(t)
    g.p_var.set(p)
    g.on_p_changed()


def _run_case(app, case: Case):
    _reset_to_new_gxr(app)
    room = app.project.rooms[0]
    expected = _baseline_expected()
    _assert_equal(wall_snapshot(room), expected, case.name, "initial")
    for action in case.actions:
        _act(app.geometry_tab, action)
        app.update()
        _assert_equal(wall_snapshot(room), expected, case.name, action)


def _run_save_reopen_case(app, prefix: tuple[str, ...], suffix: tuple[str, ...], name: str):
    _reset_to_new_gxr(app)
    expected = _baseline_expected()
    room = app.project.rooms[0]
    for action in prefix:
        _act(app.geometry_tab, action); app.update()
        _assert_equal(wall_snapshot(room), expected, name, action)
    with TemporaryDirectory() as td:
        room = _save_reopen(app, Path(td) / "xr21c.json")
        _assert_equal(wall_snapshot(room), expected, name, "save_reopen")
        for action in suffix:
            _act(app.geometry_tab, action); app.update()
            _assert_equal(wall_snapshot(room), expected, name, "post_reopen_" + action)


def _run_deliberate_edit_case(app, name: str, suffix: tuple[str, ...]):
    _reset_to_new_gxr(app)
    g = app.geometry_tab
    _set_selected_barrier(g, "N", "Concrete", "150", "0.5", "20 µSv/wk")
    app.update()
    expected = _baseline_expected()
    expected["N wall"] = ("Concrete", 150.0, 0.5, 20.0)
    room = app.project.rooms[0]
    _assert_equal(wall_snapshot(room), expected, name, "deliberate_N_edit")
    for action in suffix:
        _act(g, action); app.update()
        _assert_equal(wall_snapshot(room), expected, name, action)
    with TemporaryDirectory() as td:
        room = _save_reopen(app, Path(td) / "xr21c-edit.json")
        _assert_equal(wall_snapshot(room), expected, name, "save_reopen")
        _act(app.geometry_tab, "door_move"); app.update()
        _assert_equal(wall_snapshot(room), expected, name, "post_reopen_door_move")


def build_checks(app) -> list[tuple[str, Callable[[], None]]]:
    checks = [(c.name, lambda c=c: _run_case(app, c)) for c in CASES]
    feature_orders = tuple(permutations(("door_add", "bucky_w", "control_add")))
    for i, order in enumerate(feature_orders, 1):
        checks.append((
            f"save_reopen_order_{i}_continue",
            lambda order=order, i=i: _run_save_reopen_case(
                app, order, ("door_move", "control_rotate", "bucky_e", "bucky_w"),
                f"save_reopen_order_{i}_continue",
            ),
        ))
    checks.extend([
        ("save_reopen_selection_churn", lambda: _run_save_reopen_case(
            app, ("door_add", "select_w", "bucky_w", "control_add"),
            ("select_n", "door_move", "select_floor", "control_rotate"),
            "save_reopen_selection_churn")),
        ("save_reopen_door_wall_changes", lambda: _run_save_reopen_case(
            app, ("door_add", "door_e", "door_s"),
            ("door_w", "door_n", "bucky_w", "control_add"),
            "save_reopen_door_wall_changes")),
        ("save_reopen_bucky_wall_changes", lambda: _run_save_reopen_case(
            app, ("bucky_n", "bucky_e"),
            ("bucky_s", "bucky_w", "door_add", "control_add"),
            "save_reopen_bucky_wall_changes")),
        ("edited_barrier_then_selection", lambda: _run_deliberate_edit_case(
            app, "edited_barrier_then_selection", ("select_w", "select_floor", "select_n"))),
        ("edited_barrier_then_opening", lambda: _run_deliberate_edit_case(
            app, "edited_barrier_then_opening", ("door_add", "door_move", "door_e", "door_n"))),
        ("edited_barrier_then_bucky", lambda: _run_deliberate_edit_case(
            app, "edited_barrier_then_bucky", ("bucky_n", "bucky_e", "bucky_s", "bucky_w"))),
        ("edited_barrier_then_control", lambda: _run_deliberate_edit_case(
            app, "edited_barrier_then_control", ("control_add", "control_rotate", "control_rotate"))),
        ("edited_barrier_full_mix", lambda: _run_deliberate_edit_case(
            app, "edited_barrier_full_mix", ("door_add", "bucky_w", "control_add", "select_floor", "door_move", "control_rotate"))),
    ])
    return checks


def run_report() -> list[tuple[str, str, str]]:
    from app import ShieldingDesktopApp
    app = ShieldingDesktopApp(); app.withdraw()
    results = []
    try:
        for name, check in build_checks(app):
            try:
                check()
            except Exception as exc:
                results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
            else:
                results.append((name, "PASS", ""))
    finally:
        app.destroy()
    return results


def format_report(results):
    lines = ["XR-21C GXR extended UI state-transition stress report", "=" * 58]
    for i, (name, status, detail) in enumerate(results, 1):
        line = f"{i:02d}. {status:4s}  {name}"
        if detail: line += f" -- {detail}"
        lines.append(line)
    passed = sum(s == "PASS" for _, s, _ in results)
    failed = len(results) - passed
    lines += ["-" * 58, f"TOTAL: {len(results)}  PASS: {passed}  FAIL: {failed}"]
    return "\n".join(lines)


def main():
    results = run_report()
    print(format_report(results))
    if any(status == "FAIL" for _, status, _ in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
