from engine.shielding_engine import default_barriers
from geometry.barrier_sync import apply_geometry_to_selected_room_barriers
from geometry.geometry_nudge import GeometryNudgeMixin
from models.shielding_models import Room


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyApp:
    def create_default_room_geometry(self, room_name, modality):  # pragma: no cover
        raise AssertionError("test room already has geometry")

    def _coerce_barrier_schema(self, barrier):
        return None

    def enforce_room_source_types(self, room):
        return None


class DummyGeometryNudge(GeometryNudgeMixin):
    def __init__(self, app, room):
        self.app = app
        self.room = room
        self._loading = False
        self.draw_calls = 0
        self.change_calls = 0
        self.source_x_var = Var(room.geometry.source.x_m)
        self.source_y_var = Var(room.geometry.source.y_m)

        def on_change():
            self.change_calls += 1
            apply_geometry_to_selected_room_barriers(app, room)

        self.on_change = on_change

    def update_model_from_fields(self, show_errors=False):
        # Simulate the Geometry tab committing the visible source fields to the
        # RoomGeometry model.  The regression guard is that nudge_source_position()
        # must then fire on_change(), which updates barrier distances/results.
        self.room.geometry.source.x_m = float(self.source_x_var.get())
        self.room.geometry.source.y_m = float(self.source_y_var.get())

    def draw_room_with_risk(self):
        self.draw_calls += 1


def _distance_map(room):
    return {barrier.name: barrier.distance_m for barrier in room.barriers}


def test_ct07_source_position_nudge_recomputes_barrier_distances():
    room = Room(name="CT Room 1", modality="CT", barriers=default_barriers())
    room.geometry.length_m = 7.0
    room.geometry.width_m = 5.0
    room.geometry.source.x_m = 2.0
    room.geometry.source.y_m = 5.0

    # Prime with the previous CT-06 values observed before the source-position
    # change.  CT-07 must not leave these stale distances in Results.
    for barrier in room.barriers:
        if barrier.name == "N wall":
            barrier.distance_m = 3.0
        elif barrier.name == "E wall":
            barrier.distance_m = 3.0
        elif barrier.name == "S wall":
            barrier.distance_m = 4.0
        elif barrier.name == "W wall":
            barrier.distance_m = 2.0

    nudge = DummyGeometryNudge(DummyApp(), room)

    # Move source x from 2.0 m to 3.0 m in a 5.0 m wide room.
    nudge.nudge_source_position("x", 1.0)

    distances = _distance_map(room)
    assert nudge.change_calls >= 1
    assert distances["N wall"] == 2.0
    assert distances["S wall"] == 5.0
    assert distances["E wall"] == 2.0
    assert distances["W wall"] == 3.0
