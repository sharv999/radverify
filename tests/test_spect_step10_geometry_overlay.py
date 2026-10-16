"""Tests for SPECT Step 10 presentation-only Geometry overlay."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engine.spect_barrier_schedule import calculate_spect_tc99m_barrier_schedule
from geometry.geometry_model import RoomGeometry
from geometry.spect_preview_overlay import (
    SPECT_GEOMETRY_OVERLAY_BASELINE,
    SPECT_GEOMETRY_OVERLAY_CONTRACT_VERSION,
    build_spect_geometry_overlay,
    draw_spect_geometry_preview_overlay,
    wall_key_for_spect_preview_name,
)
from modalities.spect import SpectSourceDomain
from tabs.spect_preview_panel import build_spect_preview_barrier_requests
from models.shielding_models import Barrier, Room


ROOT = Path(__file__).resolve().parents[1]


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.calls.append(("oval", args, kwargs))
        return len(self.calls)

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", args, kwargs))
        return len(self.calls)

    def tag_raise(self, *args, **kwargs):
        self.calls.append(("raise", args, kwargs))


def _room():
    geom = RoomGeometry(room_name="SPECT Room", length_m=6.0, width_m=5.0, height_m=3.0)
    geom.source.x_m = 1.5
    geom.source.y_m = 2.0
    return Room(
        name="SPECT Room",
        modality="SPECT",
        geometry=geom,
        barriers=[
            Barrier(name="North wall", material="Pb", thickness_mm=2.0, distance_m=4.0, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
            Barrier(name="East wall", material="Concrete", thickness_mm=150.0, distance_m=3.5, occupancy_factor=0.25, design_goal_uSv_per_week=20.0),
            Barrier(name="Control barrier", material="Pb", thickness_mm=1.0, distance_m=2.0, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        ],
    )


def _result(room):
    source = SpectSourceDomain("Tc99m", 600.0, 20.0, 0.5)
    return calculate_spect_tc99m_barrier_schedule(source, build_spect_preview_barrier_requests(room))


def test_step10_overlay_payload_is_nonproduction_and_uses_existing_source_position():
    room = _room()
    before = (room.geometry.source.x_m, room.geometry.source.y_m)
    overlay = build_spect_geometry_overlay(_result(room), room.geometry)

    assert overlay["contract_version"] == SPECT_GEOMETRY_OVERLAY_CONTRACT_VERSION == 1
    assert overlay["baseline"] == SPECT_GEOMETRY_OVERLAY_BASELINE == "spect-ui-preview-v5-geometry-overlay"
    assert overlay["production_eligible"] is False
    assert overlay["radionuclide"] == "Tc99m"
    assert overlay["source_x_m"] == 1.5
    assert overlay["source_y_m"] == 2.0
    assert overlay["room_name"] == "SPECT Room"
    assert [row["wall_key"] for row in overlay["rows"]] == ["N", "E", None]
    assert before == (room.geometry.source.x_m, room.geometry.source.y_m)


def test_step10_wall_mapping_is_deliberately_narrow():
    assert wall_key_for_spect_preview_name("North wall") == "N"
    assert wall_key_for_spect_preview_name("east") == "E"
    assert wall_key_for_spect_preview_name("S wall") == "S"
    assert wall_key_for_spect_preview_name("W") == "W"
    assert wall_key_for_spect_preview_name("Control barrier") is None


def test_step10_renderer_draws_source_only_without_duplicate_barrier_status_text():
    room = _room()
    overlay = build_spect_geometry_overlay(_result(room), room.geometry)
    before = (room.geometry.source.x_m, room.geometry.source.y_m, room.geometry.length_m, room.geometry.width_m)
    canvas = FakeCanvas()

    draw_spect_geometry_preview_overlay(canvas, room.geometry, (100, 100, 600, 700), overlay)

    assert before == (room.geometry.source.x_m, room.geometry.source.y_m, room.geometry.length_m, room.geometry.width_m)
    assert not any("spect_preview_source" in call[2].get("tags", ()) for call in canvas.calls)
    texts = [call[2].get("text", "") for call in canvas.calls if call[0] == "text"]
    assert not any("SPECT preview" in text for text in texts)
    expected_dose = f"{overlay['weekly_dose_uSv_at_1m']:.2f} µSv/wk @ 1 m"
    assert expected_dose in texts
    assert not any("SPECT N:" in text for text in texts)
    assert not any("SPECT E:" in text for text in texts)
    assert not any("Control barrier" in text for text in texts)



def test_step10_renderer_uses_canonical_geometry_source_when_overlay_position_is_stale():
    room = _room()
    overlay = build_spect_geometry_overlay(_result(room), room.geometry)
    overlay["source_x_m"] = 4.5
    overlay["source_y_m"] = 5.5
    canvas = FakeCanvas()

    bbox = (100, 100, 600, 700)
    draw_spect_geometry_preview_overlay(canvas, room.geometry, bbox, overlay)

    expected_dose = f"{overlay['weekly_dose_uSv_at_1m']:.2f} µSv/wk @ 1 m"
    label = next(call for call in canvas.calls if call[0] == "text" and call[2].get("text") == expected_dose)
    label_x, label_y = label[1]
    px_per_m = min((bbox[2] - bbox[0]) / room.geometry.width_m, (bbox[3] - bbox[1]) / room.geometry.length_m)
    expected_x = bbox[0] + room.geometry.source.x_m * px_per_m
    expected_y = (bbox[3] - room.geometry.source.y_m * px_per_m) - px_per_m - 10.0

    assert label_x == expected_x
    assert label_y == expected_y


def test_step10_renderer_suppresses_stale_overlay_for_another_room():
    room = _room()
    overlay = build_spect_geometry_overlay(_result(room), room.geometry)
    other = RoomGeometry(room_name="Other Room", length_m=6.0, width_m=5.0, height_m=3.0)
    canvas = FakeCanvas()

    draw_spect_geometry_preview_overlay(canvas, other, (100, 100, 600, 700), overlay)

    assert not any(call[0] in {"oval", "text"} for call in canvas.calls)


def test_step10_geometry_tab_consumes_transient_overlay_and_gates_it_to_spect_rooms():
    geometry_tab = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")

    assert "draw_spect_geometry_preview_overlay" in geometry_tab
    assert 'preview_overlay_kind == "spect"' in geometry_tab
    assert '== "SPECT"' not in geometry_tab
    assert "build_spect_geometry_overlay" in panel
    assert "spect_preview_geometry_overlay" in panel
    assert "sync_unified_modality_outputs(app)" in panel


def test_step10_overlay_is_absent_from_persistence_results_reports_and_production_engine():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "serialization" / "spect_preview_state.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "spect_preview_geometry_overlay" not in text
        assert "SPECT_GEOMETRY_OVERLAY" not in text


def test_step10_overlay_builder_rejects_non_schedule_results():
    try:
        build_spect_geometry_overlay(SimpleNamespace(), _room().geometry)
    except TypeError as exc:
        assert "SpectBarrierScheduleResult" in str(exc)
    else:
        raise AssertionError("Expected TypeError")
