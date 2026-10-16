"""Isolated PET calculation-service boundary.

The service accepts validated PET project-domain objects, calculates PET
physics and optional isotropic/non-beam barriers, serializes the resulting
snapshot, and verifies deterministic headless replay before returning it.

It is deliberately not connected to the Tk UI, production project serializer,
production shielding dispatch, or report pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from modalities.pet import (
    PET_SOURCE_TYPE,
    PetBarrierCalculationResult,
    PetContractError,
    PetSourceDomain,
    calculate_pet_weekly_dose_at_1m,
    solve_pet_isotropic_barrier,
)
from serialization.pet_headless_replay import (
    PetHeadlessReplayResult,
    replay_pet_project_snapshot,
)
from serialization.pet_project_contract import (
    PetProjectDomainSnapshot,
    pet_project_snapshot_to_dict,
)


PET_CALCULATION_SERVICE_CONTRACT_VERSION = 1


class PetCalculationServiceError(ValueError):
    """Raised when a PET service request violates the service contract."""


@dataclass(frozen=True)
class PetBarrierCalculationRequest:
    """Validated project-domain request for one PET barrier calculation."""

    material_key: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    provided_thickness_mm: float | None = None
    source_name: str = "PET Patient Source"

    def __post_init__(self) -> None:
        if not str(self.material_key).strip():
            raise PetCalculationServiceError("material_key must not be blank.")
        if not str(self.source_name).strip():
            raise PetCalculationServiceError("source_name must not be blank.")
        _require_finite_positive("distance_m", self.distance_m)
        _require_finite_positive(
            "design_goal_uSv_per_week", self.design_goal_uSv_per_week
        )
        occupancy = _require_finite("occupancy_factor", self.occupancy_factor)
        if not 0.0 <= occupancy <= 1.0:
            raise PetCalculationServiceError(
                "occupancy_factor must be between 0 and 1 inclusive."
            )
        if self.provided_thickness_mm is not None:
            thickness = _require_finite(
                "provided_thickness_mm", self.provided_thickness_mm
            )
            if thickness < 0.0:
                raise PetCalculationServiceError(
                    "provided_thickness_mm must be greater than or equal to zero."
                )


@dataclass(frozen=True)
class PetCalculationServiceResult:
    """Replay-verified output from the isolated PET calculation service."""

    contract_version: int
    source_type: str
    snapshot: PetProjectDomainSnapshot
    payload: Mapping[str, Any]
    replay: PetHeadlessReplayResult

    @property
    def replay_verified(self) -> bool:
        return self.replay.deterministic


def _require_finite(name: str, value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PetCalculationServiceError(f"{name} must be numeric.") from exc
    if not isfinite(numeric):
        raise PetCalculationServiceError(f"{name} must be finite.")
    return numeric


def _require_finite_positive(name: str, value: float) -> float:
    numeric = _require_finite(name, value)
    if numeric <= 0.0:
        raise PetCalculationServiceError(f"{name} must be greater than zero.")
    return numeric


def calculate_pet_project_snapshot(
    source: PetSourceDomain,
    barrier_requests: Sequence[PetBarrierCalculationRequest] = (),
) -> PetProjectDomainSnapshot:
    """Calculate one isolated PET project-domain snapshot.

    ``source`` and every barrier request must already be validated domain
    objects. Raw mappings are intentionally rejected so parsing remains outside
    this calculation boundary.
    """

    if not isinstance(source, PetSourceDomain):
        raise PetCalculationServiceError(
            "source must be a validated PetSourceDomain instance."
        )
    if isinstance(barrier_requests, (str, bytes)) or not isinstance(
        barrier_requests, Sequence
    ):
        raise PetCalculationServiceError(
            "barrier_requests must be a sequence of PetBarrierCalculationRequest objects."
        )
    for index, request in enumerate(barrier_requests):
        if not isinstance(request, PetBarrierCalculationRequest):
            raise PetCalculationServiceError(
                f"barrier_requests[{index}] must be a PetBarrierCalculationRequest."
            )

    try:
        physics = calculate_pet_weekly_dose_at_1m(source)
        barriers: tuple[PetBarrierCalculationResult, ...] = tuple(
            solve_pet_isotropic_barrier(
                physics,
                material_key=request.material_key,
                distance_m=request.distance_m,
                occupancy_factor=request.occupancy_factor,
                design_goal_uSv_per_week=request.design_goal_uSv_per_week,
                provided_thickness_mm=request.provided_thickness_mm,
                source_name=request.source_name,
            )
            for request in barrier_requests
        )
    except PetContractError as exc:
        raise PetCalculationServiceError(str(exc)) from exc

    return PetProjectDomainSnapshot(
        source=source,
        physics_result=physics,
        barrier_results=barriers,
    )


def run_pet_calculation_service(
    source: PetSourceDomain,
    barrier_requests: Sequence[PetBarrierCalculationRequest] = (),
) -> PetCalculationServiceResult:
    """Calculate, serialize, and replay-verify one PET snapshot."""

    snapshot = calculate_pet_project_snapshot(source, barrier_requests)
    payload = pet_project_snapshot_to_dict(snapshot)
    replay = replay_pet_project_snapshot(payload)
    if replay.replayed_snapshot != snapshot:
        raise PetCalculationServiceError(
            "PET calculation service replay did not reproduce the calculated snapshot."
        )
    return PetCalculationServiceResult(
        contract_version=PET_CALCULATION_SERVICE_CONTRACT_VERSION,
        source_type=PET_SOURCE_TYPE,
        snapshot=snapshot,
        payload=payload,
        replay=replay,
    )
