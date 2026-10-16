from types import SimpleNamespace

from services.ui_sync_guard import sync_geometry_source_barriers_for_room


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyGeometryTab:
    def __init__(self, room_name, replacement_family):
        self.room_select_var = Var(room_name)
        self.replacement_family = replacement_family

    def apply_geometry_source_to_project(self, room):
        # Simulate a geometry-owned source write that would normally clear a
        # manual override while re-applying scanner/source metadata.
        src = room.sources[0]
        src.params.update({
            "scanner_family": self.replacement_family,
            "ksec_mGy_per_100mAs_at_1m": "0.0457",
            "manual_ksec_override": "0",
            "scanner_source": "JSON worst-case Ksec lookup",
            "scanner_ksec_status": "database",
        })


class DummyApp:
    def __init__(self, replacement_family="PHILIPS_BRILLIANCE_64"):
        self.calls = []
        self.source = SimpleNamespace(
            source_type="ct_scatter",
            room_name="CT Room 1",
            params={
                "scanner_family": "PHILIPS_BRILLIANCE_64",
                "scanner_model": "Philips Brilliance 64",
                "ksec_mGy_per_100mAs_at_1m": "0.015",
                "manual_ksec_override": "1",
                "manual_ksec_reason": "Vendor manual extract",
                "manual_ksec_source_reference": "Philips document XYZ",
                "scanner_source": "Manual override entered in Sources tab",
                "scanner_ksec_status": "manual_override",
            },
        )
        self.room = SimpleNamespace(name="CT Room 1", sources=[self.source], barriers=[])
        self.project = SimpleNamespace(rooms=[self.room], sources=[self.source])
        self.geometry_tab = DummyGeometryTab("CT Room 1", replacement_family)
        self.sources_room_var = Var("")
        self.barriers_room_var = Var("")
        self.optimizer_last_recommendations = [{"stale": True}]

    def get_room_by_name(self, name):
        return self.room if name == self.room.name else None

    def get_sources_for_room(self, room_name):
        return [s for s in self.project.sources if s.room_name == room_name]

    def _apply_geometry_to_selected_room_barriers(self, room):
        self.calls.append("_apply_geometry_to_selected_room_barriers")

    def refresh_sources_list(self, preserve_index=0):
        self.calls.append(("refresh_sources_list", preserve_index))

    def refresh_barrier_schedule(self):
        self.calls.append("refresh_barrier_schedule")

    def refresh_results_tab(self):
        self.calls.append("refresh_results_tab")

    def set_status(self, message):
        self.calls.append(("set_status", message))


def test_geometry_sync_preserves_manual_ct_ksec_when_scanner_family_is_unchanged():
    app = DummyApp(replacement_family="PHILIPS_BRILLIANCE_64")

    result = sync_geometry_source_barriers_for_room(app, app.room)

    assert result.ok
    assert app.source.params["scanner_family"] == "PHILIPS_BRILLIANCE_64"
    assert app.source.params["manual_ksec_override"] == "1"
    assert app.source.params["ksec_mGy_per_100mAs_at_1m"] == "0.015"
    assert app.source.params["manual_ksec_reason"] == "Vendor manual extract"
    assert app.source.params["manual_ksec_source_reference"] == "Philips document XYZ"
    assert app.source.params["scanner_source"] == "Manual override entered in Sources tab"
    assert app.optimizer_last_recommendations == []
    assert app.sources_room_var.get() == "CT Room 1"
    assert app.barriers_room_var.get() == "CT Room 1"
    assert "restore_manual_ct_ksec_overrides[1]" in result.actions


def test_geometry_sync_does_not_restore_manual_ksec_after_scanner_family_changes():
    app = DummyApp(replacement_family="GE_REVOLUTION_APEX_FAMILY")

    result = sync_geometry_source_barriers_for_room(app, app.room)

    assert result.ok
    assert app.source.params["scanner_family"] == "GE_REVOLUTION_APEX_FAMILY"
    assert app.source.params["manual_ksec_override"] == "0"
    assert app.source.params["ksec_mGy_per_100mAs_at_1m"] == "0.0457"
    assert "restore_manual_ct_ksec_overrides[1]" not in result.actions


def test_geometry_sync_refreshes_sources_barriers_and_results_in_order():
    app = DummyApp()

    sync_geometry_source_barriers_for_room(app, app.room)

    assert app.calls.index(("refresh_sources_list", 0)) < app.calls.index("refresh_barrier_schedule")
    assert app.calls.index("refresh_barrier_schedule") < app.calls.index("refresh_results_tab")
