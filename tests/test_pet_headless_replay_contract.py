"""Tests for deterministic headless replay of isolated PET snapshots."""

import copy
import json
from pathlib import Path

import pytest

from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PetExposurePhase,
    PetSourceDomain,
    calculate_pet_weekly_dose_at_1m,
    solve_pet_isotropic_barrier,
)
from serialization.pet_headless_replay import (
    PET_HEADLESS_REPLAY_CONTRACT_VERSION,
    PetHeadlessReplayError,
    load_and_replay_pet_project_snapshot,
    replay_pet_project_snapshot,
)
from serialization.pet_project_contract import (
    PetProjectDomainSnapshot,
    pet_project_snapshot_to_dict,
)


def _payload() -> dict:
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=200.0,
        patients_per_week=20.0,
        residual_activity_factor=0.9,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 0.75),
        ),
    )
    physics = calculate_pet_weekly_dose_at_1m(source)
    barriers = (
        solve_pet_isotropic_barrier(
            physics,
            material_key="lead",
            distance_m=2.0,
            occupancy_factor=0.5,
            design_goal_uSv_per_week=10.0,
            provided_thickness_mm=16.0,
            source_name="PET uptake patient",
        ),
        solve_pet_isotropic_barrier(
            physics,
            material_key="concrete_2350kg_m3",
            distance_m=3.0,
            occupancy_factor=0.25,
            design_goal_uSv_per_week=10.0,
            source_name="PET scanner patient",
        ),
    )
    return pet_project_snapshot_to_dict(
        PetProjectDomainSnapshot(source, physics, barriers)
    )


def test_pet_headless_replay_reconstructs_and_recomputes_deterministically():
    result = replay_pet_project_snapshot(_payload())

    assert result.contract_version == PET_HEADLESS_REPLAY_CONTRACT_VERSION
    assert result.deterministic is True
    assert result.replayed_snapshot == result.stored_snapshot
    assert len(result.replayed_snapshot.barrier_results) == 2
    assert result.replayed_snapshot.barrier_results[0].solver_result.material_key == "lead"
    assert "AAPM Task Group 108" in (
        result.replayed_snapshot.barrier_results[0]
        .solver_result.attenuation_provenance
    )


def test_pet_headless_replay_loads_json_file_without_ui(tmp_path):
    path = tmp_path / "pet_snapshot.json"
    path.write_text(json.dumps(_payload(), indent=2), encoding="utf-8")

    result = load_and_replay_pet_project_snapshot(path)

    assert result.deterministic is True
    assert result.replayed_snapshot.source.radionuclide == "F18"


def test_pet_headless_replay_supports_source_and_physics_only_snapshot():
    source = PetSourceDomain(
        radionuclide="Ga68",
        injected_activity_mbq=150.0,
        patients_per_week=12.0,
        exposure_phases=(PetExposurePhase("Imaging", 0.5, 0.5),),
    )
    physics = calculate_pet_weekly_dose_at_1m(source)
    payload = pet_project_snapshot_to_dict(PetProjectDomainSnapshot(source, physics))

    result = replay_pet_project_snapshot(payload)

    assert result.replayed_snapshot.barrier_results == ()
    assert result.replayed_snapshot.physics_result == physics


@pytest.mark.parametrize(
    ("field_path", "replacement", "message"),
    [
        (("physics_result", "weekly_dose_uSv_at_1m"), 1.0, "weekly dose"),
        (("physics_result", "phase_results", 0, "decay_integrated_hours"), 1.0, "phase 0"),
        (("barrier_results", 0, "solver_result", "required_thickness_mm"), 1.0, "barrier 0"),
        (("barrier_results", 0, "dataset", "approved_by"), "Altered", "dataset field"),
    ],
)
def test_pet_headless_replay_rejects_tampered_stored_results(
    field_path, replacement, message
):
    payload = copy.deepcopy(_payload())
    target = payload
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = replacement

    with pytest.raises(PetHeadlessReplayError, match=message):
        replay_pet_project_snapshot(payload)


def test_pet_headless_replay_rejects_invalid_json_and_non_object_root(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(PetHeadlessReplayError, match="Unable to load"):
        load_and_replay_pet_project_snapshot(invalid)

    array_root = tmp_path / "array.json"
    array_root.write_text("[]", encoding="utf-8")
    with pytest.raises(PetHeadlessReplayError, match="root must be an object"):
        load_and_replay_pet_project_snapshot(array_root)


def test_pet_headless_replay_remains_outside_ui_production_serializer_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    forbidden = (
        "replay_pet_project_snapshot",
        "load_and_replay_pet_project_snapshot",
        "PetHeadlessReplayResult",
        "PET_HEADLESS_REPLAY_CONTRACT_VERSION",
    )
    paths = [
        Path("app.py"),
        Path("services/project_serializer.py"),
        Path("engine/shielding_engine.py"),
        *Path("reports").glob("*.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for name in forbidden:
        assert name not in combined
