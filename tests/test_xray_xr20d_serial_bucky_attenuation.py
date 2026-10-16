import pytest

from engine.xray_ncrp147_fig52 import structural_transmission_factor
from services.xray_results_model import build_xray_results_model
from tests.test_xray_xr20a_bucky_subbarrier_canvas import _shielded_project


def test_xr20d_bucky_shield_attenuates_primary_and_secondary_components():
    project, room = _shielded_project()
    rows = build_xray_results_model(project, room)
    shield = next(r for r in rows if r["barrier"] == "Bucky shield")
    factors = shield["bucky_shield_component_transmissions"]
    assert factors["primary_chest_bucky"] == pytest.approx(
        structural_transmission_factor("primary", "chest_bucky", 2.2, "Pb"), rel=1e-6
    )
    assert factors["secondary_chest_bucky"] == pytest.approx(
        structural_transmission_factor("secondary", "chest_bucky", 2.2, "Pb"), rel=1e-6
    )
    assert factors["secondary_chest_bucky"] < 1.0


def test_xr20d_subbarrier_is_substantially_lower_than_parent_wall():
    project, room = _shielded_project()
    rows = build_xray_results_model(project, room)
    wall = next(r for r in rows if r["barrier"] == "N wall")
    shield = next(r for r in rows if r["barrier"] == "Bucky shield")
    assert shield["transmitted_dose_uSv_per_week"] < 0.1 * wall["transmitted_dose_uSv_per_week"]
    assert "all radiation traverses" in shield["bucky_shield_provenance"]
