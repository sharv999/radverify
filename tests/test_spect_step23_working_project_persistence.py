from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest
from engine.spect_calculation_request_contract import (
    SPECT_CALCULATION_REQUEST_SCHEMA,
    SPECT_CALCULATION_REQUEST_VERSION,
    current_spect_calculation_physics_freeze,
    spect_calculation_request_to_dict,
)
from models.shielding_models import Project, Room, project_from_dict, project_to_dict
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, SpectSourceDomain
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_KEY,
    SPECT_WORKING_PROJECT_STATE_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_VERSION,
    SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION,
    SpectWorkingProjectStateError,
    get_room_spect_working_state,
    new_spect_working_project_state,
    set_room_spect_working_state,
    spect_working_project_state_from_dict,
    spect_working_project_state_to_dict,
)
from engine.spect_working_project_request import build_spect_working_calculation_request
from services.project_io import load_project_from_file
from tabs.spect_preview_panel import (
    load_spect_working_state_into_preview,
    persist_spect_preview_source_to_room,
)


ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _source() -> SpectSourceDomain:
    return SpectSourceDomain(
        radionuclide="Tc99m",
        administered_activity_mbq=720.0,
        patients_per_week=25.0,
        imaging_duration_h=0.65,
    )


def _room() -> Room:
    return Room(name="SPECT Room 1", modality="SPECT")


def test_step23_state_reflects_controlled_host_scope_and_is_bound_to_step20_step21():
    state = new_spect_working_project_state(_source())
    payload = spect_working_project_state_to_dict(state)

    assert payload["schema"] == SPECT_WORKING_PROJECT_STATE_SCHEMA
    assert payload["schema_version"] == SPECT_WORKING_PROJECT_STATE_VERSION
    assert payload["production_host_enabled"] is True
    assert payload["production_calculation_enabled"] is True
    assert payload["issued_output_enabled"] is False
    assert payload["physics_freeze"] == current_spect_calculation_physics_freeze()
    assert payload["request_contract"] == {
        "schema": SPECT_CALCULATION_REQUEST_SCHEMA,
        "schema_version": SPECT_CALCULATION_REQUEST_VERSION,
    }


def test_step23_state_round_trip_is_canonical():
    payload = spect_working_project_state_to_dict(
        new_spect_working_project_state(_source())
    )
    restored = spect_working_project_state_from_dict(
        json.loads(json.dumps(payload))
    )
    assert spect_working_project_state_to_dict(restored) == payload


def test_step23_legacy_v1_working_state_remains_readable_but_resaves_as_v2():
    current = spect_working_project_state_to_dict(new_spect_working_project_state(_source()))
    legacy = {
        "schema": SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
        "schema_version": SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION,
        "production_eligible": False,
        "calculation_dispatch_enabled": False,
        "output_enabled": False,
        "physics_freeze": current["physics_freeze"],
        "request_contract": current["request_contract"],
        "source": current["source"],
    }
    restored = spect_working_project_state_from_dict(legacy)
    migrated = spect_working_project_state_to_dict(restored)
    assert migrated["schema"] == SPECT_WORKING_PROJECT_STATE_SCHEMA
    assert migrated["schema_version"] == SPECT_WORKING_PROJECT_STATE_VERSION
    assert migrated["production_host_enabled"] is True
    assert migrated["production_calculation_enabled"] is True
    assert migrated["issued_output_enabled"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("production_host_enabled",), False),
        (("production_calculation_enabled",), False),
        (("issued_output_enabled",), True),
        (("physics_freeze", "freeze_id"), "different-freeze"),
        (("request_contract", "schema_version"), 999),
        (("source", "administered_activity_mbq"), float("nan")),
    ],
)
def test_step23_state_fails_closed_on_contract_or_physics_drift(path, value):
    payload = spect_working_project_state_to_dict(
        new_spect_working_project_state(_source())
    )
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(SpectWorkingProjectStateError):
        spect_working_project_state_from_dict(payload)


def test_step23_state_may_only_attach_to_spect_room():
    room = Room(name="CT Room 1", modality="CT")
    with pytest.raises(SpectWorkingProjectStateError, match="only be attached"):
        set_room_spect_working_state(
            room, new_spect_working_project_state(_source())
        )


