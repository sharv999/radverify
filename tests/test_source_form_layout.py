from pathlib import Path


def test_source_form_layout_module_exists_and_owns_form_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    layout_text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")

    assert "from tabs.source_form_layout import refresh_source_form_by_type" in app_text
    assert "from tabs.source_form_layout import update_auto_tvl_key_display" in app_text
    assert "from tabs.source_form_layout import on_xray_method_change" not in app_text

    assert "def refresh_source_form_by_type(app):" in layout_text
    assert "def update_auto_tvl_key_display(app):" in layout_text
    assert "def on_xray_method_change(app, event=None):" not in layout_text
    assert "Exam room type" not in layout_text
    assert "source_form_schema_for_type(stype, app)" in layout_text
    assert "source_form_tvl_params_for_type(source_type, app)" in layout_text


def test_app_source_form_methods_are_thin_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def refresh_source_form_by_type(self):\n        from tabs.source_form_layout import refresh_source_form_by_type" in app_text
    assert "    def update_auto_tvl_key_display(self):\n        from tabs.source_form_layout import update_auto_tvl_key_display" in app_text
    assert "Exam room type" not in app_text
    assert "Manual mode: primary barriers use B = P d² / (W U T)." not in app_text
