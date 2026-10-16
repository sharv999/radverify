from types import SimpleNamespace

from tabs.results_barrier_maps import get_barrier_dose_label_map, get_barrier_risk_map


class DummyApp:
    def __init__(self, room):
        self.room = room

    def get_room_by_name(self, room_name):
        return self.room if room_name == self.room.name else None

    def get_room_barrier_results(self, room):
        # Deliberately stale cached result. Geometry overlay must not use this
        # when the Barriers-tab live helper has current PASS data.
        return [
            {
                "transmitted_dose_uSv_per_week": 29.58,
                "compliance_status": "FAIL",
                "margin_mm": -1.0,
            }
        ]


def test_geometry_overlay_maps_prefer_live_barrier_results(monkeypatch):
    room = SimpleNamespace(
        name="CT Room 1",
        barriers=[SimpleNamespace(name="N wall")],
        geometry=SimpleNamespace(openings=[]),
    )
    app = DummyApp(room)

    def fake_live_result(app_arg, room_arg, barrier_arg):
        assert app_arg is app
        assert room_arg is room
        assert barrier_arg is room.barriers[0]
        return {
            "transmitted_dose_uSv_per_week": 2.465,
            "compliance_status": "PASS",
            "margin_mm": 0.9,
        }

    monkeypatch.setattr(
        "tabs.results_barrier_maps.get_barrier_live_result",
        fake_live_result,
    )

    assert get_barrier_dose_label_map(app, "CT Room 1")["N wall"] == "Tx 2.46 µSv/wk"
    assert get_barrier_risk_map(app, "CT Room 1")["N wall"] == "pass"
