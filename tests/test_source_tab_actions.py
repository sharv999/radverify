from types import SimpleNamespace

from tabs import source_tab_actions


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_ct_form_energy_to_kvp_defaults_safely():
    app = SimpleNamespace(ct_vars={})
    assert source_tab_actions.ct_form_energy_to_kvp(app) == 140

    app.ct_vars["scanner_kvp"] = DummyVar("bad")
    assert source_tab_actions.ct_form_energy_to_kvp(app) == 140


def test_ct_form_energy_to_kvp_reads_form_value():
    app = SimpleNamespace(ct_vars={"scanner_kvp": DummyVar("120")})
    assert source_tab_actions.ct_form_energy_to_kvp(app) == 120
