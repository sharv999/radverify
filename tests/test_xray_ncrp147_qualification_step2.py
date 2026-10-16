import pytest

from engine.shielding_engine import (
    required_xray_ncrp147_thickness_mm,
    xray_ncrp147_archer_params,
    xray_ncrp147_transmission_from_thickness,
)


def test_table_b1_primary_bucky_coefficients_are_workload_specific():
    p = xray_ncrp147_archer_params("primary_bucky_wall", "Pb")
    assert p == pytest.approx({"alpha": 2.264, "beta": 13.08, "gamma": 0.5600})


def test_table_b1_primary_floor_concrete_reproduces_ncrp147_example_total_thickness():
    # NCRP 147 section 5.3.1: B ~= 5.1e-4 gives about 107 mm total concrete
    # before the 72 mm table/image-receptor preshielding is credited.
    x = required_xray_ncrp147_thickness_mm(5.1e-4, "primary_floor", "Concrete")
    assert x == pytest.approx(107.2, abs=0.5)


def test_table_c1_secondary_concrete_reproduces_radiographic_floor_example():
    # 125 patients/week, 0.034 mGy/patient at 1 m, d=3 m -> 0.4722 mGy/week.
    # P=0.02 mGy/week therefore requires B ~= 0.04235; NCRP example gives 33 mm.
    B = 0.02 / (125.0 * 0.034 / 9.0)
    x = required_xray_ncrp147_thickness_mm(B, "secondary_wall", "Concrete")
    assert x == pytest.approx(33.8, abs=1.0)


def test_table_c1_secondary_lead_reproduces_published_radiographic_example():
    # Published NCRP radiographic-room example: B=9.53e-3 -> about 0.77 mm Pb.
    x = required_xray_ncrp147_thickness_mm(9.53e-3, "secondary_wall", "Pb")
    assert x == pytest.approx(0.77, abs=0.02)


@pytest.mark.parametrize(
    "role,material,B",
    [
        ("primary_bucky_wall", "Pb", 9.3e-4),
        ("primary_floor", "Concrete", 5.1e-4),
        ("secondary_wall", "Pb", 9.53e-3),
        ("secondary_wall", "Concrete", 4.3e-2),
    ],
)
def test_archer_forward_inverse_round_trip(role, material, B):
    x = required_xray_ncrp147_thickness_mm(B, role, material)
    assert xray_ncrp147_transmission_from_thickness(x, role, material) == pytest.approx(B, rel=1e-12)


def test_unqualified_material_fails_closed():
    with pytest.raises(ValueError, match="not yet qualified"):
        required_xray_ncrp147_thickness_mm(0.01, "secondary_wall", "Gypsum")


def test_unqualified_role_fails_closed():
    with pytest.raises(ValueError, match="not qualified"):
        required_xray_ncrp147_thickness_mm(0.01, "primary_ceiling", "Pb")
