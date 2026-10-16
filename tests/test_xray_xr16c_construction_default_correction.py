import inspect

from geometry.room_defaults import get_standard_construction_for_material
from models.shielding_models import _parse_legacy_material


def test_xr16c_material_selection_has_sensible_standard_construction():
    assert get_standard_construction_for_material("Pb") == ("Pb", 0.88)
    assert get_standard_construction_for_material("Concrete") == ("Concrete", 150.0)
    assert get_standard_construction_for_material("Pb glass") == ("Pb glass", 2.20)


def test_xr16c_legacy_lead_glass_fallback_is_2_20_mm_pb_equivalent():
    assert _parse_legacy_material("Pb glass") == ("Pb glass", 2.20)


def test_xr16c_geometry_editor_couples_material_change_to_thickness():
    from tabs.geometry_tab import GeometryTab
    wall = inspect.getsource(GeometryTab.on_barrier_material_changed)
    control = inspect.getsource(GeometryTab.on_xray_control_material_changed)
    assert "get_standard_construction_for_material" in wall
    assert "barrier_thickness_var.set" in wall
    assert "get_standard_construction_for_material" in control
    assert "xray_control_thickness_var.set" in control


def test_xr16c_loading_saved_project_does_not_rewrite_persisted_construction():
    from tabs.geometry_tab import GeometryTab
    wall = inspect.getsource(GeometryTab.on_barrier_material_changed)
    control = inspect.getsource(GeometryTab.on_xray_control_material_changed)
    assert '_loading' in wall
    assert '_loading' in control
