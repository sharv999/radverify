
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room, project_from_dict, project_to_dict
from modalities.pet import PET_CALCULATION_BLOCK_REASON, PetExposurePhase, PetSourceDomain
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_KEY,
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
    PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
    PetWorkingProjectState,
    PetWorkingProjectStateError,
    get_room_pet_working_state,
    pet_working_project_state_from_dict,
    pet_working_project_state_to_dict,
    set_room_pet_working_state,
)
from engine.pet_calculation_input_provenance import (
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID,
    PET_CALCULATION_INPUT_PROVENANCE_REVISION,
)


def _state() -> PetWorkingProjectState:
    return PetWorkingProjectState(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            residual_activity_factor=1.0,
            exposure_phases=(
                PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
                PetExposurePhase("Imaging", 1.0, 0.5, 1.0),
            ),
        ),
        position=PetPreviewPosition(2.5, 3.0, 1.0),
    )


def test_pet_working_state_is_single_source_host_enabled_output_closed_and_provenance_bound():
    payload = pet_working_project_state_to_dict(_state())

    assert payload["schema"] == PET_WORKING_PROJECT_STATE_SCHEMA
    assert payload["schema_version"] == PET_WORKING_PROJECT_STATE_VERSION
    assert payload["production_host_enabled"] is True
    assert payload["production_calculation_enabled"] is True
    assert payload["issued_output_enabled"] is False
    assert payload["single_source_per_room"] is True
    assert payload["provenance_manifest"] == {
        "manifest_id": PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID,
        "revision": PET_CALCULATION_INPUT_PROVENANCE_REVISION,
    }
    assert payload["source"]["radionuclide"] == "F18"
    assert payload["position"] == {
        "x_from_west_m": 2.5,
        "y_from_south_m": 3.0,
        "height_above_ffl_m": 1.0,
    }


def test_pet_working_state_round_trip_is_canonical():
    payload = json.loads(json.dumps(pet_working_project_state_to_dict(_state())))
    restored = pet_working_project_state_from_dict(payload)
    assert restored == _state()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("production_host_enabled",), False),
        (("production_calculation_enabled",), False),
        (("issued_output_enabled",), True),
        (("single_source_per_room",), False),
        (("provenance_manifest", "revision"), "future-revision"),
        (("position", "x_from_west_m"), float("nan")),
    ],
)
def test_pet_working_state_fails_closed_on_identity_or_contract_drift(path, value):
    payload = pet_working_project_state_to_dict(_state())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(PetWorkingProjectStateError):
        pet_working_project_state_from_dict(payload)


def test_legacy_v2_working_state_loads_and_resaves_as_current_v3():
    current = pet_working_project_state_to_dict(_state())
    legacy = {
        "schema": PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
        "schema_version": PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
        "production_eligible": False,
        "single_source_per_room": current["single_source_per_room"],
        "provenance_manifest": copy.deepcopy(current["provenance_manifest"]),
        "position": copy.deepcopy(current["position"]),
        "source": copy.deepcopy(current["source"]),
    }
    restored = pet_working_project_state_from_dict(legacy)
    assert restored == _state()
    migrated = pet_working_project_state_to_dict(restored)
    assert migrated["schema"] == PET_WORKING_PROJECT_STATE_SCHEMA
    assert migrated["schema_version"] == PET_WORKING_PROJECT_STATE_VERSION
    assert migrated["production_host_enabled"] is True
    assert migrated["production_calculation_enabled"] is True
    assert migrated["issued_output_enabled"] is False


def test_normal_working_project_round_trip_preserves_pet_room_state_without_project_source():
    room = Room(name="Hybrid Room 1", modality="CT")
    set_room_pet_working_state(room, _state())
    project = Project(project_name="PET persistence", rooms=[room], sources=[])

    payload = project_to_dict(project)

    assert PET_WORKING_PROJECT_STATE_KEY in payload["rooms"][0]["modality_state"]
    assert payload["sources"] == []

    restored = project_from_dict(json.loads(json.dumps(payload)))
    assert restored.sources == []
    assert get_room_pet_working_state(restored.rooms[0]) == _state()


def test_pet_working_state_opens_host_but_not_legacy_dispatch_or_reports():
    room = Room(name="Hybrid Room 1", modality="CT")
    set_room_pet_working_state(room, _state())
    project = Project(rooms=[room], sources=[])

    assert "PET" in production_modality_names()
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON
    assert project.sources == []

    forbidden = (
        "PET_WORKING_PROJECT_STATE_KEY",
        "pet_working_project_state_from_dict",
        "get_room_pet_working_state",
    )
    production_paths = [
        Path("engine/shielding_engine.py"),
        Path("tabs/results_tab_rendering.py"),
        Path("reports/results_payload_builder.py"),
        Path("reports/output_pipeline.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in production_paths)
    for token in forbidden:
        assert token not in combined
