from pathlib import Path


def test_source_form_state_module_exists_and_owns_reload_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    state_text = Path("tabs/source_form_state.py").read_text(encoding="utf-8")

    assert "from tabs.source_form_state import reload_source_ui_from_model" in app_text
    assert "def reload_source_ui_from_model(" in state_text
    assert "app.load_source_params_into_form(src)" in state_text
    assert "app.update_live_source_preview_from_form()" in state_text


def test_app_source_form_state_method_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _reload_source_ui_from_model(" in app_text
    assert "from tabs.source_form_state import reload_source_ui_from_model" in app_text
    assert "return reload_source_ui_from_model(" in app_text
    assert "self.load_source_params_into_form(src)" not in app_text
