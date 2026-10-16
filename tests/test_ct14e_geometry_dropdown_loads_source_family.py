from types import SimpleNamespace

from geometry.source_sync import SourceSyncMixin


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyGeometry(SourceSyncMixin):
    def __init__(self):
        self.source_option_var = Var("GE Revolution Apex / Apex Elite")
        self._scanner_display_to_family = {
            "GE Revolution Apex / Apex Elite": "GE_REVOLUTION_APEX",
            "Canon Aquilion Exceed LB": "CANON_AQUILION_EXCEED_LB",
        }
        self.ksec_label_updates = 0
        source = SimpleNamespace(
            source_type="ct_scatter",
            params={"scanner_family": "CANON_AQUILION_EXCEED_LB"},
        )
        self.app = SimpleNamespace(
            ct_scanner_resolution_context=object(),
            get_sources_for_room=lambda room_name: [source],
        )

    def _update_scanner_ksec_label(self):
        self.ksec_label_updates += 1


def test_geometry_dropdown_loads_saved_source_family_not_first_option():
    tab = DummyGeometry()
    room = SimpleNamespace(name="CT Room 1")

    tab.load_scanner_from_room_source(room)

    assert tab.source_option_var.get() == "Canon Aquilion Exceed LB"
    assert tab.source_option_var.get() != "GE Revolution Apex / Apex Elite"
    assert tab.ksec_label_updates == 1
