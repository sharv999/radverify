from pathlib import Path

from modalities.ct import CT_PLUGIN


def test_ct_plugin_preserves_existing_geometry_source_params():
    existing = {
        "scanner_family": "saved-family",
        "scanner_model": "Saved Scanner",
        "ksec_mGy_per_100mAs_at_1m": "",
        "scanner_ksec_status": "manual_override_required",
        "scans_per_week": 25,
        "workload_mAs_per_scan": 400,
    }

    params = CT_PLUGIN.prepare_geometry_source_params(
        "ct_scatter",
        existing,
        {"selected_source_type": "ct_scatter", "selected_model": "Other Scanner"},
    )

    assert params["scanner_family"] == "saved-family"
    assert params["scanner_model"] == "Saved Scanner"
    assert params["ksec_mGy_per_100mAs_at_1m"] == ""
    assert params["scanner_ksec_status"] == "manual_override_required"
    assert params["scans_per_week"] == 25
    assert params["workload_mAs_per_scan"] == 400


def test_generic_geometry_sync_refreshes_display_from_canonical_source():
    text = Path("geometry/source_sync.py").read_text(encoding="utf-8")

    assert "def _refresh_geometry_scanner_display_from_source" in text
    assert "self._refresh_geometry_scanner_display_from_source(room)" in text
    assert "self._update_scanner_ksec_label()" in text


def test_geometry_sync_delegates_source_state_to_plugin():
    text = Path("geometry/source_sync.py").read_text(encoding="utf-8")

    assert 'if selected_type == "CT"' not in text
    assert 'elif selected_type == "SPECT/CT"' not in text
    assert 'elif selected_type == "X-ray"' not in text
    assert "for source_spec in plugin.source_specs():" in text
    assert "params = plugin.prepare_geometry_source_params(" in text
    assert "selected_source_params" not in text
    assert "_scanner_params_from_selection" not in text
