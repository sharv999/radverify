from tabs.barrier_table_formatting import format_barrier_table_cell


def test_pet_spect_barrier_table_uses_ct_style_numeric_precision():
    row = {
        "material": "Pb",
        "thickness_mm": 0.88,
        "distance_m": 2,
        "occupancy_factor": 0.2,
        "design_goal_uSv_per_week": 10,
        "unshielded_weekly_dose_uSv": 4318.654321,
        "transmitted_dose_uSv_per_week": 22.53491,
        "barrier_transmission_factor_B": 0.0115784321,
        "display_required_thickness_mm": 1.15049,
        "display_recommended_thickness_mm": 1.32,
        "linear_attenuation_coefficient_cm_inv": 50,
        "compliance_status": "PASS",
    }

    assert format_barrier_table_cell(row, "thickness_mm") == "0.88"
    assert format_barrier_table_cell(row, "distance_m") == "2.0"
    assert format_barrier_table_cell(row, "occupancy_factor") == "0.2"
    assert format_barrier_table_cell(row, "design_goal_uSv_per_week") == "10.0"
    assert format_barrier_table_cell(row, "unshielded_weekly_dose_uSv") == "4318.65"
    assert format_barrier_table_cell(row, "transmitted_dose_uSv_per_week") == "22.53"
    assert format_barrier_table_cell(row, "barrier_transmission_factor_B") == "0.011578"
    assert format_barrier_table_cell(row, "display_required_thickness_mm") == "1.15"
    assert format_barrier_table_cell(row, "display_recommended_thickness_mm") == "1.32"
    assert format_barrier_table_cell(row, "linear_attenuation_coefficient_cm_inv") == "50.0"


def test_concrete_actual_thickness_keeps_ct_style_one_decimal_place():
    row = {"material": "Concrete", "thickness_mm": 150}
    assert format_barrier_table_cell(row, "thickness_mm") == "150.0"


def test_small_required_thickness_retains_useful_third_decimal():
    row = {"material": "Pb", "display_required_thickness_mm": 0.705}
    assert format_barrier_table_cell(row, "display_required_thickness_mm") == "0.705"


def test_occupancy_factor_preserves_small_values_without_false_rounding():
    assert format_barrier_table_cell({"occupancy_factor": 1.0}, "occupancy_factor") == "1.0"
    assert format_barrier_table_cell({"occupancy_factor": 0.2}, "occupancy_factor") == "0.2"
    assert format_barrier_table_cell({"occupancy_factor": 0.05}, "occupancy_factor") == "0.05"
    assert format_barrier_table_cell({"occupancy_factor": 0.025}, "occupancy_factor") == "0.025"
