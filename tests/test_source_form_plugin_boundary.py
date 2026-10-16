from pathlib import Path

from modalities.base import ModalityPlugin
from modalities.registry import source_owner_plugin


def test_ct_plugin_owns_scanner_services_and_form_state_contract():
    plugin = source_owner_plugin("ct_scatter")
    assert isinstance(plugin, ModalityPlugin)
    for method_name in (
        "initialise_app_services",
        "source_form_vendor_values",
        "source_form_model_values",
        "source_form_schema",
        "source_form_tvl_params",
        "handle_source_form_event",
        "collect_source_form_params",
        "load_source_form_params",
    ):
        assert callable(getattr(plugin, method_name))


def test_app_exposes_only_generic_source_selector_callbacks():
    app_text = Path("app.py").read_text(encoding="utf-8")
    assert "def on_ct_vendor_change" not in app_text
    assert "def on_ct_model_change" not in app_text
    assert "def on_ct_kvp_change" not in app_text
    assert "def update_ct_source_ksec_from_selector" not in app_text
    assert "def _ct_form_energy_to_kvp" not in app_text
    assert "def _load_scanner_databases" not in app_text
    assert "def on_source_selector_vendor_change" in app_text
    assert "def on_source_selector_model_change" in app_text
    assert "def on_source_selector_energy_change" in app_text
    assert "def refresh_selected_source_resolution" in app_text


def test_generic_form_sync_routes_plugin_owned_state():
    sync_text = Path("sources/source_form_sync.py").read_text(encoding="utf-8")
    assert "collect_plugin_source_form_params" in sync_text
    assert "load_plugin_source_form_params" in sync_text
    assert "self.ct_vars" not in sync_text
    assert "services.ct_scanner_resolution" not in sync_text


def test_form_layout_renders_plugin_owned_schema():
    layout_text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    xray_text = Path("modalities/xray.py").read_text(encoding="utf-8")
    assert "source_form_schema_for_type(stype, app)" in layout_text
    assert "render_plugin_source_form(app, f, stype, schema)" in layout_text
    assert "def source_form_schema" in ct_text
    assert "SourceFormFieldSpec(" in ct_text
    assert "def source_form_schema" in xray_text
    assert "def source_form_tvl_params" in xray_text
    assert "populate_ct_vendor_combo_values" not in layout_text
    assert "populate_ct_model_combo_values" not in layout_text


def test_source_form_sync_contains_no_xray_or_nm_collection_loading_branches():
    text = Path("sources/source_form_sync.py").read_text(encoding="utf-8")
    assert "primary_vars[" not in text
    assert "nm_vars[" not in text
    assert 'source_type in ("primary_xray", "xray_primary")' not in text
    assert 'source_type == "nm_patient"' not in text
    assert "collect_plugin_source_form_params" in text
    assert "load_plugin_source_form_params" in text


def test_xray_and_nm_plugins_own_source_form_collection_and_loading():
    xray_text = Path("modalities/xray.py").read_text(encoding="utf-8")
    registry_text = Path("modalities/registry.py").read_text(encoding="utf-8")
    assert "def collect_source_form_params" in xray_text
    assert "def load_source_form_params" in xray_text
    placeholder = registry_text.split("class _SpectCTPlaceholderPlugin", 1)[1].split(
        "_SPECT_CT_PLACEHOLDER_PLUGIN", 1
    )[0]
    assert "def collect_source_form_params" in placeholder
    assert "def load_source_form_params" in placeholder
