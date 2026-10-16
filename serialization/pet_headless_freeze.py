"""Frozen baseline for the non-production PET headless calculation path.

This module is intentionally small and dependency-light.  It records the
contract versions and regression gate that define the approved headless PET
baseline before any UI or production-report integration begins.

Changing any frozen value requires an explicit architectural unfreeze:

1. update the affected contract version(s),
2. update the PET regression fixtures/manifest where appropriate,
3. run both validation-gate commands, and
4. document the reason for the unfreeze.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.barrier_input_contract import BARRIER_SOURCE_INPUT_CONTRACT_VERSION
from engine.isotropic_barrier_solver import ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION
from engine.material_attenuation_data import (
    MATERIAL_ATTENUATION_CONTRACT_VERSION,
    MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION,
)
from modalities.pet import (
    PET_BARRIER_ADAPTER_CONTRACT_VERSION,
    PET_PHYSICS_CONTRACT_VERSION,
)
from serialization.pet_headless_replay import PET_HEADLESS_REPLAY_CONTRACT_VERSION
from services.pet_calculation_service import PET_CALCULATION_SERVICE_CONTRACT_VERSION

PET_HEADLESS_PATH_FROZEN = True
PET_HEADLESS_FREEZE_BASELINE = "pet-headless-v2-activity-retention"
PET_HEADLESS_FREEZE_DATE = "2026-08-17"

PET_VALIDATION_GATE_COMMANDS = (
    "python -m pytest -q",
    "python -m tools.pet_cli_regression .\\tests\\fixtures\\pet_requests\\pet_cli_regression_manifest.json",
)


@dataclass(frozen=True)
class PetHeadlessFreezeVersions:
    physics: int
    barrier_adapter: int
    barrier_source_input: int
    isotropic_solver: int
    material_attenuation: int
    attenuation_dataset_schema: int
    calculation_service: int
    headless_replay: int


FROZEN_PET_HEADLESS_VERSIONS = PetHeadlessFreezeVersions(
    physics=2,
    barrier_adapter=1,
    barrier_source_input=1,
    isotropic_solver=1,
    material_attenuation=1,
    attenuation_dataset_schema=1,
    calculation_service=1,
    headless_replay=1,
)


def current_pet_headless_versions() -> PetHeadlessFreezeVersions:
    """Return the currently imported PET headless contract versions."""

    return PetHeadlessFreezeVersions(
        physics=PET_PHYSICS_CONTRACT_VERSION,
        barrier_adapter=PET_BARRIER_ADAPTER_CONTRACT_VERSION,
        barrier_source_input=BARRIER_SOURCE_INPUT_CONTRACT_VERSION,
        isotropic_solver=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
        material_attenuation=MATERIAL_ATTENUATION_CONTRACT_VERSION,
        attenuation_dataset_schema=MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION,
        calculation_service=PET_CALCULATION_SERVICE_CONTRACT_VERSION,
        headless_replay=PET_HEADLESS_REPLAY_CONTRACT_VERSION,
    )


def assert_pet_headless_freeze_intact() -> None:
    """Raise if the approved PET headless baseline has changed silently."""

    if not PET_HEADLESS_PATH_FROZEN:
        raise RuntimeError("PET headless freeze marker is disabled.")
    current = current_pet_headless_versions()
    if current != FROZEN_PET_HEADLESS_VERSIONS:
        raise RuntimeError(
            "PET headless contract versions changed without an explicit freeze-baseline update: "
            f"expected {FROZEN_PET_HEADLESS_VERSIONS}, got {current}."
        )
