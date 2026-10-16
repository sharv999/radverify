import pytest

from engine.xray_ncrp147_fig52 import (
    FIG52_VERSION,
    Fig52Component,
    component_required_structural_mm,
    representative_fig52_scenarios,
    required_joint_structural_mm,
    solve_fig52_scenario,
)


def test_fig52_scenario_inventory_covers_every_section_53_barrier_case():
    scenarios = representative_fig52_scenarios()
    assert list(scenarios) == [
        "floor_under_table", "ceiling", "chest_bucky_wall",
        "darkroom_wall", "cross_table_wall", "control_wall",
    ]
    assert [s.section for s in scenarios.values()] == ["5.3.1", "5.3.2", "5.3.3", "5.3.4", "5.3.5", "5.3.6"]


def test_531_floor_primary_reproduces_107_mm_total_and_35_mm_structural_concrete():
    c = representative_fig52_scenarios()["floor_under_table"].components[0]
    structural = component_required_structural_mm(c, 0.02, "Concrete")
    # NCRP worked example: 107 mm total, 72 mm table/receptor equivalent -> 35 mm structure.
    assert structural == pytest.approx(35.2, abs=1.0)


def test_531_floor_secondary_reproduces_about_33_mm_concrete_and_primary_governs():
    s = representative_fig52_scenarios()["floor_under_table"]
    result = solve_fig52_scenario(s, 0.02, "Concrete")
    assert result["individual_required_mm"]["secondary_floor"] == pytest.approx(33.8, abs=1.0)
    assert result["required_structural_mm"] == pytest.approx(result["individual_required_mm"]["primary_floor"])


def test_532_ceiling_reproduces_about_44_mm_concrete_first_principles_example():
    result = solve_fig52_scenario(representative_fig52_scenarios()["ceiling"], 0.02, "Concrete")
    assert result["required_structural_mm"] == pytest.approx(44.0, abs=1.0)


def test_533_chest_bucky_primary_reproduces_about_045_mm_structural_lead():
    s = representative_fig52_scenarios()["chest_bucky_wall"]
    result = solve_fig52_scenario(s, 0.10, "Pb")
    assert result["individual_required_mm"]["primary_chest_bucky"] == pytest.approx(0.45, abs=0.04)
    assert result["individual_required_mm"]["secondary_chest_bucky"] == pytest.approx(0.35, abs=0.03)
    assert result["required_structural_mm"] == pytest.approx(0.45, abs=0.04)


def test_534_darkroom_wall_reproduces_about_053_mm_lead_personnel_film_room_case():
    result = solve_fig52_scenario(representative_fig52_scenarios()["darkroom_wall"], 0.025, "Pb")
    assert result["required_structural_mm"] == pytest.approx(0.53, abs=0.04)


def test_535_cross_table_is_joint_not_max_of_independent_components():
    s = representative_fig52_scenarios()["cross_table_wall"]
    result = solve_fig52_scenario(s, 0.02, "Pb")
    max_individual = max(result["individual_required_mm"].values())
    assert result["combination"] == "joint"
    assert result["required_structural_mm"] > max_individual
    assert result["transmitted_sum_at_required_mm"] == pytest.approx(0.02, rel=1e-10)
    # First-principles two-component implementation is expected near 0.68 mm;
    # NCRP notes a more complete all-source calculation of about 0.78 mm.
    assert result["required_structural_mm"] == pytest.approx(0.68, abs=0.04)


def test_536_control_wall_reproduces_about_027_mm_lead_for_controlled_area():
    result = solve_fig52_scenario(representative_fig52_scenarios()["control_wall"], 0.10, "Pb")
    assert result["required_structural_mm"] == pytest.approx(0.27, abs=0.03)


def test_cross_table_preshield_is_grid_cassette_only_not_table_support():
    c = representative_fig52_scenarios()["cross_table_wall"].components[0]
    assert c.preshield == "grid_cassette"
    result = solve_fig52_scenario(representative_fig52_scenarios()["cross_table_wall"], 0.02, "Pb")
    primary = next(x for x in result["components"] if x["name"] == "primary_cross_table")
    assert primary["preshield_mm"] == pytest.approx(0.30)


def test_fig52_patient_scaling_is_deterministic():
    a = representative_fig52_scenarios(125)["control_wall"].components[0].unshielded_mGy_week
    b = representative_fig52_scenarios(250)["control_wall"].components[0].unshielded_mGy_week
    assert b == pytest.approx(2 * a)


def test_fig52_fail_closed_for_unqualified_material():
    c = Fig52Component("x", "secondary", 1.0, "all_barriers")
    with pytest.raises(ValueError, match="not qualified"):
        component_required_structural_mm(c, 0.02, "Gypsum")


def test_fig52_version_is_frozen_for_replay():
    result = solve_fig52_scenario(representative_fig52_scenarios()["control_wall"], 0.10, "Pb")
    assert result["fig52_version"] == FIG52_VERSION
