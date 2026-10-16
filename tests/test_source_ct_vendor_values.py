from pathlib import Path


def test_scanner_selector_values_are_plugin_owned():
    app_text = Path("app.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    layout_text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")

    assert "def source_form_vendor_values" in ct_text
    assert "def source_form_model_values" in ct_text
    assert "ct_vendor_values_for_source_type" not in app_text
    assert "self.source_form_vendor_values(app, source_type)" in ct_text
    assert "self.source_form_model_values(app, source_type)" in ct_text
    assert "source_form_schema_for_type(stype, app)" in layout_text
