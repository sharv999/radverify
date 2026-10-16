"""Tests for the isolated PET calculation-request serialization contract."""

import copy
import json
from pathlib import Path

import pytest

from modalities.pet import PET_CALCULATION_BLOCK_REASON, PetExposurePhase, PetSourceDomain
from serialization.pet_calculation_request_contract import (
    PET_CALCULATION_REQUEST_SCHEMA,
    PET_CALCULATION_REQUEST_VERSION,
    PetCalculationRequestEnvelope,
    PetCalculationRequestSerializationError,
    load_and_replay_pet_calculation_request,
    pet_calculation_request_from_dict,
    pet_calculation_request_to_dict,
    replay_pet_calculation_request,
)
from services.pet_calculation_service import PetBarrierCalculationRequest


def _request() -> PetCalculationRequestEnvelope:
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
    barriers = (
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
    return PetCalculationRequestEnvelope(source, barriers)


def test_pet_request_is_json_compatible_versioned_and_non_production():
    payload = pet_calculation_request_to_dict(_request())

    assert payload["schema"] == PET_CALCULATION_REQUEST_SCHEMA
    assert payload["schema_version"] == PET_CALCULATION_REQUEST_VERSION
    assert payload["production_eligible"] is False
    assert payload["source"]["radionuclide"] == "F18"
    assert len(payload["barrier_requests"]) == 2
    json.dumps(payload, allow_nan=False, sort_keys=True)


def test_pet_request_round_trip_preserves_validated_domain_objects():
    original = _request()
    restored = pet_calculation_request_from_dict(
        json.loads(json.dumps(pet_calculation_request_to_dict(original)))
    )

    assert restored == original
    assert restored.source.exposure_phases[1].activity_retention_factor == 0.75
    assert restored.barrier_requests[0].provided_thickness_mm == 16.0


def test_serialized_request_replays_through_isolated_service_deterministically():
    payload = pet_calculation_request_to_dict(_request())

    first = replay_pet_calculation_request(payload)
    second = replay_pet_calculation_request(copy.deepcopy(payload))

    assert first.replay_verified is True
    assert first.snapshot == second.snapshot
    assert first.payload == second.payload
    assert first.payload["production_eligible"] is False
    assert first.snapshot.barrier_results[0].approved_by == "Steve H"


def test_request_can_be_saved_loaded_and_replayed_without_ui_state(tmp_path):
    path = tmp_path / "pet-request.json"
    path.write_text(
        json.dumps(pet_calculation_request_to_dict(_request()), indent=2),
        encoding="utf-8",
    )

    result = load_and_replay_pet_calculation_request(path)

    assert result.replay_verified is True
    assert result.snapshot.source.radionuclide_spec.code == "F18"
    assert len(result.snapshot.barrier_results) == 2


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "unknown"),
        (("schema_version",), 99),
        (("production_eligible",), True),
        (("source", "injected_activity_mbq"), float("nan")),
        (("source", "exposure_phases", 0, "activity_retention_factor"), 1.5),
        (("barrier_requests", 0, "distance_m"), 0.0),
        (("barrier_requests", 0, "occupancy_factor"), -0.1),
    ],
)
def test_pet_request_rejects_invalid_schema_nonfinite_and_domain_values(path, value):
    payload = pet_calculation_request_to_dict(_request())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(PetCalculationRequestSerializationError):
        pet_calculation_request_from_dict(payload)


def test_pet_request_replay_rejects_noncanonical_extra_fields():
    payload = pet_calculation_request_to_dict(_request())
    payload["unexpected"] = "not allowed"

    with pytest.raises(PetCalculationRequestSerializationError, match="canonical"):
        replay_pet_calculation_request(payload)


def test_pet_request_contract_remains_outside_ui_production_serializer_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    forbidden = (
        "pet_calculation_request_to_dict",
        "pet_calculation_request_from_dict",
        "replay_pet_calculation_request",
        "PetCalculationRequestEnvelope",
        PET_CALCULATION_REQUEST_SCHEMA,
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
