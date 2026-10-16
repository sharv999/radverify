from pathlib import Path


def test_ct_source_actions_are_owned_by_plugin_boundary():
    app_text = Path("app.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")

    assert "def handle_source_form_event" in ct_text
    assert "central_ct_ksec_resolver" in ct_text
    assert "update_ct_source_ksec_from_selector" not in app_text
