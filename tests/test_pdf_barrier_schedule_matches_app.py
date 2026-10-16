from reports.report_generator import PDF_BARRIER_COLUMNS, PDF_BARRIER_HEADINGS


def test_pdf_barrier_schedule_matches_requested_report_view():
    assert list(PDF_BARRIER_COLUMNS) == [
        "name", "thickness_mm", "barrier_role", "distance_m", "occupancy_factor",
        "design_goal_uSv_per_week", "unshielded_weekly_dose_uSv",
        "transmitted_dose_uSv_per_week", "barrier_transmission_factor_B",
        "display_required_thickness_mm", "solver_used", "compliance_status",
    ]
    assert "material" not in PDF_BARRIER_COLUMNS
    assert "display_recommended_thickness_mm" not in PDF_BARRIER_COLUMNS
    assert "linear_attenuation_coefficient_cm_inv" not in PDF_BARRIER_COLUMNS


def test_pdf_barrier_schedule_uses_requested_human_report_headings():
    assert PDF_BARRIER_HEADINGS["thickness_mm"] == "Actual (mm)"
    assert PDF_BARRIER_HEADINGS["distance_m"] == "Distance (m)"
    assert PDF_BARRIER_HEADINGS["barrier_transmission_factor_B"] == "B"
    assert PDF_BARRIER_HEADINGS["display_required_thickness_mm"] == "Required (mm)"
    assert PDF_BARRIER_HEADINGS["solver_used"] == "Solver"
