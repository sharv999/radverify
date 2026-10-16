"""Tests for SPECT Step 17 preview usability/workflow hardening."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from geometry.geometry_model import RoomGeometry
from models.shielding_models import Room
from tabs.spect_preview_panel import (
    SPECT_UI_PREVIEW_SOURCE,
    SPECT_UI_WORKFLOW_HARDENING_BASELINE,
    SPECT_UI_WORKFLOW_HARDENING_CONTRACT_VERSION,
    SpectPreviewError,
    SpectPreviewRoomPositionState,
    SpectPreviewSessionState,
    build_spect_preview_source,
    get_spect_preview_room_position_state,
    reset_spect_preview_position_to_room_geometry,
    reset_spect_preview_source_to_defaults,
    spect_preview_state_badge_text,
)

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def _room(name="SPECT Room", x=1.5, y=2.0):
    geometry = RoomGeometry(room_name=name, length_m=6.0, width_m=5.0, height_m=3.0)
    geometry.source.x_m = x
    geometry.source.y_m = y
    return Room(name=name, modality="SPECT", geometry=geometry)


def _app(room):
    rooms = {room.name: room}
    return SimpleNamespace(
        sources_room_var=_Var(room.name),
        get_room_by_name=lambda name: rooms.get(name),
        spect_preview_activity_var=_Var("600"),
        spect_preview_patients_var=_Var("20"),
        spect_preview_duration_var=_Var("0.5"),
        spect_preview_source_x_var=_Var(f"{room.geometry.source.x_m:g}"),
        spect_preview_source_y_var=_Var(f"{room.geometry.source.y_m:g}"),
        spect_preview_state_badge_var=_Var(),
    )


def test_step17_contract_is_explicitly_ui_workflow_only():
    assert SPECT_UI_WORKFLOW_HARDENING_CONTRACT_VERSION == 11
    assert SPECT_UI_WORKFLOW_HARDENING_BASELINE == "spect-ui-preview-v11-workflow-hardening"


def test_step17_source_input_errors_name_the_actual_field():
    with pytest.raises(SpectPreviewError, match="Tc-99m activity is required"):
        build_spect_preview_source("", "20", "0.5")
    with pytest.raises(SpectPreviewError, match="Patients/week must be numeric"):
        build_spect_preview_source("600", "many", "0.5")
    with pytest.raises(SpectPreviewError, match="Imaging interval must be greater than zero"):
        build_spect_preview_source("600", "20", "0")


def test_step17_state_badge_distinguishes_room_baseline_modified_and_invalid():
    room = _room()
    app = _app(room)

    assert spect_preview_state_badge_text(app, room).startswith("ROOM BASELINE")

    app.spect_preview_activity_var.set("800")
    assert "PREVIEW MODIFIED" in spect_preview_state_badge_text(app, room)
    assert "source inputs" in spect_preview_state_badge_text(app, room)

    app.spect_preview_activity_var.set("600")
    app.spect_preview_source_x_var.set("2.25")
    assert "PREVIEW MODIFIED" in spect_preview_state_badge_text(app, room)
    assert "source position" in spect_preview_state_badge_text(app, room)

    app.spect_preview_source_x_var.set("outside")
    assert spect_preview_state_badge_text(app, room).startswith("INVALID INPUT")


def test_step17_reset_position_restores_saved_room_geometry_without_mutating_it():
    room = _room(x=1.25, y=2.75)
    before = deepcopy(room.geometry)
    app = _app(room)
    state = get_spect_preview_room_position_state(app, room)
    state.source_x_m = "4.5"
    state.source_y_m = "5.5"
    app.spect_preview_source_x_var.set("4.5")
    app.spect_preview_source_y_var.set("5.5")

    reset_spect_preview_position_to_room_geometry(app, room, refresh=False)

    assert state == SpectPreviewRoomPositionState("1.25", "2.75")
    assert app.spect_preview_source_x_var.get() == "1.25"
    assert app.spect_preview_source_y_var.get() == "2.75"
    assert app.spect_preview_state_badge_var.get().startswith("ROOM BASELINE")
    assert room.geometry == before


def test_step17_reset_source_inputs_restores_defaults_without_touching_room_state():
    room = _room()
    before = deepcopy(room)
    app = _app(room)
    app._spect_preview_session_state = SpectPreviewSessionState("900", "35", "1.25")
    app.spect_preview_activity_var.set("900")
    app.spect_preview_patients_var.set("35")
    app.spect_preview_duration_var.set("1.25")

    reset_spect_preview_source_to_defaults(app, refresh=False)

    assert app._spect_preview_session_state == SpectPreviewSessionState("600", "20", "0.5")
    assert app.spect_preview_activity_var.get() == f"{SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq:g}"
    assert app.spect_preview_patients_var.get() == f"{SPECT_UI_PREVIEW_SOURCE.patients_per_week:g}"
    assert app.spect_preview_duration_var.get() == f"{SPECT_UI_PREVIEW_SOURCE.imaging_duration_h:g}"
    assert room == before


def test_step17_panel_exposes_nonproduction_badges_and_explicit_reset_controls():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")

    assert "NON-PRODUCTION PREVIEW" in panel
    assert "ROOM BASELINE" in panel
    assert "PREVIEW MODIFIED" in panel
    assert "INVALID INPUT" in panel
    assert "Reset Source Inputs" in panel
    assert "Reset Position to Room Geometry" in panel


def test_step17_workflow_state_stays_out_of_project_results_reports_and_production():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    tokens = (
        "spect_preview_state_badge_var",
        "SPECT_UI_WORKFLOW_HARDENING_BASELINE",
        "reset_spect_preview_position_to_room_geometry",
    )
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text
