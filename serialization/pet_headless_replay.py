"""Headless deterministic replay contract for isolated PET snapshots.

This module validates a serialized PET project-domain snapshot, reconstructs
its source and stored results, independently recomputes the PET physics and
barrier calculations, and verifies deterministic equivalence.  It deliberately
does not import the Tk UI, production project serializer, shielding dispatch,
or report pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isclose
from pathlib import Path
from typing import Any, Mapping

from modalities.pet import (
    PetBarrierCalculationResult,
    PetPhysicsResult,
    calculate_pet_weekly_dose_at_1m,
    solve_pet_isotropic_barrier,
)
from serialization.pet_project_contract import (
    PetProjectDomainSnapshot,
    PetProjectSerializationError,
    pet_project_snapshot_from_dict,
    pet_project_snapshot_to_dict,
)


PET_HEADLESS_REPLAY_CONTRACT_VERSION = 1
_REPLAY_REL_TOL = 1e-12
_REPLAY_ABS_TOL = 1e-12


class PetHeadlessReplayError(ValueError):
    """Raised when a PET snapshot cannot be replayed deterministically."""


@dataclass(frozen=True)
class PetHeadlessReplayResult:
    """Validated stored and independently replayed PET snapshots."""

    contract_version: int
    stored_snapshot: PetProjectDomainSnapshot
    replayed_snapshot: PetProjectDomainSnapshot

    @property
    def deterministic(self) -> bool:
        return True


def _numbers_match(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return isclose(
        float(left),
        float(right),
        rel_tol=_REPLAY_REL_TOL,
        abs_tol=_REPLAY_ABS_TOL,
    )


def _assert_physics_match(stored: PetPhysicsResult, replayed: PetPhysicsResult) -> None:
    scalar_fields = (
        "contract_version",
        "radionuclide",
        "radiation_type",
        "tvl_key",
        "calculation_basis",
    )
    for field in scalar_fields:
        if getattr(stored, field) != getattr(replayed, field):
            raise PetHeadlessReplayError(
                f"Replayed PET physics field {field!r} does not match the stored result."
            )
    if not _numbers_match(
        stored.weekly_dose_uSv_at_1m,
        replayed.weekly_dose_uSv_at_1m,
    ):
        raise PetHeadlessReplayError(
            "Replayed PET weekly dose at 1 m does not match the stored result."
        )
    if len(stored.phase_results) != len(replayed.phase_results):
        raise PetHeadlessReplayError(
            "Replayed PET phase-result count does not match the stored result."
        )
    for index, (left, right) in enumerate(
        zip(stored.phase_results, replayed.phase_results, strict=True)
    ):
        if left.name != right.name:
            raise PetHeadlessReplayError(
                f"Replayed PET phase {index} name does not match the stored result."
            )
        for field in (
            "start_time_h",
            "duration_h",
            "activity_retention_factor",
            "decay_integrated_hours",
            "weekly_dose_uSv_at_1m",
        ):
            if not _numbers_match(getattr(left, field), getattr(right, field)):
                raise PetHeadlessReplayError(
                    f"Replayed PET phase {index} field {field!r} does not match the stored result."
                )


def _replay_barrier(
    physics: PetPhysicsResult,
    stored: PetBarrierCalculationResult,
) -> PetBarrierCalculationResult:
    solved = stored.solver_result
    return solve_pet_isotropic_barrier(
        physics,
        material_key=solved.material_key,
        distance_m=solved.distance_m,
        occupancy_factor=solved.occupancy_factor,
        design_goal_uSv_per_week=solved.design_goal_uSv_per_week,
        provided_thickness_mm=solved.provided_thickness_mm,
        source_name=solved.source_name,
    )


def _assert_barrier_match(
    index: int,
    stored: PetBarrierCalculationResult,
    replayed: PetBarrierCalculationResult,
) -> None:
    for field in ("dataset_id", "dataset_revision", "approved_by", "approved_date"):
        if getattr(stored, field) != getattr(replayed, field):
            raise PetHeadlessReplayError(
                f"Replayed PET barrier {index} dataset field {field!r} does not match."
            )

    left = stored.solver_result
    right = replayed.solver_result
    text_fields = (
        "contract_version",
        "solver_mode",
        "source_name",
        "source_type",
        "radiation_type",
        "tvl_key",
        "material_key",
        "attenuation_record_id",
        "attenuation_provenance",
        "compliance_status",
    )
    for field in text_fields:
        if getattr(left, field) != getattr(right, field):
            raise PetHeadlessReplayError(
                f"Replayed PET barrier {index} field {field!r} does not match."
            )

    numeric_fields = (
        "distance_m",
        "occupancy_factor",
        "design_goal_uSv_per_week",
        "unshielded_weekly_dose_uSv_at_barrier",
        "occupied_unshielded_weekly_dose_uSv",
        "required_transmission",
        "required_tvl_count",
        "required_thickness_mm",
        "provided_thickness_mm",
        "provided_transmission",
        "transmitted_weekly_dose_uSv",
    )
    for field in numeric_fields:
        if not _numbers_match(getattr(left, field), getattr(right, field)):
            raise PetHeadlessReplayError(
                f"Replayed PET barrier {index} field {field!r} does not match."
            )


def replay_pet_project_snapshot(
    payload: Mapping[str, Any],
) -> PetHeadlessReplayResult:
    """Validate and deterministically replay one serialized PET snapshot."""

    try:
        stored = pet_project_snapshot_from_dict(payload)
    except PetProjectSerializationError as exc:
        raise PetHeadlessReplayError(str(exc)) from exc

    replayed_physics = calculate_pet_weekly_dose_at_1m(stored.source)
    _assert_physics_match(stored.physics_result, replayed_physics)

    replayed_barriers = tuple(
        _replay_barrier(replayed_physics, result)
        for result in stored.barrier_results
    )
    for index, (left, right) in enumerate(
        zip(stored.barrier_results, replayed_barriers, strict=True)
    ):
        _assert_barrier_match(index, left, right)

    replayed = PetProjectDomainSnapshot(
        source=stored.source,
        physics_result=replayed_physics,
        barrier_results=replayed_barriers,
    )
    if pet_project_snapshot_to_dict(stored) != pet_project_snapshot_to_dict(replayed):
        raise PetHeadlessReplayError(
            "Replayed PET snapshot is not byte-structure deterministic after normalization."
        )

    return PetHeadlessReplayResult(
        contract_version=PET_HEADLESS_REPLAY_CONTRACT_VERSION,
        stored_snapshot=stored,
        replayed_snapshot=replayed,
    )


def load_and_replay_pet_project_snapshot(path: str | Path) -> PetHeadlessReplayResult:
    """Load one JSON PET snapshot from disk and replay it headlessly."""

    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetHeadlessReplayError(
            f"Unable to load PET project-domain snapshot {source_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise PetHeadlessReplayError("PET project-domain JSON root must be an object.")
    return replay_pet_project_snapshot(payload)
