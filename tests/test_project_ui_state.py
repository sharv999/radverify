from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.project_ui_state import apply_loaded_project_to_ui, ensure_valid_post_open_selection


class Var:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class DummyNotebook:
    def __init__(self, calls):
        self.calls = calls

    def select(self, tab):
        self.calls.append(("select", tab))


class DummyGeometryTab:
    def __init__(self, calls):
        self.calls = calls

    def refresh_room_list(self, preferred_room_name=None):
        self.calls.append(("geometry_refresh_room_list", preferred_room_name))


class DummyApp:
    def __init__(self):
        self.calls = []
        self.project = None
        self.current_file = None
        self.current_room_index = None
        self.current_source_index = None
        self.last_selected_source_index = 99
        self.last_selected_source_room_name = "Old room"
        self.sources_room_var = Var()
        self.barriers_room_var = Var()
        self.geometry_tab = DummyGeometryTab(self.calls)
        self.main_notebook = DummyNotebook(self.calls)
        self.project_tab = "project-tab"

    def _prune_unsupported_rooms(self):
        self.calls.append("_prune_unsupported_rooms")

    def refresh_all(self):
        self.calls.append("refresh_all")

    def refresh_sources_list(self, preserve_index=None):
        self.calls.append(("refresh_sources_list", preserve_index))

    def _reload_source_ui_from_model(self, room, index, refresh_live=False):
        self.calls.append(("_reload_source_ui_from_model", room.name, index, refresh_live))

    def _safe_refresh_barrier_schedule(self):
        self.calls.append("_safe_refresh_barrier_schedule")

    def refresh_results_tab(self):
        self.calls.append("refresh_results_tab")

    def set_status(self, message):
        self.calls.append(("set_status", message))


def test_apply_loaded_project_to_ui_sets_project_and_refreshes_selection():
    app = DummyApp()
    room = SimpleNamespace(name="Loaded CT Room")
    project = SimpleNamespace(rooms=[room])

    apply_loaded_project_to_ui(app, project, Path("example.json"))

    assert app.project is project
    assert app.current_file == Path("example.json")
    assert app.current_room_index == 0
    assert app.current_source_index == 0
    assert app.last_selected_source_index is None
    assert app.last_selected_source_room_name is None
    assert app.sources_room_var.value == "Loaded CT Room"
    assert app.barriers_room_var.value == "Loaded CT Room"
    assert "_prune_unsupported_rooms" in app.calls
    assert ("refresh_sources_list", 0) in app.calls
    assert ("_reload_source_ui_from_model", "Loaded CT Room", 0, True) in app.calls
    assert ("select", "project-tab") in app.calls
    assert any(call[0] == "set_status" for call in app.calls if isinstance(call, tuple))


def test_ensure_valid_post_open_selection_handles_empty_project():
    app = DummyApp()
    app.project = SimpleNamespace(rooms=[])

    ensure_valid_post_open_selection(app)

    assert app.calls == ["refresh_all"]
