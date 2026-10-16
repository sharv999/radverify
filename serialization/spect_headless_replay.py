"""Deterministic replay for non-production SPECT Step 1 snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Mapping

from modalities.spect import calculate_spect_weekly_dose_at_1m, solve_spect_isotropic_barrier
from serialization.spect_project_contract import (
    SpectBarrierSnapshot,
    SpectProjectDomainSnapshot,
    spect_project_snapshot_from_dict,
    spect_project_snapshot_to_dict,
)

SPECT_HEADLESS_REPLAY_CONTRACT_VERSION = 1


class SpectHeadlessReplayError(ValueError):
    pass


@dataclass(frozen=True)
class SpectHeadlessReplayResult:
    contract_version: int
    stored_snapshot: SpectProjectDomainSnapshot
    replayed_snapshot: SpectProjectDomainSnapshot

    @property
    def deterministic(self) -> bool:
        return True


def replay_spect_project_snapshot(payload: Mapping[str, Any]) -> SpectHeadlessReplayResult:
    stored = spect_project_snapshot_from_dict(payload)
    physics = calculate_spect_weekly_dose_at_1m(stored.source)
    if not isclose(physics.weekly_dose_uSv_at_1m, stored.physics_result.weekly_dose_uSv_at_1m, rel_tol=1e-12, abs_tol=1e-12):
        raise SpectHeadlessReplayError("Replayed SPECT weekly dose does not match stored result.")
    if physics != stored.physics_result:
        raise SpectHeadlessReplayError("Replayed SPECT physics does not match stored result.")

    barriers = []
    for item in stored.barrier_results:
        solved = item.result.solver_result
        replayed = solve_spect_isotropic_barrier(
            physics,
            attenuation=item.attenuation,
            distance_m=solved.distance_m,
            occupancy_factor=solved.occupancy_factor,
            design_goal_uSv_per_week=solved.design_goal_uSv_per_week,
            provided_thickness_mm=solved.provided_thickness_mm,
            source_name=solved.source_name,
        )
        if replayed != item.result:
            raise SpectHeadlessReplayError("Replayed SPECT barrier does not match stored result.")
        barriers.append(SpectBarrierSnapshot(replayed, item.attenuation))

    replayed_snapshot = SpectProjectDomainSnapshot(stored.source, physics, tuple(barriers))
    if spect_project_snapshot_to_dict(stored) != spect_project_snapshot_to_dict(replayed_snapshot):
        raise SpectHeadlessReplayError("Replayed SPECT snapshot is not deterministic after normalization.")
    return SpectHeadlessReplayResult(
        contract_version=SPECT_HEADLESS_REPLAY_CONTRACT_VERSION,
        stored_snapshot=stored,
        replayed_snapshot=replayed_snapshot,
    )
