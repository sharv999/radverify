from pathlib import Path


def test_geometry_changed_delegates_to_ui_sync_guard():
    text = Path("geometry/barrier_sync.py").read_text(encoding="utf-8")

    assert "from services.ui_sync_guard import" in text
    assert "sync_geometry_source_barriers_for_room(" in text
    assert "selected_geometry_room(app)" in text


def test_project_state_sync_runs_guarded_output_relevant_sync():
    text = Path("services/project_state_sync.py").read_text(encoding="utf-8")

    assert "from services.ui_sync_guard import sync_output_relevant_ui_state" in text
    assert 'run("sync_output_relevant_ui_state", lambda: sync_output_relevant_ui_state(app))' in text
