"""Tests for SPECT Step 11 session-only preview source-position editing."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from geometry.geometry_model import RoomGeometry
from geometry.spect_preview_overlay import build_spect_geometry_overlay
from geometry.spect_preview_position import (
    SPECT_PREVIEW_POSITION_BASELINE,
    SPECT_PREVIEW_POSITION_CONTRACT_VERSION,
    SpectPreviewPositionError,
    build_spect_preview_position,
    cardinal_distances_for_spect_preview,
)
from models.shielding_models import Barrier, Room
from tabs.spect_preview_panel import (
    SPECT_UI_GEOMETRY_EDIT_BASELINE,
    SPECT_UI_GEOMETRY_EDIT_CONTRACT_VERSION,
    SpectPreviewRoomPositionState,
    build_spect_preview_barrier_requests,
    calculate_spect_room_preview,
    get_spect_preview_room_position_state,
)

ROOT = Path(__file__).resolve().parents[1]


def _room(name="SPECT Room", x=1.5, y=2.0):
    geom = RoomGeometry(room_name=name, length_m=6.0, width_m=5.0, height_m=3.0)
    geom.source.x_m = x
    geom.source.y_m = y
    return Room(
        name=name,
        modality="SPECT",
        geometry=geom,
        barriers=[
            Barrier(name="North wall", material="Pb", thickness_mm=2.0, distance_m=4.0, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
            Barrier(name="East wall", material="Concrete", thickness_mm=150.0, distance_m=3.5, occupancy_factor=0.25, design_goal_uSv_per_week=20.0),
            Barrier(name="South wall", material="Pb", thickness_mm=2.0, distance_m=2.0, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
            Barrier(name="West wall", material="Pb", thickness_mm=2.0, distance_m=1.5, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
            Barrier(name="Control barrier", material="Pb", thickness_mm=1.0, distance_m=2.25, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        ],
    )


def test_step11_contract_is_explicitly_preview_geometry_only():
    assert SPECT_UI_GEOMETRY_EDIT_CONTRACT_VERSION == 6
    assert SPECT_UI_GEOMETRY_EDIT_BASELINE == "spect-ui-preview-v6-source-position-edit"
    assert SPECT_PREVIEW_POSITION_CONTRACT_VERSION == 1
    assert SPECT_PREVIEW_POSITION_BASELINE == SPECT_UI_GEOMETRY_EDIT_BASELINE


def test_step11_position_validation_and_cardinal_distances_do_not_mutate_geometry():
    room = _room()
    before = deepcopy(room.geometry)
    position = build_spect_preview_position(room.geometry, source_x_m="2.25", source_y_m="4.5")
    distances = cardinal_distances_for_spect_preview(room.geometry, source_x_m=2.25, source_y_m=4.5)

    assert position.source_x_m == pytest.approx(2.25)
    assert position.source_y_m == pytest.approx(4.5)
    assert distances == pytest.approx({"N": 1.5, "S": 4.5, "E": 2.75, "W": 2.25})
    assert room.geometry == before


@pytest.mark.parametrize("x,y", [("abc", "2"), ("-0.1", "2"), ("5.1", "2"), ("2", "6.1")])
def test_step11_rejects_invalid_or_outside_room_positions(x, y):
    with pytest.raises(SpectPreviewPositionError):
        build_spect_preview_position(_room().geometry, source_x_m=x, source_y_m=y)


def test_step11_barrier_adapter_uses_preview_distances_only_for_cardinal_walls():
    room = _room()
    before = deepcopy(room)
    requests = build_spect_preview_barrier_requests(room, source_x_m=2.25, source_y_m=4.5)
    by_name = {request.barrier_name: request for request in requests}

    assert by_name["North wall"].distance_m == pytest.approx(1.5)
    assert by_name["East wall"].distance_m == pytest.approx(2.75)
    assert by_name["South wall"].distance_m == pytest.approx(4.5)
    assert by_name["West wall"].distance_m == pytest.approx(2.25)
    assert by_name["Control barrier"].distance_m == pytest.approx(2.25)
    assert room == before


def test_step11_moving_preview_source_changes_schedule_without_mutating_room():
    room = _room()
    before = deepcopy(room)
    baseline = calculate_spect_room_preview(room, source_x_m=1.5, source_y_m=2.0)
    moved = calculate_spect_room_preview(room, source_x_m=1.5, source_y_m=5.0)
    baseline_north = next(row for row in baseline.rows if row.barrier_name == "North wall")
    moved_north = next(row for row in moved.rows if row.barrier_name == "North wall")

    assert moved_north.distance_m < baseline_north.distance_m
    assert moved_north.required_thickness_mm > baseline_north.required_thickness_mm
    assert room == before


def test_step11_overlay_accepts_transient_position_override_without_geometry_mutation():
    room = _room()
    before = deepcopy(room.geometry)
    result = calculate_spect_room_preview(room, source_x_m=3.25, source_y_m=4.25)
    overlay = build_spect_geometry_overlay(result, room.geometry, source_x_m=3.25, source_y_m=4.25)

    assert overlay["source_x_m"] == pytest.approx(3.25)
    assert overlay["source_y_m"] == pytest.approx(4.25)
    assert room.geometry == before


def test_step11_session_positions_are_per_room_and_default_from_saved_geometry():
    app = SimpleNamespace()
    room_a = _room("Room A", 1.0, 2.0)
    room_b = _room("Room B", 3.0, 4.0)

    state_a = get_spect_preview_room_position_state(app, room_a)
    state_b = get_spect_preview_room_position_state(app, room_b)
    state_a.source_x_m = "2.5"

    assert state_a == SpectPreviewRoomPositionState("2.5", "2")
    assert state_b == SpectPreviewRoomPositionState("3", "4")
    assert room_a.geometry.source.x_m == pytest.approx(1.0)
    assert room_b.geometry.source.x_m == pytest.approx(3.0)


def test_step11_position_state_is_absent_from_normal_production_persistence_and_reports():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    tokens = ("spect_preview_source_x_var", "SpectPreviewRoomPositionState", "_spect_preview_room_positions")
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text


def test_step11_panel_exposes_what_if_position_fields_and_keeps_host_geometry_neutral():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    geometry_tab = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")

    assert "Preview source X from West (m)" in panel
    assert "Preview source Y from South (m)" in panel
    assert "do not modify saved RoomGeometry" in panel
    assert '== "SPECT"' not in geometry_tab
