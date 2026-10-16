from tools.xray_ui_state_stress_extended import CASES, build_checks, format_report


def test_xr21c_exhausts_all_three_feature_family_orderings():
    order_cases = [c for c in CASES if c.name.startswith("order_")]
    assert len(order_cases) == 6
    assert len({c.actions for c in order_cases}) == 6


def test_xr21c_includes_required_extended_transition_classes():
    names = {c.name for c in CASES}
    assert {
        "selection_churn_before_features", "selection_churn_between_features",
        "control_four_rotations", "bucky_all_walls_then_door", "door_all_walls_then_bucky",
    } <= names
    text = open("tools/xray_ui_state_stress_extended.py", encoding="utf-8").read()
    for token in ("save_reopen", "edited_barrier_then_opening", "edited_barrier_then_bucky", "edited_barrier_then_control"):
        assert token in text


def test_xr21c_report_is_explicit_per_case_pass_fail():
    report = format_report([("alpha", "PASS", ""), ("beta", "FAIL", "boom")])
    assert "PASS  alpha" in report
    assert "FAIL  beta -- boom" in report
    assert "TOTAL: 2  PASS: 1  FAIL: 1" in report
