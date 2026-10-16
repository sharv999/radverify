"""Tests for SPECT Step 13 preview-state validation/canonicalization hardening."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from geometry.geometry_model import RoomGeometry
from models.shielding_models import Room
from serialization.spect_preview_state import (
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    save_spect_preview_state,
    load_spect_preview_state,
    spect_preview_state_from_dict,
    spect_preview_state_to_dict,
)
from tabs.spect_preview_panel import (
    SpectPreviewError,
    SpectPreviewRoomPositionState,
    apply_spect_preview_snapshot,
    spect_preview_snapshot_from_app,
)

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self._value = value
    def get(self):
        return self._value
    def set(self, value):
        self._value = value


def _room(name: str, *, modality="SPECT", width=5.0, length=6.0):
    geometry = RoomGeometry(room_name=name, width_m=width, length_m=length, height_m=3.0)
    geometry.source.x_m = 1.0
    geometry.source.y_m = 2.0
    return Room(name=name, modality=modality, geometry=geometry)


def _app(*rooms):
    by_name = {room.name: room for room in rooms}
    selected = rooms[0].name if rooms else ""
    return SimpleNamespace(
        spect_preview_activity_var=_Var("600"),
        spect_preview_patients_var=_Var("20"),
        spect_preview_duration_var=_Var("0.5"),
        spect_preview_source_x_var=_Var("1"),
        spect_preview_source_y_var=_Var("2"),
        sources_room_var=_Var(selected),
        get_room_by_name=lambda name: by_name.get(name),
    )


@pytest.mark.parametrize("room_name", ["", " Room A", "Room A "])
def test_step13_room_identity_must_be_exact_nonblank(room_name):
    with pytest.raises(SpectPreviewStateError):
        SpectPreviewRoomPositionSnapshot(room_name, "1", "2")


@pytest.mark.parametrize("value", ["", " ", "nan", "NaN", "inf", "-inf", "abc", "-0.1"])
def test_step13_coordinates_must_be_finite_nonnegative_numeric_strings(value):
    with pytest.raises(SpectPreviewStateError):
        SpectPreviewRoomPositionSnapshot("Room A", value, "2")
    with pytest.raises(SpectPreviewStateError):
        SpectPreviewRoomPositionSnapshot("Room A", "1", value)


def test_step13_coordinate_text_is_canonicalized_deterministically():
    position = SpectPreviewRoomPositionSnapshot("Room A", "01.2500", "0.000")
    assert position.source_x_m == "1.25"
    assert position.source_y_m == "0"


def test_step13_rejects_case_colliding_duplicate_room_identities():
    with pytest.raises(SpectPreviewStateError):
        SpectPreviewStateSnapshot(
            "600", "20", "0.5",
            room_positions=(
                SpectPreviewRoomPositionSnapshot("Room A", "1", "2"),
                SpectPreviewRoomPositionSnapshot("room a", "3", "4"),
            ),
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p["preview_geometry"].pop("room_positions"),
        lambda p: p["preview_geometry"].update({"extra": []}),
        lambda p: p["preview_geometry"]["room_positions"][0].pop("room_name"),
        lambda p: p["preview_geometry"]["room_positions"][0].pop("source_x_m"),
        lambda p: p["preview_geometry"]["room_positions"][0].pop("source_y_m"),
        lambda p: p["preview_geometry"]["room_positions"][0].update({"extra": "x"}),
    ],
)
def test_step13_rejects_missing_or_extra_geometry_fields(mutator):
    payload = spect_preview_state_to_dict(
        SpectPreviewStateSnapshot(
            "600", "20", "0.5",
            (SpectPreviewRoomPositionSnapshot("Room A", "1", "2"),),
        )
    )
    mutator(payload)
    with pytest.raises(SpectPreviewStateError):
        spect_preview_state_from_dict(payload)


def test_step13_save_load_is_byte_deterministic(tmp_path):
    state = SpectPreviewStateSnapshot(
        "600", "20", "0.5",
        room_positions=(
            SpectPreviewRoomPositionSnapshot("Room A", "1.2500", "2.500"),
            SpectPreviewRoomPositionSnapshot("Room B", "3.000", "4"),
        ),
    )
    first = tmp_path / "a.spectpreview.json"
    second = tmp_path / "b.spectpreview.json"
    save_spect_preview_state(first, state)
    restored = load_spect_preview_state(first)
    save_spect_preview_state(second, restored)
    assert first.read_bytes() == second.read_bytes()


def test_step13_apply_rejects_missing_room_atomically():
    room = _room("Room A")
    app = _app(room)
    before = (app.spect_preview_activity_var.get(), app.spect_preview_source_x_var.get())
    snapshot = SpectPreviewStateSnapshot(
        "900", "30", "1",
        (SpectPreviewRoomPositionSnapshot("Missing Room", "1", "2"),),
    )
    with pytest.raises(SpectPreviewError, match="missing room"):
        apply_spect_preview_snapshot(app, snapshot)
    assert (app.spect_preview_activity_var.get(), app.spect_preview_source_x_var.get()) == before


def test_step13_apply_rejects_non_spect_room_identity():
    room = _room("CT Room", modality="CT")
    app = _app(room)
    snapshot = SpectPreviewStateSnapshot(
        "600", "20", "0.5",
        (SpectPreviewRoomPositionSnapshot("CT Room", "1", "2"),),
    )
    with pytest.raises(SpectPreviewError, match="not a SPECT room"):
        apply_spect_preview_snapshot(app, snapshot)


def test_step13_apply_rejects_coordinates_outside_current_room_bounds():
    room = _room("Room A", width=5.0, length=6.0)
    app = _app(room)
    snapshot = SpectPreviewStateSnapshot(
        "600", "20", "0.5",
        (SpectPreviewRoomPositionSnapshot("Room A", "5.1", "2"),),
    )
    with pytest.raises(SpectPreviewError, match="Invalid persisted"):
        apply_spect_preview_snapshot(app, snapshot)


def test_step13_capture_rejects_stale_or_missing_room_position_entries():
    room = _room("Room A")
    app = _app(room)
    app._spect_preview_room_positions = {
        "Missing Room": SpectPreviewRoomPositionState("1", "2"),
    }
    with pytest.raises(SpectPreviewError, match="missing room"):
        spect_preview_snapshot_from_app(app)


def test_step13_hardening_stays_out_of_normal_project_and_report_paths():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "_canonical_coordinate_text" not in text
        assert "_validate_persisted_preview_room_position" not in text
