from pathlib import Path

from modalities.ct import CT_PLUGIN


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _App:
    ct_vars = {
        "scanner_model": _Var("Live Scanner"),
        "ksec_mGy_per_100mAs_at_1m": _Var("0.012"),
        "scans_per_week": _Var("45"),
        "workload_mAs_per_scan": _Var("500"),
    }


def test_ct_plugin_prepares_complete_geometry_source_view():
    view = CT_PLUGIN.prepare_geometry_source_view(
        (
            {
                "name": "CT source",
                "source_type": "ct_scatter",
                "params": {
                    "scanner_family": "family-1",
                    "scanner_model": "",
                    "scanner_kvp": 140,
                },
            },
        ),
        {"app": _App()},
    )

    assert view.source_type == "ct_scatter"
    assert view.label == "Live Scanner"
    assert view.render_metadata["scanner_family"] == "family-1"
    assert view.render_metadata["ksec_mGy_per_100mAs_at_1m"] == "0.012"
    assert view.render_metadata["scans_per_week"] == "45"
    assert view.render_metadata["workload_mAs_per_scan"] == "500"


def test_geometry_tab_does_not_prepare_ct_render_metadata():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    sync_text = Path("geometry/source_sync.py").read_text(encoding="utf-8")

    redraw = text[text.index("def draw_room_with_risk"):text.index("def refresh_from_model")]
    assert "_param_or_ct_var" not in redraw
    assert "getattr(self.app, \"ct_vars\"" not in redraw
    assert '"ct_scatter"' not in redraw
    assert "plugin.prepare_geometry_source_view(" in sync_text
    assert "geometry_source.render_metadata.update" in sync_text


def test_ct_specific_live_form_access_is_owned_by_ct_plugin():
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    sync_text = Path("geometry/source_sync.py").read_text(encoding="utf-8")

    assert 'getattr(app, "ct_vars"' in ct_text
    assert 'getattr(self.app, "ct_vars"' not in sync_text
