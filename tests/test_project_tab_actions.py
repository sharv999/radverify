from pathlib import Path


def test_project_tab_actions_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    for name in [
        "new_project",
        "open_project",
        "save_project",
        "save_project_as",
        "apply_project_form",
        "refresh_project_form",
    ]:
        assert f"from tabs.project_tab_actions import {name}" in app_text
        assert f"return {name}(self)" in app_text
        assert f"def {name}(app)" in actions_text

    assert "from services.project_io import load_project_from_file, save_project_to_file" not in app_text
    assert "from services.project_ui_state import apply_loaded_project_to_ui" not in app_text
    assert "load_project_from_file(filename)" in actions_text
    assert "save_project_to_file(app, app.current_file)" in actions_text


def test_project_form_actions_live_in_actions_module():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    assert 'app.project_vars["Project Name"].set(app.project.project_name)' in actions_text
    assert 'self.project_vars["Project Name"].set(self.project.project_name)' not in app_text


def test_project_type_checkbox_maps_to_persisted_project_type():
    actions_text = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    assert '"refurbishment" if app.project_refurbishment_var.get() else "new_build"' in actions_text
    assert 'getattr(app.project, "project_type", "new_build")' in actions_text
