from __future__ import annotations

from types import SimpleNamespace

from tabs.geometry_tab import GeometryTab


class _Widget:
    def __init__(self):
        self.visible = True
        self.values = ()

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def __setitem__(self, key, value):
        if key == "values":
            self.values = tuple(value)
            return
        raise KeyError(key)


class _Var:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Harness:
    """Exercise the real GeometryTab modality-switch orchestration without Tk."""

    _update_source_control_visibility = GeometryTab._update_source_control_visibility
    update_source_options = GeometryTab.update_source_options

    def __init__(self):
        self.source_type_var = _Var("CT")
        self.source_label_var = _Var("Canon Aquilion Exceed LB")
        self.source_option_var = _Var("")
        self.scanner_ksec_var = _Var("")
        self.scanner_ksec_energy_var = _Var("")
        self.source_option_label = _Widget()
        self.source_option_combo = _Widget()
        self.scanner_ksec_label = _Widget()
        self.scanner_ksec_value_label = _Widget()
        self.scanner_ksec_energy_label = _Widget()
        self.scanner_ksec_energy_value_label = _Widget()
        self._scanner_display_to_family = {}
        self._source_label_modality_id = "CT"
        self._loading = True
        self._ct_scanners = (
            SimpleNamespace(
                short_name="Aquilion Exceed LB",
                family_id="canon-aquilion-exceed-lb",
            ),
        )

    def _scanner_records_for_source_type(self, source_type_label):
        return self._ct_scanners if source_type_label == "CT" else ()

    @staticmethod
    def _scanner_display_value(scanner):
        return scanner.short_name

    def _update_scanner_ksec_label(self):
        # A deterministic stand-in for the CT database display update. The
        # switch-cycle assertions below are about visibility/state ownership,
        # not the ksec database itself.
        self.scanner_ksec_var.set("0.005 mGy/100 mAs @ 1 m")
        self.scanner_ksec_energy_var.set("140 kVp")

    def on_geometry_scanner_changed(self):
        self.source_label_var.set("Canon Aquilion Exceed LB")

    @staticmethod
    def get_selected_room():
        return None


def _assert_ct_controls(h):
    assert h.source_option_label.visible
    assert h.source_option_combo.visible
    assert h.scanner_ksec_label.visible
    assert h.scanner_ksec_value_label.visible
    assert h.scanner_ksec_energy_label.visible
    assert h.scanner_ksec_energy_value_label.visible
    assert h.source_option_combo.values == ("Aquilion Exceed LB",)
    assert h.source_option_var.get() == "Aquilion Exceed LB"
    assert h.scanner_ksec_var.get() == "0.005 mGy/100 mAs @ 1 m"
    assert h.scanner_ksec_energy_var.get() == "140 kVp"


def _assert_patient_only_controls(h):
    assert not h.source_option_label.visible
    assert not h.source_option_combo.visible
    assert not h.scanner_ksec_label.visible
    assert not h.scanner_ksec_value_label.visible
    assert not h.scanner_ksec_energy_label.visible
    assert not h.scanner_ksec_energy_value_label.visible
    assert h.source_option_combo.values == ()
    assert h.source_option_var.get() == ""
    assert h.scanner_ksec_var.get() == ""
    assert h.scanner_ksec_energy_var.get() == ""
    assert h._scanner_display_to_family == {}


def test_geometry_modality_switch_ct_spect_pet_ct_clears_and_restores_ct_controls():
    """CT-only Geometry UI state must not leak through patient modalities.

    This protects the real modality-switch path, not only the low-level widget
    visibility helper: CT -> SPECT -> PET -> CT must clear the scanner option,
    ksec display values, option list, and scanner-family map while non-CT is
    active, then repopulate them when CT is selected again.
    """
    h = _Harness()

    h.update_source_options()
    _assert_ct_controls(h)
    assert h.source_label_var.get() == "Canon Aquilion Exceed LB"
    h._loading = False
    assert h._scanner_display_to_family == {
        "Aquilion Exceed LB": "canon-aquilion-exceed-lb"
    }

    h.source_type_var.set("SPECT")
    h.update_source_options()
    _assert_patient_only_controls(h)
    assert h.source_label_var.get() == "SPECT Patient Source"

    # Seed deliberately stale CT display text before the next switch. PET must
    # clear it too, even when arriving from another non-CT modality.
    h.scanner_ksec_var.set("STALE CT KSEC")
    h.scanner_ksec_energy_var.set("STALE CT ENERGY")
    h.source_type_var.set("PET")
    h.update_source_options()
    _assert_patient_only_controls(h)
    assert h.source_label_var.get() == "PET Patient Source"

    h.source_type_var.set("CT")
    h.update_source_options()
    _assert_ct_controls(h)
    assert h.source_label_var.get() == "Canon Aquilion Exceed LB"
    assert h._scanner_display_to_family == {
        "Aquilion Exceed LB": "canon-aquilion-exceed-lb"
    }
