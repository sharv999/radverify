from __future__ import annotations

from pathlib import Path

import pytest

from engine.pet_project_dispatch import (
    PET_PROJECT_DISPATCH_CONTRACT_VERSION,
    PetProjectDispatchError,
    dispatch_persisted_pet_working_state,
)
from engine.shielding_engine import default_barriers, dispatch_room_persisted_pet_calculation
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PET_CALCULATION_BLOCK_REASON, PetExposurePhase, PetSourceDomain
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_KEY,
    PetWorkingProjectState,
    set_room_pet_working_state,
)
from services.source_readiness import PET_WORKING_STATE_BLOCK_REASON, validate_project_source_readiness


def _project() -> Project:
    room = Room(
        name="Hybrid Room 1",
        modality="CT",
        barriers=default_barriers(),
        geometry=RoomGeometry(width_m=5.0, length_m=6.0, height_m=3.0),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(
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
            position=PetPreviewPosition(1.0, 2.0, 0.8),
        ),
    )
    return Project(project_name="PET dispatch", rooms=[room], sources=[])


def test_persisted_pet_working_state_dispatches_all_room_barriers_replay_verified():
    project = _project()
    result = dispatch_room_persisted_pet_calculation(project, "Hybrid Room 1")

    assert result is not None
    assert result.contract_version == PET_PROJECT_DISPATCH_CONTRACT_VERSION
    assert result.source_type == "pet_patient"
    assert result.replay_verified is True
    assert result.physics_result.weekly_dose_uSv_at_1m > 0.0
    assert [row.barrier_name for row in result.barrier_results] == [
        "N wall", "E wall", "S wall", "W wall", "Floor", "Ceiling"
    ]
    assert [row.distance_m for row in result.barrier_results] == pytest.approx(
        [4.0, 4.0, 2.0, 1.0, 0.8, 2.2]
    )
    assert all(row.solver_result.source_type == "pet_patient" for row in result.barrier_results)


def test_pet_dispatch_uses_pet_position_not_ct_geometry_source_isocentre():
    project = _project()
    first = dispatch_persisted_pet_working_state(project, "Hybrid Room 1")
    project.rooms[0].geometry.source_x_m = 4.7
    project.rooms[0].geometry.source_y_m = 5.7
    second = dispatch_persisted_pet_working_state(project, "Hybrid Room 1")

    assert first is not None and second is not None
    assert [row.distance_m for row in first.barrier_results] == [row.distance_m for row in second.barrier_results]
    assert [row.solver_result for row in first.barrier_results] == [row.solver_result for row in second.barrier_results]


def test_pet_dispatch_returns_none_when_room_has_no_persisted_pet_state():
    project = _project()
    project.rooms[0].modality_state = {}
    assert dispatch_persisted_pet_working_state(project, "Hybrid Room 1") is None


def test_pet_dispatch_fails_closed_on_malformed_persisted_state():
    project = _project()
    project.rooms[0].modality_state[PET_WORKING_PROJECT_STATE_KEY]["provenance_manifest"]["revision"] = "future"
    with pytest.raises(PetProjectDispatchError, match="Persisted PET working state is invalid"):
        dispatch_persisted_pet_working_state(project, "Hybrid Room 1")


def test_pet_dispatch_fails_closed_on_unsupported_barrier_material():
    project = _project()
    project.rooms[0].barriers[0].material = "Gypsum"
    project.rooms[0].barriers[0].material_legacy = "Gypsum"
    with pytest.raises(PetProjectDispatchError, match="unsupported PET material"):
        dispatch_persisted_pet_working_state(project, "Hybrid Room 1")


def test_dispatch_opening_does_not_open_registry_results_reports_or_export():
    project = _project()

    assert "PET" in production_modality_names()
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    readiness = validate_project_source_readiness(project)
    assert any(item.get("output_blocking") is True for item in readiness["source_results"])

    forbidden = (
        "dispatch_persisted_pet_working_state",
        "dispatch_room_persisted_pet_calculation",
        "PetRoomDispatchResult",
    )
    still_closed_paths = [
        Path("tabs/results_tab_rendering.py"),
        Path("reports/results_payload_builder.py"),
        Path("reports/output_pipeline.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in still_closed_paths)
    for token in forbidden:
        assert token not in combined
