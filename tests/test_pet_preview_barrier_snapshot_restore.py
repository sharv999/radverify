from __future__ import annotations

import copy

import pytest

from engine.shielding_engine import default_barriers
from models.shielding_models import Room
from modalities.pet import PetContractError
from tabs.pet_preview_panel import (
    build_pet_preview_barrier_values_from_room,
    restore_pet_preview_barrier_snapshot_to_room,
)


def _room() -> Room:
    room = Room(name="PET Room", modality="CT", barriers=default_barriers())
    # Give every barrier a distinctive persisted input so accidental defaults
    # are obvious on round-trip.
    for index, barrier in enumerate(room.barriers, start=1):
        barrier.thickness_mm = float(index) * 1.76
        barrier.occupancy_factor = 0.2 if index < 5 else 1.0
        barrier.design_goal_uSv_per_week = 10.0 if index != 1 else 50.0
    return room


def test_pet_preview_barrier_snapshot_restore_round_trips_provided_thicknesses():
    room = _room()
    saved = build_pet_preview_barrier_values_from_room(room)
    expected = {b.name: b.thickness_mm for b in room.barriers}

    for barrier in room.barriers:
        barrier.thickness_mm = 0.88

    restore_pet_preview_barrier_snapshot_to_room(room, saved)

    assert {b.name: b.thickness_mm for b in room.barriers} == expected


def test_pet_preview_barrier_snapshot_restore_round_trips_material_occupancy_and_design_goal():
    room = _room()
    room.barriers[0].material = "Concrete"
    room.barriers[0].occupancy_factor = 1.0
    room.barriers[0].design_goal_uSv_per_week = 20.0
    saved = build_pet_preview_barrier_values_from_room(room)

    room.barriers[0].material = "Pb"
    room.barriers[0].occupancy_factor = 0.2
    room.barriers[0].design_goal_uSv_per_week = 10.0

    restore_pet_preview_barrier_snapshot_to_room(room, saved)

    assert room.barriers[0].material == "Concrete"
    assert room.barriers[0].occupancy_factor == 1.0
    assert room.barriers[0].design_goal_uSv_per_week == 20.0


def test_pet_preview_barrier_snapshot_restore_does_not_restore_distance():
    room = _room()
    saved = list(build_pet_preview_barrier_values_from_room(room))
    saved[0] = dict(saved[0])
    saved[0]["distance_m"] = "999"
    original_distance = room.barriers[0].distance_m

    restore_pet_preview_barrier_snapshot_to_room(room, saved)

    assert room.barriers[0].distance_m == original_distance


def test_pet_preview_barrier_snapshot_restore_fails_closed_on_inventory_mismatch():
    room = _room()
    saved = list(build_pet_preview_barrier_values_from_room(room))
    saved.pop()
    before = copy.deepcopy(room.barriers)

    with pytest.raises(PetContractError, match="inventory does not match"):
        restore_pet_preview_barrier_snapshot_to_room(room, saved)

    assert room.barriers == before


def test_load_pet_preview_no_longer_discards_saved_barrier_rows():
    text = open("tabs/pet_preview_panel.py", encoding="utf-8").read()
    assert "restore_pet_preview_barrier_snapshot_to_room(room, barrier_values)" in text
    assert "del barrier_values" not in text
