"""Tests for the isolated PET project-domain serialization contract."""

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
from serialization.pet_project_contract import (
    PET_PROJECT_SERIALIZATION_SCHEMA,
    PET_PROJECT_SERIALIZATION_VERSION,
    PetProjectDomainSnapshot,
    PetProjectSerializationError,
    pet_project_snapshot_from_dict,
    pet_project_snapshot_to_dict,
)


def _snapshot() -> PetProjectDomainSnapshot:
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
    lead = solve_pet_isotropic_barrier(
        physics,
        material_key="lead",
        distance_m=2.0,
        occupancy_factor=0.5,
        design_goal_uSv_per_week=10.0,
        provided_thickness_mm=16.0,
        source_name="PET uptake patient",
    )
    concrete = solve_pet_isotropic_barrier(
        physics,
        material_key="concrete_2350kg_m3",
        distance_m=3.0,
        occupancy_factor=0.25,
        design_goal_uSv_per_week=10.0,
    )
    return PetProjectDomainSnapshot(source, physics, (lead, concrete))


def test_pet_project_snapshot_is_json_compatible_and_explicitly_non_production():
    payload = pet_project_snapshot_to_dict(_snapshot())

    assert payload["schema"] == PET_PROJECT_SERIALIZATION_SCHEMA
    assert payload["schema_version"] == PET_PROJECT_SERIALIZATION_VERSION
    assert payload["production_eligible"] is False
    assert payload["source"]["radionuclide"] == "F18"
    assert len(payload["barrier_results"]) == 2
    assert payload["barrier_results"][0]["dataset"]["approved_by"] == "Steve H"
    assert payload["barrier_results"][0]["solver_result"]["material_key"] == "lead"

    encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
    assert "radshield_pet_project_domain_v2" in encoded


def test_pet_project_snapshot_round_trip_preserves_source_physics_solver_and_provenance():
    original = _snapshot()
    payload = json.loads(json.dumps(pet_project_snapshot_to_dict(original)))
    restored = pet_project_snapshot_from_dict(payload)

    assert restored == original
    assert restored.source.exposure_phases[1].activity_retention_factor == 0.75
    assert restored.physics_result.weekly_dose_uSv_at_1m == pytest.approx(
        original.physics_result.weekly_dose_uSv_at_1m
    )
    assert restored.barrier_results[0].solver_result.required_thickness_mm == pytest.approx(
        original.barrier_results[0].solver_result.required_thickness_mm
    )
    assert "AAPM Task Group 108" in (
        restored.barrier_results[0].solver_result.attenuation_provenance
    )


def test_pet_project_snapshot_supports_source_and_physics_without_barrier_results():
    source = PetSourceDomain(
        radionuclide="Ga68",
        injected_activity_mbq=150.0,
        patients_per_week=12.0,
        exposure_phases=(PetExposurePhase("Imaging", 0.5, 0.5),),
    )
    snapshot = PetProjectDomainSnapshot(
        source=source,
        physics_result=calculate_pet_weekly_dose_at_1m(source),
    )

    restored = pet_project_snapshot_from_dict(
        pet_project_snapshot_to_dict(snapshot)
    )
    assert restored == snapshot
    assert restored.barrier_results == ()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 99),
        (("production_eligible",), True),
        (("physics_result", "contract_version"), 99),
        (("physics_result", "radiation_type"), "xray_140kvp"),
        (("barrier_results", 0, "adapter_contract_version"), 99),
        (("barrier_results", 0, "solver_result", "source_type"), "ct_scatter"),
        (("barrier_results", 0, "solver_result", "required_thickness_mm"), float("nan")),
    ],
)
def test_pet_project_snapshot_rejects_invalid_versions_identity_and_nonfinite_values(path, value):
    payload = pet_project_snapshot_to_dict(_snapshot())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(PetProjectSerializationError):
        pet_project_snapshot_from_dict(payload)


def test_pet_project_snapshot_rejects_source_physics_radionuclide_mismatch():
    payload = pet_project_snapshot_to_dict(_snapshot())
    payload["physics_result"]["radionuclide"] = "Ga68"

    with pytest.raises(
        PetProjectSerializationError,
        match="radionuclide must match",
    ):
        pet_project_snapshot_from_dict(payload)


def test_pet_serialization_contract_remains_outside_working_project_ui_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    forbidden = (
        "pet_project_snapshot_to_dict",
        "pet_project_snapshot_from_dict",
        "PetProjectDomainSnapshot",
        "radshield_pet_project_domain_v2",
    )
    paths = [
        Path("app.py"),
        Path("services/project_serializer.py"),
        Path("models/shielding_models.py"),
        Path("engine/shielding_engine.py"),
        *Path("reports").glob("*.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for name in forbidden:
        assert name not in combined
