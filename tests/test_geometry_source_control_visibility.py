from modalities.base import GeometryUISpec
from tabs.geometry_tab import GeometryTab


class _Widget:
    def __init__(self):
        self.visible = True

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class _Var:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Harness:
    _update_source_control_visibility = GeometryTab._update_source_control_visibility

    def __init__(self):
        self.source_option_label = _Widget()
        self.source_option_combo = _Widget()
        self.scanner_ksec_label = _Widget()
        self.scanner_ksec_value_label = _Widget()
        self.scanner_ksec_energy_label = _Widget()
        self.scanner_ksec_energy_value_label = _Widget()
        self.source_option_var = _Var("Aquilion Exceed LB")
        self.scanner_ksec_var = _Var("0.005 mGy/100 mAs @ 1 m")
        self.scanner_ksec_energy_var = _Var("140 kVp")


def test_spect_geometry_hides_ct_scanner_and_ksec_controls():
    h = _Harness()
    h._update_source_control_visibility(GeometryUISpec(selector_kind="none"))

    assert not h.source_option_label.visible
    assert not h.source_option_combo.visible
    assert not h.scanner_ksec_label.visible
    assert not h.scanner_ksec_value_label.visible
    assert not h.scanner_ksec_energy_label.visible
    assert not h.scanner_ksec_energy_value_label.visible
    assert h.source_option_var.get() == ""
    assert h.scanner_ksec_var.get() == ""
    assert h.scanner_ksec_energy_var.get() == ""


def test_ct_geometry_shows_scanner_and_ksec_controls():
    h = _Harness()
    h._update_source_control_visibility(GeometryUISpec(selector_kind="ct_scanner_database"))

    assert h.source_option_label.visible
    assert h.source_option_combo.visible
    assert h.scanner_ksec_label.visible
    assert h.scanner_ksec_value_label.visible
    assert h.scanner_ksec_energy_label.visible
    assert h.scanner_ksec_energy_value_label.visible


def test_non_ct_selector_can_show_config_without_ct_ksec_metadata():
    h = _Harness()
    h._update_source_control_visibility(
        GeometryUISpec(selector_kind="static", static_options=("Option A",))
    )

    assert h.source_option_label.visible
    assert h.source_option_combo.visible
    assert not h.scanner_ksec_label.visible
    assert not h.scanner_ksec_value_label.visible
    assert not h.scanner_ksec_energy_label.visible
    assert not h.scanner_ksec_energy_value_label.visible
    assert h.source_option_var.get() == "Aquilion Exceed LB"
    assert h.scanner_ksec_var.get() == ""
    assert h.scanner_ksec_energy_var.get() == ""
