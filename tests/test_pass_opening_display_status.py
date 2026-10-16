from __future__ import annotations


def test_opening_pass_with_adequate_margin_uses_pass_row_tag():
    """
    A PASS opening with adequate positive margin should display green/PASS.
    """
    from tabs.barriers_openings import _opening_row_tag_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": 0.700,
        "transmitted_dose_uSv_per_week": 2.473,
        "design_goal_uSv_per_week": 10.0,
    }

    assert _opening_row_tag_from_live(live) == "qa_pass"


def test_opening_pass_with_small_positive_margin_uses_review_row_tag():
    """
    A PASS opening with small positive margin should display amber/REVIEW.
    Applies equally to doors and viewing panels.
    """
    from tabs.barriers_openings import _opening_row_tag_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": 0.345,
        "transmitted_dose_uSv_per_week": 5.125,
        "design_goal_uSv_per_week": 10.0,
    }

    assert _opening_row_tag_from_live(live) == "qa_review"


def test_opening_with_negative_margin_uses_fail_row_tag():
    """
    An opening with negative margin should display red/FAIL.
    """
    from tabs.barriers_openings import _opening_row_tag_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": -0.620,
        "transmitted_dose_uSv_per_week": 22.006,
        "design_goal_uSv_per_week": 10.0,
    }

    assert _opening_row_tag_from_live(live) == "qa_fail"


def test_pass_viewing_panel_results_status_remains_pass_with_adequate_margin():
    """
    Results tab display status should remain PASS when margin is adequate.
    """
    from tabs.results_tab_rendering import result_status_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": 0.700,
        "transmitted_dose_uSv_per_week": 2.473,
        "design_goal_uSv_per_week": 10.0,
        "solver_used": "mu_plus_buildup",
    }

    assert result_status_from_live(live) == "PASS"


def test_results_status_small_positive_margin_is_review():
    """
    Results tab should show REVIEW for openings with small positive margin.
    """
    from tabs.results_tab_rendering import result_status_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": 0.345,
        "transmitted_dose_uSv_per_week": 5.125,
        "design_goal_uSv_per_week": 10.0,
    }

    assert result_status_from_live(live) == "REVIEW"


def test_results_status_negative_margin_is_fail():
    """
    Results tab should show FAIL for openings with negative margin.
    """
    from tabs.results_tab_rendering import result_status_from_live

    live = {
        "compliance_status": "PASS",
        "margin_mm": -0.620,
        "transmitted_dose_uSv_per_week": 22.006,
        "design_goal_uSv_per_week": 10.0,
    }

    assert result_status_from_live(live) == "FAIL"