"""Headless, non-production SPECT Step 1 calculation service."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from engine.isotropic_barrier_solver import TvlAttenuationInput
from modalities.spect import (
    SPECT_SOURCE_TYPE,
    SpectContractError,
    SpectSourceDomain,
    calculate_spect_weekly_dose_at_1m,
    solve_spect_isotropic_barrier,
)
from serialization.spect_headless_replay import SpectHeadlessReplayResult, replay_spect_project_snapshot
from serialization.spect_project_contract import (
    SpectBarrierSnapshot,
    SpectProjectDomainSnapshot,
    spect_project_snapshot_to_dict,
)

SPECT_CALCULATION_SERVICE_CONTRACT_VERSION = 1


class SpectCalculationServiceError(ValueError):
    pass


@dataclass(frozen=True)
class SpectBarrierCalculationRequest:
    attenuation: TvlAttenuationInput
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    provided_thickness_mm: float | None = None
    source_name: str = "SPECT Patient Source"

    def __post_init__(self) -> None:
        if not isinstance(self.attenuation, TvlAttenuationInput):
            raise SpectCalculationServiceError("attenuation must be a TvlAttenuationInput.")
        _positive("distance_m", self.distance_m)
        _positive("design_goal_uSv_per_week", self.design_goal_uSv_per_week)
        occupancy = _finite("occupancy_factor", self.occupancy_factor)
        if not 0.0 <= occupancy <= 1.0:
            raise SpectCalculationServiceError("occupancy_factor must be between 0 and 1 inclusive.")
        if self.provided_thickness_mm is not None and _finite("provided_thickness_mm", self.provided_thickness_mm) < 0.0:
            raise SpectCalculationServiceError("provided_thickness_mm must be greater than or equal to zero.")
        if not str(self.source_name).strip():
            raise SpectCalculationServiceError("source_name must not be blank.")


@dataclass(frozen=True)
class SpectCalculationServiceResult:
    contract_version: int
    source_type: str
    snapshot: SpectProjectDomainSnapshot
    payload: dict
    replay: SpectHeadlessReplayResult

    @property
    def replay_verified(self) -> bool:
        return self.replay.deterministic


def _finite(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectCalculationServiceError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise SpectCalculationServiceError(f"{name} must be finite.")
    return number


def _positive(name: str, value: float) -> float:
    number = _finite(name, value)
    if number <= 0.0:
        raise SpectCalculationServiceError(f"{name} must be greater than zero.")
    return number


def calculate_spect_project_snapshot(
    source: SpectSourceDomain,
    barrier_requests: Sequence[SpectBarrierCalculationRequest] = (),
) -> SpectProjectDomainSnapshot:
    if not isinstance(source, SpectSourceDomain):
        raise SpectCalculationServiceError("source must be a validated SpectSourceDomain instance.")
    if isinstance(barrier_requests, (str, bytes)) or not isinstance(barrier_requests, Sequence):
        raise SpectCalculationServiceError("barrier_requests must be a sequence.")
    for index, request in enumerate(barrier_requests):
        if not isinstance(request, SpectBarrierCalculationRequest):
            raise SpectCalculationServiceError(
                f"barrier_requests[{index}] must be a SpectBarrierCalculationRequest."
            )
    try:
        physics = calculate_spect_weekly_dose_at_1m(source)
        barriers = tuple(
            SpectBarrierSnapshot(
                result=solve_spect_isotropic_barrier(
                    physics,
                    attenuation=request.attenuation,
                    distance_m=request.distance_m,
                    occupancy_factor=request.occupancy_factor,
                    design_goal_uSv_per_week=request.design_goal_uSv_per_week,
                    provided_thickness_mm=request.provided_thickness_mm,
                    source_name=request.source_name,
                ),
                attenuation=request.attenuation,
            )
            for request in barrier_requests
        )
    except SpectContractError as exc:
        raise SpectCalculationServiceError(str(exc)) from exc
    return SpectProjectDomainSnapshot(source, physics, barriers)


def run_spect_calculation_service(
    source: SpectSourceDomain,
    barrier_requests: Sequence[SpectBarrierCalculationRequest] = (),
) -> SpectCalculationServiceResult:
    snapshot = calculate_spect_project_snapshot(source, barrier_requests)
    payload = spect_project_snapshot_to_dict(snapshot)
    replay = replay_spect_project_snapshot(payload)
    return SpectCalculationServiceResult(
        contract_version=SPECT_CALCULATION_SERVICE_CONTRACT_VERSION,
        source_type=SPECT_SOURCE_TYPE,
        snapshot=snapshot,
        payload=payload,
        replay=replay,
    )
