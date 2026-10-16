from services.barriers_modality_context import barriers_modality_context
from services.calculation_display_state import room_calculation_display_state
from services.xray_results_model import build_xray_results_model, xray_results_issueable
from tabs.results_barrier_maps import get_barrier_dose_label_map, get_barrier_risk_map
from tests.test_xray_xr08d_results_report_requalification import _App, _project


def _app_with_results(project):
    app = _App(project)
    app.get_room_by_name = lambda name: next((r for r in project.rooms if r.name == name), None)
    app.get_room_results_model = lambda room: build_xray_results_model(project, room)
    app.get_room_barrier_results = lambda room: build_xray_results_model(project, room)
    return app


def test_xr09_barriers_context_no_longer_displays_blocked_solver():
    p = _project(); room = p.rooms[0]
    context = barriers_modality_context(room, current_solver_mode="blocked")
    assert context.solver_display == "NCRP 147 §5.3 / Fig. 5.2"
    assert context.solver_editable is False
    assert "radiographic workload" in context.energy_basis_display


def test_xr09_live_display_gate_consumes_canonical_xr08e_results():
    p = _project(); app = _app_with_results(p); room = p.rooms[0]
    rows = app.get_room_results_model(room)
    assert xray_results_issueable(rows) is True
    state = room_calculation_display_state(app, room)
    assert state.blocking is False
    assert state.message == ""


def test_xr09_geometry_maps_equal_canonical_results_for_every_barrier():
    p = _project(); app = _app_with_results(p); room = p.rooms[0]
    rows = app.get_room_results_model(room)
    by_name = {row["barrier"]: row for row in rows}
    risk = get_barrier_risk_map(app, room.name)
    labels = get_barrier_dose_label_map(app, room.name)
    assert set(risk) == set(by_name)
    assert set(labels) == set(by_name)
    for name, row in by_name.items():
        expected = "fail" if row["compliance_status"] == "FAIL" or row["margin_mm"] < 0 else ("review" if row["compliance_status"] == "REVIEW" or row["margin_mm"] < 0.5 else "pass")
        assert risk[name] == expected
        assert f"Tx {row['transmitted_dose_uSv_per_week']:.2f} µSv/wk" in labels[name]
        assert f"Unsh {row['unshielded_weekly_dose_uSv']:.1f} µSv/wk" in labels[name]


def test_xr09_incomplete_fig52_result_set_blocks_live_display():
    p = _project(); app = _app_with_results(p); room = p.rooms[0]
    original = app.get_room_results_model
    app.get_room_results_model = lambda r: [{**original(r)[0], "issued_output_enabled": False}]
    state = room_calculation_display_state(app, room)
    assert state.blocking is True
    assert "not fully qualified" in state.message
