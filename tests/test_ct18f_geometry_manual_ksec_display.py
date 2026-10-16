from pathlib import Path
from types import SimpleNamespace

from services.ct_source_display import build_ct_source_display_state


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyScannerDatabase:
    def get_scanner(self, family):
        raise AssertionError("manual override display must not fall back to scanner DB")


class DummyGeometry:
    def __init__(self, source):
        self.source = source


class DummyGeometryTab:
    from tabs.geometry_tab import GeometryTab

    _update_scanner_ksec_label = GeometryTab._update_scanner_ksec_label
    _selected_scanner_ksec_energy_fallback = lambda self, selected_family_id="": "140 kVp"

    def __init__(self, source):
        self.source_option_var = Var("Philips Brilliance 64")
        self.scanner_ksec_var = Var("")
        self.scanner_ksec_energy_var = Var("")
        # Deliberately omit Philips Brilliance 64 from the display map. This
        # reproduces the real UI problem where the combobox display can differ
        # from the scanner_family key.
        self._scanner_display_to_family = {}
        self.scanner_db = DummyScannerDatabase()
        self._room = SimpleNamespace(name="CT Room 1")
        self.app = SimpleNamespace(
            get_sources_for_room=lambda room_name: [source],
        )

    def get_selected_room(self):
        return self._room


def test_geometry_room_load_does_not_call_scanner_change_handler():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    start = text.index("    def load_selected_room_geometry")
    end = text.index("    def draw_room_with_risk", start)
    block = text[start:end]

    assert "self.on_geometry_scanner_changed()" not in block
    assert "Source params are authoritative on room load" in block
    assert "self._update_scanner_ksec_label()" in block


def test_geometry_display_state_uses_manual_ksec_even_when_source_text_mentions_null():
    state = build_ct_source_display_state(
        "ct_scatter",
        {
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "manual_ksec_override": "1",
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "scanner_kvp": 140,
            "scanner_source": (
                "NULL ksec — manual override required "
                "(Selected scanner has NULL ksec in ct_scatter_master_database.json)"
            ),
        },
    )

    assert state.basis == "manual_override"
    assert state.is_manual_override
    assert "0.015 mGy/100 mAs @ 1 m" in state.ksec_display
    assert "manual override" in state.ksec_display
    assert "NULL — manual override" not in state.ksec_display


def test_geometry_ksec_label_prefers_manual_room_source_over_combobox_mismatch():
    src = SimpleNamespace(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "manual_ksec_override": "1",
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "scanner_kvp": 140,
            "scanner_source": "NULL ksec — manual override required",
        },
    )

    tab = DummyGeometryTab(src)
    tab._update_scanner_ksec_label()

    assert "0.015 mGy/100 mAs @ 1 m" in tab.scanner_ksec_var.get()
    assert "manual override" in tab.scanner_ksec_var.get()
    assert "NULL — manual override" not in tab.scanner_ksec_var.get()
