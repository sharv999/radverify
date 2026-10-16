from pathlib import Path


def test_results_barrier_maps_module_exists_and_owns_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    maps_text = Path("tabs/results_barrier_maps.py").read_text(encoding="utf-8")
    geometry_text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    scanner_text = Path("geometry/scanner_renderer.py").read_text(encoding="utf-8")

    assert "def get_barrier_dose_label_map(app, room_name: str) -> dict:" in maps_text
    assert "def get_barrier_risk_map(app, room_name: str) -> dict:" in maps_text

    assert "from tabs.results_barrier_maps import get_barrier_risk_map" not in app_text
    assert "from tabs.results_barrier_maps import get_barrier_dose_label_map" not in app_text

    assert "get_barrier_risk_map(self.app, room.name)" in geometry_text
    assert "get_barrier_dose_label_map(self.app, room.name)" in geometry_text
    assert "get_barrier_dose_label_map(self.app, room.name)" in scanner_text


def test_app_barrier_map_methods_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "def get_barrier_dose_label_map(self" not in app_text
    assert "def get_barrier_risk_map(self" not in app_text

    assert (
        "    def get_barrier_dose_label_map(self, room_name: str) -> dict:\n"
        "        from tabs.results_barrier_maps import get_barrier_dose_label_map"
    ) not in app_text

    assert (
        "    def get_barrier_risk_map(self, room_name: str) -> dict:\n"
        "        from tabs.results_barrier_maps import get_barrier_risk_map"
    ) not in app_text

def test_pet_geometry_risk_map_prefers_canonical_results_model(monkeypatch):
    from types import SimpleNamespace
    import tabs.results_barrier_maps as maps

    room = SimpleNamespace(
        name="PET Room 1",
        barriers=[SimpleNamespace(name="N wall"), SimpleNamespace(name="E wall")],
        geometry=SimpleNamespace(openings=[]),
    )

    class App:
        def get_room_by_name(self, name):
            return room if name == room.name else None

        def get_room_results_model(self, selected_room):
            assert selected_room is room
            return [
                {
                    "barrier_name": "N wall",
                    "results_source": "persisted_pet_single_source",
                    "compliance_status": "PASS",
                    "margin_mm": 10.56,
                },
                {
                    "barrier_name": "E wall",
                    "results_source": "persisted_pet_single_source",
                    "compliance_status": "FAIL",
                    "margin_mm": -0.8154,
                },
            ]

        def get_room_barrier_results(self, selected_room):
            return []

    # The legacy per-barrier calculator is not PET-aware.  If Geometry falls
    # back to it, both rows would appear FAIL/ERROR despite canonical Results.
    monkeypatch.setattr(
        maps,
        "get_barrier_live_result",
        lambda *_args, **_kwargs: {"compliance_status": "ERROR", "margin_mm": -1.0},
    )

    assert maps.get_barrier_risk_map(App(), room.name) == {
        "N wall": "pass",
        "E wall": "fail",
    }


def test_spect_geometry_dose_and_risk_maps_use_canonical_results_model(monkeypatch):
    from types import SimpleNamespace
    import tabs.results_barrier_maps as maps

    room = SimpleNamespace(
        name="SPECT Room 1",
        barriers=[SimpleNamespace(name="N wall")],
        geometry=SimpleNamespace(openings=[]),
    )

    class App:
        def get_room_by_name(self, name):
            return room if name == room.name else None

        def get_room_results_model(self, selected_room):
            assert selected_room is room
            return [{
                "barrier_name": "N wall",
                "results_source": "spect_step26_production_dispatch",
                "compliance_status": "PASS",
                "margin_mm": 1.25,
                "transmitted_dose_uSv_per_week": 3.5,
                "unshielded_weekly_dose_uSv": 25.0,
                "barrier_transmission_factor_B": 0.8,
            }]

        def get_room_barrier_results(self, selected_room):
            return []

    monkeypatch.setattr(
        maps,
        "get_barrier_live_result",
        lambda *_args, **_kwargs: {"compliance_status": "ERROR", "margin_mm": -1.0},
    )

    assert maps.get_barrier_risk_map(App(), room.name) == {"N wall": "pass"}
    assert maps.get_barrier_dose_label_map(App(), room.name)["N wall"] == (
        "Tx 3.50 µSv/wk\nUnsh 25.0 µSv/wk\nB=0.800000"
    )
