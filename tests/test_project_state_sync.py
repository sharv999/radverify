from pathlib import Path
from types import SimpleNamespace

from services.project_state_sync import sync_project_state_from_ui


class DummyGeometryTab:
    def __init__(self, calls):
        self.calls = calls

    def update_model_from_fields(self, show_errors=False):
        self.calls.append(("geometry", show_errors))


class DummyApp:
    def __init__(self):
        self.calls = []
        self.project = SimpleNamespace(
            rooms=[
                SimpleNamespace(
                    name="CT Room 1",
                    barriers=[SimpleNamespace(name="N wall")],
                )
            ]
        )
        self.geometry_tab = DummyGeometryTab(self.calls)

    def apply_project_form(self):
        self.calls.append("apply_project_form")

    def persist_previous_selected_source(self):
        self.calls.append("persist_previous_selected_source")

    def sync_current_source_to_model(self, ignore_errors=True):
        self.calls.append(("sync_current_source_to_model", ignore_errors))

    def _repair_invalid_source_inventory(self):
        self.calls.append("_repair_invalid_source_inventory")

    def enforce_room_source_types(self, room):
        self.calls.append(("enforce_room_source_types", room.name))

    def _apply_geometry_to_selected_room_barriers(self, room):
        self.calls.append(("_apply_geometry_to_selected_room_barriers", room.name))

    def sync_room_sources_from_project(self, room):
        self.calls.append(("sync_room_sources_from_project", room.name))

    def _coerce_barrier_schema(self, barrier):
        self.calls.append(("_coerce_barrier_schema", barrier.name))

    def _sanitize_all_nm_patient_sources(self):
        self.calls.append("_sanitize_all_nm_patient_sources")


def test_project_state_sync_calls_expected_paths():
    app = DummyApp()

    result = sync_project_state_from_ui(app)

    assert result.ok
    assert "apply_project_form" in app.calls
    assert "persist_previous_selected_source" in app.calls
    assert ("sync_current_source_to_model", True) in app.calls
    assert ("geometry", False) in app.calls
    assert "_repair_invalid_source_inventory" in app.calls
    assert ("enforce_room_source_types", "CT Room 1") in app.calls
    assert ("_apply_geometry_to_selected_room_barriers", "CT Room 1") in app.calls
    assert ("sync_room_sources_from_project", "CT Room 1") in app.calls
    assert ("_coerce_barrier_schema", "N wall") in app.calls
    assert "_sanitize_all_nm_patient_sources" in app.calls


def test_project_state_sync_collects_noncritical_warnings():
    class WarningApp(DummyApp):
        def apply_project_form(self):
            raise RuntimeError("boom")

    app = WarningApp()
    result = sync_project_state_from_ui(app)

    assert result.ok
    assert any("apply_project_form" in warning for warning in result.warnings)


def test_app_has_single_prepare_project_for_save():
    text = Path("app.py").read_text(encoding="utf-8")

    assert text.count("def prepare_project_for_save") == 1
    assert "sync_project_state_for_save(self)" in text