def test_step23_normal_project_round_trip_preserves_spect_working_source_only():
    room = _room()
    room.geometry.source.x_m = 2.25
    room.geometry.source.y_m = 3.5
    set_room_spect_working_state(
        room, new_spect_working_project_state(_source())
    )
    project = Project(project_name="SPECT working persistence", rooms=[room], sources=[])

    payload = project_to_dict(project)
    assert payload["sources"] == []
    assert SPECT_WORKING_PROJECT_STATE_KEY in payload["rooms"][0]["modality_state"]
    assert payload["rooms"][0]["geometry"]["source"]["x_m"] == pytest.approx(2.25)
    assert "position" not in payload["rooms"][0]["modality_state"][SPECT_WORKING_PROJECT_STATE_KEY]

    restored = project_from_dict(json.loads(json.dumps(payload)))
    assert restored.sources == []
    assert get_room_spect_working_state(restored.rooms[0]).source == _source()
    assert restored.rooms[0].geometry.source.x_m == pytest.approx(2.25)


def test_step23_project_io_rejects_stale_working_physics_before_returning_project(tmp_path):
    room = _room()
    set_room_spect_working_state(room, new_spect_working_project_state(_source()))
    payload = project_to_dict(Project(rooms=[room]))
    payload["rooms"][0]["modality_state"][SPECT_WORKING_PROJECT_STATE_KEY][
        "physics_freeze"
    ]["freeze_id"] = "stale-freeze"
    path = tmp_path / "stale_spect_working.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SpectWorkingProjectStateError, match="physics freeze"):
        load_project_from_file(path)


def test_step23_working_source_reconstructs_exact_step21_canonical_request():
    state = new_spect_working_project_state(_source())
    barriers = (
        SpectBarrierScheduleRequest(
            barrier_id="north",
            barrier_name="North wall",
            material_key="lead",
            distance_m=2.0,
            occupancy_factor=1.0,
            design_goal_uSv_per_week=1.0,
            provided_thickness_mm=1.0,
            source_name="SPECT patient",
        ),
    )
    request = build_spect_working_calculation_request(state, barriers)
    payload = spect_calculation_request_to_dict(request)

    assert payload["source"] == {
        "radionuclide": "Tc99m",
        "administered_activity_mbq": 720.0,
        "patients_per_week": 25.0,
        "imaging_duration_h": 0.65,
    }
    assert payload["physics_freeze"] == current_spect_calculation_physics_freeze()
    assert payload["production_eligible"] is False


def test_step23_preview_source_can_be_persisted_and_restored_without_preview_geometry():
    room = _room()
    room.geometry.source.x_m = 2.0
    room.geometry.source.y_m = 2.5
    app = SimpleNamespace(
        sources_room_var=_Var(room.name),
        spect_preview_activity_var=_Var("810"),
        spect_preview_patients_var=_Var("27"),
        spect_preview_duration_var=_Var("0.8"),
        spect_preview_source_x_var=_Var("4.5"),
        spect_preview_source_y_var=_Var("5.5"),
        get_room_by_name=lambda name: room if name == room.name else None,
    )

    assert persist_spect_preview_source_to_room(app, room) is True
    stored = get_room_spect_working_state(room)
    assert stored.source.administered_activity_mbq == pytest.approx(810.0)
    state_payload = room.modality_state[SPECT_WORKING_PROJECT_STATE_KEY]
    assert "position" not in state_payload
    assert "source_x_m" not in json.dumps(state_payload)

    app.spect_preview_activity_var.set("1")
    app.spect_preview_patients_var.set("1")
    app.spect_preview_duration_var.set("1")
    assert load_spect_working_state_into_preview(app, room) is True
    assert app.spect_preview_activity_var.get() == "810"
    assert app.spect_preview_patients_var.get() == "27"
    assert app.spect_preview_duration_var.get() == "0.8"
    assert app.spect_preview_source_x_var.get() == "4.5"
    assert app.spect_preview_source_y_var.get() == "5.5"


def test_step23_invalid_preview_edit_does_not_overwrite_last_valid_working_state():
    room = _room()
    set_room_spect_working_state(room, new_spect_working_project_state(_source()))
    before = copy.deepcopy(room.modality_state)
    app = SimpleNamespace(
        spect_preview_activity_var=_Var("not-a-number"),
        spect_preview_patients_var=_Var("25"),
        spect_preview_duration_var=_Var("0.65"),
    )

    assert persist_spect_preview_source_to_room(app, room) is False
    assert room.modality_state == before


def test_step23_does_not_open_production_dispatch_results_reports_or_exports():
    assert "SPECT" in production_modality_names()
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON

    forbidden = (
        "SPECT_WORKING_PROJECT_STATE_KEY",
        "get_room_spect_working_state",
        "build_spect_working_calculation_request",
    )
    paths = [
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "tabs" / "results_tab_rendering.py",
        ROOT / "reports" / "results_payload_builder.py",
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "services" / "export_eligibility.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined
