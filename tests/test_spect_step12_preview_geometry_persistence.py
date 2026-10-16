"""Tests for SPECT Step 12 dedicated preview source-position persistence."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from geometry.geometry_model import RoomGeometry
from models.shielding_models import Room
from serialization.spect_preview_state import (
    SPECT_PREVIEW_STATE_BASELINE,
    SPECT_PREVIEW_STATE_LEGACY_BASELINE,
    SPECT_PREVIEW_STATE_LEGACY_VERSION,
    SPECT_PREVIEW_STATE_SCHEMA,
    SPECT_PREVIEW_STATE_VERSION,
    SPECT_PREVIEW_STATE_V2_BASELINE,
    SPECT_PREVIEW_STATE_V2_VERSION,
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    load_spect_preview_state,
    save_spect_preview_state,
    spect_preview_state_from_dict,
    spect_preview_state_to_dict,
)
from tabs.spect_preview_panel import (
    SPECT_UI_PERSISTED_GEOMETRY_BASELINE,
    SPECT_UI_PERSISTED_GEOMETRY_CONTRACT_VERSION,
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


def _room(name: str, x: float, y: float) -> Room:
    geometry = RoomGeometry(room_name=name, length_m=6.0, width_m=5.0, height_m=3.0)
    geometry.source.x_m = x
    geometry.source.y_m = y
    return Room(name=name, modality="SPECT", geometry=geometry)


def _app(room_a=None, room_b=None):
    rooms = {room.name: room for room in (room_a, room_b) if room is not None}
    selected = next(iter(rooms), "")
    return SimpleNamespace(
        spect_preview_activity_var=_Var("700"),
        spect_preview_patients_var=_Var("22"),
        spect_preview_duration_var=_Var("0.75"),
        spect_preview_source_x_var=_Var(""),
        spect_preview_source_y_var=_Var(""),
        sources_room_var=_Var(selected),
        get_room_by_name=lambda name: rooms.get(name),
    )


def test_step12_contract_versions_dedicated_preview_geometry_payload():
    assert SPECT_UI_PERSISTED_GEOMETRY_CONTRACT_VERSION == 7
    assert SPECT_UI_PERSISTED_GEOMETRY_BASELINE == "spect-ui-preview-v7-persisted-source-position"
    assert SPECT_PREVIEW_STATE_SCHEMA == "radshield_spect_ui_preview_state_v1"
    assert SPECT_PREVIEW_STATE_VERSION == 4
    assert SPECT_PREVIEW_STATE_BASELINE == "spect-ui-preview-v9-physics-compatibility"
    assert SPECT_PREVIEW_STATE_V2_VERSION == 2
    assert SPECT_PREVIEW_STATE_V2_BASELINE == SPECT_UI_PERSISTED_GEOMETRY_BASELINE


def test_step12_v2_round_trip_persists_raw_per_room_preview_positions(tmp_path):
    state = SpectPreviewStateSnapshot(
        "abc",
        "27",
        "0.80",
        room_positions=(
            SpectPreviewRoomPositionSnapshot("Room A", "1.25", "2.5"),
            SpectPreviewRoomPositionSnapshot("Room B", "3.50", "4.1"),
        ),
    )
    payload = spect_preview_state_to_dict(state)

    assert payload["production_eligible"] is False
    assert payload["normal_project_state"] is False
    assert payload["preview_geometry"]["room_positions"][0] == {
        "room_name": "Room A",
        "source_x_m": "1.25",
        "source_y_m": "2.5",
    }
    assert spect_preview_state_from_dict(payload) == state

    path = tmp_path / "case.spectpreview.json"
    save_spect_preview_state(path, state)
    assert load_spect_preview_state(path) == state


def test_step12_existing_step9_v1_files_remain_readable_without_geometry():
    legacy = {
        "schema": SPECT_PREVIEW_STATE_SCHEMA,
        "schema_version": SPECT_PREVIEW_STATE_LEGACY_VERSION,
        "preview_baseline": SPECT_PREVIEW_STATE_LEGACY_BASELINE,
        "production_eligible": False,
        "normal_project_state": False,
        "source_inputs": {
            "administered_activity_mbq": "600",
            "patients_per_week": "20",
            "imaging_duration_h": "0.5",
        },
    }
    restored = spect_preview_state_from_dict(legacy)
    assert restored == SpectPreviewStateSnapshot("600", "20", "0.5", ())


def test_step12_snapshot_capture_includes_all_session_room_positions_in_canonical_order():
    room_b = _room("Room B", 3.0, 4.0)
    room_a = _room("Room A", 1.0, 2.0)
    app = _app(room_b, room_a)
    app._spect_preview_room_positions = {
        "Room B": SpectPreviewRoomPositionState("3.5", "4.5"),
        "Room A": SpectPreviewRoomPositionState("1.5", "2.5"),
    }
    app.spect_preview_source_x_var.set("3.75")
    app.spect_preview_source_y_var.set("4.75")

    snapshot = spect_preview_snapshot_from_app(app)

    assert snapshot.room_positions == (
        SpectPreviewRoomPositionSnapshot("Room A", "1.5", "2.5"),
        SpectPreviewRoomPositionSnapshot("Room B", "3.75", "4.75"),
    )
    assert room_b.geometry.source.x_m == pytest.approx(3.0)
    assert room_b.geometry.source.y_m == pytest.approx(4.0)


def test_step12_apply_restores_preview_positions_and_current_ui_without_mutating_geometry():
    room_a = _room("Room A", 1.0, 2.0)
    room_b = _room("Room B", 3.0, 4.0)
    before_a = deepcopy(room_a.geometry)
    before_b = deepcopy(room_b.geometry)
    app = _app(room_a, room_b)

    snapshot = SpectPreviewStateSnapshot(
        "900",
        "30",
        "1.0",
        room_positions=(
            SpectPreviewRoomPositionSnapshot("Room A", "2.25", "3.25"),
            SpectPreviewRoomPositionSnapshot("Room B", "4.0", "1.0"),
        ),
    )
    apply_spect_preview_snapshot(app, snapshot)

    assert app._spect_preview_room_positions == {
        "Room A": SpectPreviewRoomPositionState("2.25", "3.25"),
        "Room B": SpectPreviewRoomPositionState("4", "1"),
    }
    assert app.spect_preview_source_x_var.get() == "2.25"
    assert app.spect_preview_source_y_var.get() == "3.25"
    assert room_a.geometry == before_a
    assert room_b.geometry == before_b


def test_step12_rejects_duplicate_or_noncanonical_room_position_payloads():
    state = SpectPreviewStateSnapshot(
        "600",
        "20",
        "0.5",
        room_positions=(
            SpectPreviewRoomPositionSnapshot("Room A", "1", "2"),
            SpectPreviewRoomPositionSnapshot("Room B", "3", "4"),
        ),
    )
    payload = spect_preview_state_to_dict(state)
    payload["preview_geometry"]["room_positions"].reverse()
    with pytest.raises(SpectPreviewStateError):
        spect_preview_state_from_dict(payload)

    payload = spect_preview_state_to_dict(state)
    payload["preview_geometry"]["room_positions"][1]["room_name"] = "room a"
    with pytest.raises(SpectPreviewStateError):
        spect_preview_state_from_dict(payload)


def test_step12_preview_geometry_tokens_stay_out_of_normal_project_results_reports_and_engine():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    tokens = (
        "SpectPreviewRoomPositionSnapshot",
        "preview_geometry",
        "SPECT_UI_PERSISTED_GEOMETRY_BASELINE",
    )
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text


def test_step12_panel_wording_declares_position_persistence_is_preview_only():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    assert "payload may include per-room preview X/Y" in panel
    assert "do not modify saved RoomGeometry" in panel
    assert "normal project save" in panel
