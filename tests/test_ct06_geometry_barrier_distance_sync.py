from types import SimpleNamespace

import pytest

from geometry.barrier_sync import apply_geometry_to_selected_room_barriers
from geometry.geometry_model import RoomGeometry
from models.shielding_models import Room
from engine.shielding_engine import default_barriers


class DummyApp:
    def __init__(self):
        self.enforce_calls = 0
        self.coerced = []

    def create_default_room_geometry(self, room_name, modality):
        return RoomGeometry(room_name=room_name)

    def _coerce_barrier_schema(self, barrier):
        self.coerced.append(barrier.name)

    def enforce_room_source_types(self, room):
        self.enforce_calls += 1


def _room_with_geometry(*, length=7.0, width=6.0, height=3.6, x=2.0, y=4.0):
    room = Room(
        name="CT Room 1",
        modality="CT",
        barriers=default_barriers(),
    )
    room.geometry = RoomGeometry(room_name=room.name)
    room.geometry.length_m = length
    room.geometry.width_m = width
    room.geometry.height_m = height
    room.geometry.source.x_m = x
    room.geometry.source.y_m = y
    return room


def _distances_by_name(room):
    return {barrier.name: barrier.distance_m for barrier in room.barriers}


def test_ct06_geometry_dimension_change_recomputes_wall_barrier_distances():
    app = DummyApp()
    room = _room_with_geometry(length=7.0, width=6.0, x=2.0, y=4.0)

    # Simulate stale values visible in the failing CT-06 screenshot.
    for barrier in room.barriers:
        if barrier.name in {"N wall", "E wall", "S wall", "W wall"}:
            barrier.distance_m = 2.0

    apply_geometry_to_selected_room_barriers(app, room)

    distances = _distances_by_name(room)
    assert distances["N wall"] == pytest.approx(3.0)
    assert distances["S wall"] == pytest.approx(4.0)
    assert distances["E wall"] == pytest.approx(4.0)
    assert distances["W wall"] == pytest.approx(2.0)
    assert app.enforce_calls == 1


def test_ct06_geometry_sync_preserves_existing_barrier_settings_while_updating_distance():
    app = DummyApp()
    room = _room_with_geometry(length=7.0, width=6.0, x=2.0, y=4.0)

    n_wall = next(b for b in room.barriers if b.name == "N wall")
    n_wall.material = "Pb"
    n_wall.thickness_mm = 1.32
    n_wall.occupancy_factor = 0.5
    n_wall.design_goal_uSv_per_week = 50.0
    n_wall.distance_m = 2.0

    apply_geometry_to_selected_room_barriers(app, room)

    n_wall = next(b for b in room.barriers if b.name == "N wall")
    assert n_wall.distance_m == pytest.approx(3.0)
    assert n_wall.material == "Pb"
    assert n_wall.thickness_mm == pytest.approx(1.32)
    assert n_wall.occupancy_factor == pytest.approx(0.5)
    assert n_wall.design_goal_uSv_per_week == pytest.approx(50.0)
