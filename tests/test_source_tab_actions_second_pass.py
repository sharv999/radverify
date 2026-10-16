from pathlib import Path


def test_remaining_source_tab_actions_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/source_tab_actions.py").read_text(encoding="utf-8")

    for name in [
        "refresh_sources_list",
        "get_selected_source_index",
        "on_sources_room_change",
        "clear_source_form",
        "on_source_form_change",
        "persist_previous_selected_source",
        "load_selected_source",
        "add_source",
        "delete_source",
        "update_source_options",
        "sync_current_source_to_model",
        "apply_source_form",
        "refresh_source_calculations",
    ]:
        assert f"from tabs.source_tab_actions import {name}" in app_text
        assert f"def {name}(app" in actions_text


def test_app_source_actions_are_thin_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/source_tab_actions.py").read_text(encoding="utf-8")

    assert "    def add_source(self):\n        from tabs.source_tab_actions import add_source" in app_text
    assert "    def delete_source(self):\n        from tabs.source_tab_actions import delete_source" in app_text
    assert 'messagebox.showwarning("No room", "Create or select a room first.")' not in app_text
    assert 'messagebox.showwarning("No room", "Create or select a room first.")' in actions_text