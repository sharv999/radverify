from pathlib import Path


def test_ct_form_state_is_owned_by_plugin_boundary():
    app_text = Path("app.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    sync_text = Path("sources/source_form_sync.py").read_text(encoding="utf-8")

    assert "def collect_source_form_params" in ct_text
    assert "def load_source_form_params" in ct_text
    assert "self.ct_vars" not in sync_text
    assert "ct_vars" not in app_text
