from modalities.registry import (
    geometry_ui_for_modality,
    get_modality_plugin,
    is_production_modality,
    source_calculation_blocked_reason,
    source_type_for_modality_role,
)
from modalities.xray import XRAY_CALCULATION_BLOCK_REASON, XRayModalityPlugin
from tabs.barrier_inline_values import xray_barrier_role_values


def test_xr04_general_xray_is_host_visible_but_output_blocked():
    assert is_production_modality("X-ray") is True
    plugin = get_modality_plugin("X-ray")
    assert isinstance(plugin, XRayModalityPlugin)
    assert source_calculation_blocked_reason("xray_primary") == XRAY_CALCULATION_BLOCK_REASON
    assert plugin.spec.expected_sources[0].dose_model == "not_implemented"


def test_xr04_geometry_uses_general_radiography_source_and_xray_machine_symbol():
    plugin = get_modality_plugin("X-ray")
    ui = geometry_ui_for_modality("X-ray")
    assert ui.static_options == ("General Radiography",)
    assert source_type_for_modality_role("X-ray", ui.primary_source_role) == "xray_primary"
    assert plugin.layout_rendering().source_symbol_kind == "xray_machine"
    assert plugin.layout_rendering().show_radiation_symbol is False


def test_xr04_barrier_roles_cover_primary_and_secondary_general_xray_geometry():
    # XR-08C supersedes the coarse XR-04 primary/secondary roles with the
    # qualified NCRP 147 Section 5.3 / Figure 5.2 scenario vocabulary.
    assert xray_barrier_role_values() == [
        "fig52_chest_bucky_wall",
        "fig52_cross_table_wall",
        "fig52_secondary_wall",
        "fig52_control_wall",
        "fig52_door",
        "fig52_darkroom_wall",
        "fig52_floor_under_table",
        "fig52_ceiling",
    ]
