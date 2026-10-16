"""Tests for the isolated PET calculation-service boundary."""

import json
from pathlib import Path

import pytest

from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PetExposurePhase,
    PetSourceDomain,
)
from services.pet_calculation_service import (
    PET_CALCULATION_SERVICE_CONTRACT_VERSION,
    PetBarrierCalculationRequest,
    PetCalculationServiceError,
    calculate_pet_project_snapshot,
    run_pet_calculation_service,
)


def _source() -> PetSourceDomain:
    return PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=200.0,
        patients_per_week=20.0,
        residual_activity_factor=0.9,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 0.75),
        ),
    )


def _requests() -> tuple[PetBarrierCalculationRequest, ...]:
    return (
        PetBarrierCalculationRequest(
            material_key="lead",
            distance_m=2.0,
            occupancy_factor=0.5,
            design_goal_uSv_per_week=10.0,
            provided_thickness_mm=16.0,
            source_name="PET uptake patient",
        ),
        PetBarrierCalculationRequest(
            material_key="concrete_2350kg_m3",
            distance_m=3.0,
            occupancy_factor=0.25,
            design_goal_uSv_per_week=10.0,
        ),
    )


def test_pet_calculation_service_returns_replayable_snapshot_and_payload():
    result = run_pet_calculation_service(_source(), _requests())

    assert result.contract_version == PET_CALCULATION_SERVICE_CONTRACT_VERSION
    assert result.source_type == "pet_patient"
    assert result.replay_verified is True
    assert result.replay.replayed_snapshot == result.snapshot
    assert result.payload["production_eligible"] is False
    assert len(result.snapshot.barrier_results) == 2
    assert result.snapshot.barrier_results[0].solver_result.material_key == "lead"
    assert result.snapshot.barrier_results[0].approved_by == "Steve H"
    assert "AAPM Task Group 108" in (
        result.snapshot.barrier_results[0].solver_result.attenuation_provenance
    )
    json.dumps(result.payload, allow_nan=False)


def test_pet_calculation_service_supports_source_only_snapshot():
    result = run_pet_calculation_service(_source())

    assert result.snapshot.barrier_results == ()
    assert result.snapshot.physics_result.radionuclide == "F18"
    assert result.replay_verified is True


def test_snapshot_calculation_is_deterministic_before_serialization():
    first = calculate_pet_project_snapshot(_source(), _requests())
    second = calculate_pet_project_snapshot(_source(), _requests())

    assert first == second


@pytest.mark.parametrize(
    "kwargs",
    [
        {"material_key": "", "distance_m": 1.0, "occupancy_factor": 1.0, "design_goal_uSv_per_week": 10.0},
        {"material_key": "lead", "distance_m": 0.0, "occupancy_factor": 1.0, "design_goal_uSv_per_week": 10.0},
        {"material_key": "lead", "distance_m": 1.0, "occupancy_factor": 1.1, "design_goal_uSv_per_week": 10.0},
        {"material_key": "lead", "distance_m": 1.0, "occupancy_factor": 1.0, "design_goal_uSv_per_week": float("nan")},
        {"material_key": "lead", "distance_m": 1.0, "occupancy_factor": 1.0, "design_goal_uSv_per_week": 10.0, "provided_thickness_mm": -1.0},
    ],
)
def test_pet_barrier_request_rejects_invalid_project_domain_values(kwargs):
    with pytest.raises(PetCalculationServiceError):
        PetBarrierCalculationRequest(**kwargs)


def test_pet_calculation_service_rejects_raw_mappings_and_invalid_request_members():
    with pytest.raises(PetCalculationServiceError, match="validated PetSourceDomain"):
        run_pet_calculation_service({"radionuclide": "F18"})  # type: ignore[arg-type]

    with pytest.raises(PetCalculationServiceError, match=r"barrier_requests\[0\]"):
        run_pet_calculation_service(_source(), ({"material_key": "lead"},))  # type: ignore[arg-type]


def test_pet_calculation_service_remains_outside_ui_production_serializer_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    forbidden = (
        "run_pet_calculation_service",
        "calculate_pet_project_snapshot",
        "PetBarrierCalculationRequest",
        "PetCalculationServiceResult",
        "PET_CALCULATION_SERVICE_CONTRACT_VERSION",
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
