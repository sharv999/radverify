from types import SimpleNamespace

from services.project_state_sync import sync_project_state_from_ui


class DummyGeometryTab:
    def __init__(self, app):
        self.app = app

    def update_model_from_fields(self, show_errors=False):
        # Simulate the Geometry tab's stale scanner combobox rewriting the CT
        # source during output/save sync.
        src = self.app.project.sources[0]
        src.params = {
            "scanner_family": "GE_REVOLUTION_APEX",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "scanner_source": "stale geometry scanner",
        }

    def sync_geometry_source_metadata_from_project_source(self, room):
        room.geometry.source.ksec_mGy_per_100mAs_at_1m = (
            self.app.project.sources[0].params["ksec_mGy_per_100mAs_at_1m"]
        )


class DummyApp:
    def __init__(self):
        self.project = SimpleNamespace(
            sources=[
                SimpleNamespace(
                    name="Secondary scatter source diagnostic",
                    source_type="ct_scatter",
                    radiation_type="xray_140kvp",
                    room_name="CT Room 1",
                    params={
                        "scanner_family": "CANON_AQUILION_EXCEED_LB",
                        "scanner_model": "Canon Aquilion Exceed LB",
                        "ksec_mGy_per_100mAs_at_1m": 0.005,
                        "scanner_source": "canonical Sources tab scanner",
                    },
                )
            ],
            rooms=[
                SimpleNamespace(
                    name="CT Room 1",
                    barriers=[SimpleNamespace(name="N wall")],
                    geometry=SimpleNamespace(source=SimpleNamespace()),
                )
            ],
        )
        self.geometry_tab = DummyGeometryTab(self)

    def apply_project_form(self):
        pass

    def persist_previous_selected_source(self):
        pass

    def sync_current_source_to_model(self, ignore_errors=True):
        pass

    def _repair_invalid_source_inventory(self):
        pass

    def enforce_room_source_types(self, room):
        pass

    def _apply_geometry_to_selected_room_barriers(self, room):
        pass

    def sync_room_sources_from_project(self, room):
        room.sources = [s for s in self.project.sources if s.room_name == room.name]

    def _coerce_barrier_schema(self, barrier):
        pass

    def _sanitize_all_nm_patient_sources(self):
        pass


def test_output_sync_preserves_canonical_ct_source_when_geometry_combobox_is_stale():
    app = DummyApp()

    result = sync_project_state_from_ui(app)

    assert result.ok
    assert app.project.sources[0].params["scanner_family"] == "CANON_AQUILION_EXCEED_LB"
    assert app.project.sources[0].params["scanner_model"] == "Canon Aquilion Exceed LB"
    assert app.project.sources[0].params["ksec_mGy_per_100mAs_at_1m"] == 0.005
    assert "restore_ct_source_snapshots" in "\n".join(result.actions)
