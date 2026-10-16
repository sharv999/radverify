from pathlib import Path


def test_single_room_actions_are_owned_by_project_tab_actions():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    assert "from tabs.rooms_tab_actions" not in app_text
    assert "from tabs.project_tab_actions import refresh_single_room_state" in app_text
    assert "from tabs.project_tab_actions import on_room_form_change" in app_text
    assert "from tabs.project_tab_actions import load_selected_room" in app_text
    assert "def refresh_single_room_state(app" in actions_text
    assert "def on_room_form_change(app" in actions_text
    assert "def apply_room_form(app" in actions_text


def test_multi_room_mutators_are_removed_from_app_surface():
    app_text = Path("app.py").read_text(encoding="utf-8")
    project_actions = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    assert "def add_room(self)" not in app_text
    assert "def delete_room(self)" not in app_text
    assert "def add_room(app" not in project_actions
    assert "def delete_room(app" not in project_actions
