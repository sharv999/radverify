from types import SimpleNamespace

import pytest

from engine.shielding_engine import default_barriers
from geometry.barrier_sync import BarrierSyncMixin, apply_geometry_to_selected_room_barriers
from geometry.geometry_model import RoomGeometry
from models.shielding_models import Room


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Editor(BarrierSyncMixin):
    def __init__(self, room, selected, distance):
        self._room = room
        self.barrier_wall_var = _Var(selected)
        self.barrier_material_var = _Var("Concrete")
        self.barrier_thickness_var = _Var("150")
        self.barrier_t_var = _Var("1")
        self.barrier_distance_var = _Var(str(distance))

    def get_selected_room(self):
        return self._room


class _App:
    def create_default_room_geometry(self, room_name, modality):
        return RoomGeometry(room_name=room_name)

    def _coerce_barrier_schema(self, barrier):
        return barrier

    def enforce_room_source_types(self, room):
        return None


def _barrier(room, name):
    return next(b for b in room.barriers if b.name == name)


def test_floor_and_ceiling_default_distances_are_geometry_derived():
    room = Room(
        name="SPECT Room 1",
        modality="SPECT",
        geometry=RoomGeometry(room_name="SPECT Room 1", height_m=3.6),
        barriers=default_barriers(),
    )

    apply_geometry_to_selected_room_barriers(_App(), room)

    assert _barrier(room, "Floor").distance_m == pytest.approx(1.0)
    assert _barrier(room, "Ceiling").distance_m == pytest.approx(2.6)
    assert _barrier(room, "Floor").distance_is_manual is False
    assert _barrier(room, "Ceiling").distance_is_manual is False


def test_manual_floor_distance_survives_canonical_refresh():
    room = Room(
        name="SPECT Room 1",
        modality="SPECT",
        geometry=RoomGeometry(room_name="SPECT Room 1", height_m=3.6),
        barriers=default_barriers(),
    )
    apply_geometry_to_selected_room_barriers(_App(), room)

    _Editor(room, "Floor", 1.25).apply_barrier_fields_to_room(room)
    apply_geometry_to_selected_room_barriers(_App(), room)

    floor = _barrier(room, "Floor")
    assert floor.distance_m == pytest.approx(1.25)
    assert floor.distance_is_manual is True


def test_manual_ceiling_distance_survives_canonical_refresh():
    room = Room(
        name="SPECT Room 1",
        modality="SPECT",
        geometry=RoomGeometry(room_name="SPECT Room 1", height_m=3.6),
        barriers=default_barriers(),
    )
    apply_geometry_to_selected_room_barriers(_App(), room)

    _Editor(room, "Ceiling", 2.35).apply_barrier_fields_to_room(room)
    apply_geometry_to_selected_room_barriers(_App(), room)

    ceiling = _barrier(room, "Ceiling")
    assert ceiling.distance_m == pytest.approx(2.35)
    assert ceiling.distance_is_manual is True
