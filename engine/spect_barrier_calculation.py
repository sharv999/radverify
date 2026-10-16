"""Headless Tc-99m practical barrier calculation adapter.

SPECT Step 4 combines the validated Step 1 Tc-99m patient-source workload with
the Step 20 frozen broad-beam Archer transmission data.  It remains explicitly
non-production and is not connected to UI, reports, serialization, modality
registration, or production shielding dispatch.

The adapter owns only the calculation choreography: source workload -> inverse
square distance -> occupancy/use factor -> required transmission -> Step 3
required thickness / provided transmission.  The practical material model
itself remains owned by :mod:`engine.spect_practical_transmission`.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from engine.barrier_input_contract import BarrierInputContractError
from engine.spect_practical_transmission import (
    LoadedSpectPracticalDataset,
    SpectPracticalTransmissionError,
    calculate_tc99m_required_thickness,
    calculate_tc99m_transmission,
    load_frozen_spect_tc99m_practical_dataset,
)
from modalities.spect import (
    SPECT_PHYSICS_CONTRACT_VERSION,
    SpectContractError,
    SpectPhysicsResult,
    SpectSourceDomain,
    calculate_spect_weekly_dose_at_1m,
    spect_barrier_source_input,
)


SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION = 1
SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS = "development_nonproduction"
SPECT_PRACTICAL_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "spect"
    / "spect_tc99m_practical_transmission_approved_frozen.json"
)


class SpectPracticalBarrierError(ValueError):
    """Raised when a Step 4 headless practical barrier request is invalid."""


@dataclass(frozen=True)
class SpectPracticalBarrierRequest:
    """Barrier-specific inputs applied to one validated SPECT source."""

    material_key: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    provided_thickness_mm: float | None = None
    source_name: str = "SPECT Patient Source"

    def __post_init__(self) -> None:
        material = str(self.material_key or "").strip()
        if not material:
            raise SpectPracticalBarrierError("material_key must not be blank.")
        object.__setattr__(self, "material_key", material)
        object.__setattr__(self, "distance_m", _positive("distance_m", self.distance_m))
        object.__setattr__(
            self,
            "occupancy_factor",
            _unit_interval("occupancy_factor", self.occupancy_factor),
        )
        object.__setattr__(
            self,
            "design_goal_uSv_per_week",
            _positive("design_goal_uSv_per_week", self.design_goal_uSv_per_week),
        )
        if self.provided_thickness_mm is not None:
            object.__setattr__(
                self,
                "provided_thickness_mm",
                _non_negative("provided_thickness_mm", self.provided_thickness_mm),
            )
        source_name = str(self.source_name or "").strip()
        if not source_name:
            raise SpectPracticalBarrierError("source_name must not be blank.")
        object.__setattr__(self, "source_name", source_name)


@dataclass(frozen=True)
class SpectPracticalBarrierResult:
    """Deterministic Step 4 result for one Tc-99m practical barrier."""

    adapter_contract_version: int
    adapter_status: str
    source_physics: SpectPhysicsResult
    material_key: str
    practical_record_id: str
    practical_provenance: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    unshielded_weekly_dose_uSv_at_barrier: float
    occupied_unshielded_weekly_dose_uSv: float
    required_transmission: float
    required_thickness_mm: float
    required_room_scatter_caution: bool
    required_source_model_extrapolation: bool
    required_scope_note: str
    provided_thickness_mm: float | None
    provided_transmission: float | None
    transmitted_weekly_dose_uSv: float | None
    provided_room_scatter_caution: bool | None
    provided_scope_note: str | None
    compliance_status: str


def _finite(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectPracticalBarrierError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise SpectPracticalBarrierError(f"{name} must be finite.")
    return number


def _positive(name: str, value: float) -> float:
    number = _finite(name, value)
    if number <= 0.0:
        raise SpectPracticalBarrierError(f"{name} must be greater than zero.")
    return number


def _non_negative(name: str, value: float) -> float:
    number = _finite(name, value)
    if number < 0.0:
        raise SpectPracticalBarrierError(f"{name} must be greater than or equal to zero.")
    return number


def _unit_interval(name: str, value: float) -> float:
    number = _finite(name, value)
    if not 0.0 <= number <= 1.0:
        raise SpectPracticalBarrierError(f"{name} must be between 0 and 1 inclusive.")
    return number


def calculate_spect_tc99m_practical_barrier(
    source: SpectSourceDomain,
    request: SpectPracticalBarrierRequest,
    *,
    dataset: LoadedSpectPracticalDataset | None = None,
) -> SpectPracticalBarrierResult:
    """Calculate one headless Tc-99m barrier using the Step 3 practical model.

    The returned compliance status is a development calculation result only.
    In particular, low-transmission Step 3 room-scatter cautions are propagated
    and are not converted into production acceptance criteria.
    """

    if not isinstance(source, SpectSourceDomain):
        raise SpectPracticalBarrierError("source must be a validated SpectSourceDomain.")
    if not isinstance(request, SpectPracticalBarrierRequest):
        raise SpectPracticalBarrierError("request must be a SpectPracticalBarrierRequest.")

    practical_dataset = dataset
    if practical_dataset is None:
        try:
            practical_dataset = load_frozen_spect_tc99m_practical_dataset(
                SPECT_PRACTICAL_DATASET_PATH
            )
        except SpectPracticalTransmissionError as exc:
            raise SpectPracticalBarrierError(str(exc)) from exc
    if not isinstance(practical_dataset, LoadedSpectPracticalDataset):
        raise SpectPracticalBarrierError(
            "dataset must be a validated LoadedSpectPracticalDataset."
        )

    try:
        physics = calculate_spect_weekly_dose_at_1m(source)
    except SpectContractError as exc:
        raise SpectPracticalBarrierError(str(exc)) from exc
    if int(physics.contract_version) != SPECT_PHYSICS_CONTRACT_VERSION:
        raise SpectPracticalBarrierError(
            f"Unsupported SPECT physics contract version {physics.contract_version!r}."
        )

    try:
        barrier_source = spect_barrier_source_input(
            physics, source_name=request.source_name
        )
        dose_at_barrier = barrier_source.weekly_dose_uSv_at_distance(request.distance_m)
    except (SpectContractError, BarrierInputContractError) as exc:
        raise SpectPracticalBarrierError(str(exc)) from exc

    occupied_unshielded = (
        dose_at_barrier
        * barrier_source.use_factor
        * request.occupancy_factor
    )
    required_transmission = (
        1.0
        if occupied_unshielded <= 0.0
        else min(1.0, request.design_goal_uSv_per_week / occupied_unshielded)
    )

    try:
        required = calculate_tc99m_required_thickness(
            practical_dataset,
            material_key=request.material_key,
            target_transmission=required_transmission,
        )
    except SpectPracticalTransmissionError as exc:
        raise SpectPracticalBarrierError(str(exc)) from exc

    provided_transmission = None
    transmitted_weekly_dose = None
    provided_room_scatter_caution = None
    provided_scope_note = None
    compliance_status = "NOT_ASSESSED"
    if request.provided_thickness_mm is not None:
        try:
            provided = calculate_tc99m_transmission(
                practical_dataset,
                material_key=request.material_key,
                thickness_mm=request.provided_thickness_mm,
            )
        except SpectPracticalTransmissionError as exc:
            raise SpectPracticalBarrierError(str(exc)) from exc
        provided_transmission = provided.transmission
        transmitted_weekly_dose = occupied_unshielded * provided.transmission
        provided_room_scatter_caution = provided.room_scatter_caution
        provided_scope_note = provided.scope_note
        compliance_status = (
            "PASS"
            if transmitted_weekly_dose <= request.design_goal_uSv_per_week
            else "FAIL"
        )

    return SpectPracticalBarrierResult(
        adapter_contract_version=SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION,
        adapter_status=SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS,
        source_physics=physics,
        material_key=required.material_key,
        practical_record_id=required.record_id,
        practical_provenance=required.provenance,
        distance_m=request.distance_m,
        occupancy_factor=request.occupancy_factor,
        design_goal_uSv_per_week=request.design_goal_uSv_per_week,
        unshielded_weekly_dose_uSv_at_barrier=dose_at_barrier,
        occupied_unshielded_weekly_dose_uSv=occupied_unshielded,
        required_transmission=required_transmission,
        required_thickness_mm=required.required_thickness_mm,
        required_room_scatter_caution=required.room_scatter_caution,
        required_source_model_extrapolation=required.source_model_extrapolation,
        required_scope_note=required.scope_note,
        provided_thickness_mm=request.provided_thickness_mm,
        provided_transmission=provided_transmission,
        transmitted_weekly_dose_uSv=transmitted_weekly_dose,
        provided_room_scatter_caution=provided_room_scatter_caution,
        provided_scope_note=provided_scope_note,
        compliance_status=compliance_status,
    )
