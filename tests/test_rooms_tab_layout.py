from pathlib import Path


def test_rooms_tab_is_removed_and_room_controls_live_on_project_tab():
    ui_text = Path("ui/main_window.py").read_text(encoding="utf-8")
    project_layout = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert 'text="Rooms"' not in ui_text
    assert "app.rooms_tab" not in ui_text
    assert "build_rooms_tab" not in app_text
    assert 'text="Room Name"' in project_layout
    assert 'text="Modality"' in project_layout
    assert "values=tuple(app.ROOM_TYPES)" in project_layout
    assert "Add Room" not in project_layout
    assert "Delete Room" not in project_layout


def test_existing_tab_delegates_are_preserved():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "from tabs.project_tab_layout import build_project_tab" in app_text
    assert "from tabs.source_tab_layout import build_sources_tab" in app_text
    assert "from tabs.results_tab_layout import build_results_tab" in app_text
    assert "from tabs.results_tab_actions import generate_outputs" in app_text
    assert "from tabs.ai_qa_tab_layout import build_ai_qa_tab" not in app_text
