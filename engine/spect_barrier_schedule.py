"""Headless multi-barrier SPECT schedule adapter.

SPECT Step 5 lifts the Step 4 single-barrier Tc-99m calculation into a
canonical, deterministic multi-barrier request/result contract suitable for a
future read-only UI preview.  It remains explicitly non-production and is not
connected to Tk UI, reports, project serialization, services, or production
shielding dispatch.

The adapter preserves caller request order, rejects duplicate barrier IDs, loads
one validated Step 3 practical-transmission dataset for the schedule, and
propagates Step 4 compliance/caution/provenance outputs without reimplementing
shielding physics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine.spect_barrier_calculation import (
    SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS,
    SPECT_PRACTICAL_DATASET_PATH,
    SpectPracticalBarrierError,
    SpectPracticalBarrierRequest,
    SpectPracticalBarrierResult,
    calculate_spect_tc99m_practical_barrier,
)
from engine.spect_practical_transmission import (
    LoadedSpectPracticalDataset,
    SpectPracticalTransmissionError,
    load_spect_tc99m_practical_dataset,
)
from modalities.spect import (
    SpectContractError,
    SpectPhysicsResult,
    SpectSourceDomain,
    calculate_spect_weekly_dose_at_1m,
)


SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION = 1
SPECT_BARRIER_SCHEDULE_STATUS = "development_nonproduction"


class SpectBarrierScheduleError(ValueError):
    """Raised when a Step 5 headless schedule request violates its contract."""


@dataclass(frozen=True)
class SpectBarrierScheduleRequest:
    """One named barrier request in the canonical Step 5 SPECT schedule."""

    barrier_id: str
    barrier_name: str
    material_key: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    provided_thickness_mm: float | None = None
    source_name: str = "SPECT Patient Source"

    def __post_init__(self) -> None:
        barrier_id = _required_text("barrier_id", self.barrier_id)
        barrier_name = _required_text("barrier_name", self.barrier_name)
        object.__setattr__(self, "barrier_id", barrier_id)
        object.__setattr__(self, "barrier_name", barrier_name)

        # Step 4 remains the owner of barrier-physics input validation.  Build
        # its request here so Step 5 cannot drift to a second numeric contract.
        try:
            calculation = SpectPracticalBarrierRequest(
                material_key=self.material_key,
                distance_m=self.distance_m,
                occupancy_factor=self.occupancy_factor,
                design_goal_uSv_per_week=self.design_goal_uSv_per_week,
                provided_thickness_mm=self.provided_thickness_mm,
                source_name=self.source_name,
            )
        except SpectPracticalBarrierError as exc:
            raise SpectBarrierScheduleError(str(exc)) from exc

        object.__setattr__(self, "material_key", calculation.material_key)
        object.__setattr__(self, "distance_m", calculation.distance_m)
        object.__setattr__(self, "occupancy_factor", calculation.occupancy_factor)
        object.__setattr__(
            self, "design_goal_uSv_per_week", calculation.design_goal_uSv_per_week
        )
        object.__setattr__(
            self, "provided_thickness_mm", calculation.provided_thickness_mm
        )
        object.__setattr__(self, "source_name", calculation.source_name)

    def to_calculation_request(self) -> SpectPracticalBarrierRequest:
        """Return the Step 4 request represented by this schedule row."""

        return SpectPracticalBarrierRequest(
            material_key=self.material_key,
            distance_m=self.distance_m,
            occupancy_factor=self.occupancy_factor,
            design_goal_uSv_per_week=self.design_goal_uSv_per_week,
            provided_thickness_mm=self.provided_thickness_mm,
            source_name=self.source_name,
        )


@dataclass(frozen=True)
class SpectBarrierScheduleRow:
    """Flattened deterministic result row for future presentation adapters."""

    schedule_index: int
    barrier_id: str
    barrier_name: str
    material_key: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    unshielded_weekly_dose_uSv_at_barrier: float
    occupied_unshielded_weekly_dose_uSv: float
    required_transmission: float
    required_thickness_mm: float
    provided_thickness_mm: float | None
    provided_transmission: float | None
    transmitted_weekly_dose_uSv: float | None
    compliance_status: str
    required_room_scatter_caution: bool
    provided_room_scatter_caution: bool | None
    required_source_model_extrapolation: bool
    practical_record_id: str
    practical_provenance: str
    required_scope_note: str
    provided_scope_note: str | None


@dataclass(frozen=True)
class SpectBarrierScheduleResult:
    """Canonical Step 5 result for one Tc-99m source and zero or more barriers."""

    contract_version: int
    status: str
    production_eligible: bool
    ordering_basis: str
    source_physics: SpectPhysicsResult
    rows: tuple[SpectBarrierScheduleRow, ...]
    pass_count: int
    fail_count: int
    not_assessed_count: int
    requires_room_scatter_review: bool
    contains_source_model_extrapolation: bool


def _required_text(name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise SpectBarrierScheduleError(f"{name} must not be blank.")
    return text


def _validate_requests(
    barrier_requests: Sequence[SpectBarrierScheduleRequest],
) -> tuple[SpectBarrierScheduleRequest, ...]:
    if isinstance(barrier_requests, (str, bytes)) or not isinstance(
        barrier_requests, Sequence
    ):
        raise SpectBarrierScheduleError(
            "barrier_requests must be a sequence of SpectBarrierScheduleRequest objects."
        )

    requests = tuple(barrier_requests)
    seen_ids: dict[str, int] = {}
    for index, request in enumerate(requests):
        if not isinstance(request, SpectBarrierScheduleRequest):
            raise SpectBarrierScheduleError(
                f"barrier_requests[{index}] must be a SpectBarrierScheduleRequest."
            )
        identity = request.barrier_id.casefold()
        if identity in seen_ids:
            first = seen_ids[identity]
            raise SpectBarrierScheduleError(
                f"Duplicate barrier_id {request.barrier_id!r} at barrier_requests[{index}]; "
                f"first used at barrier_requests[{first}]."
            )
        seen_ids[identity] = index
    return requests


def _load_dataset(
    dataset: LoadedSpectPracticalDataset | None,
) -> LoadedSpectPracticalDataset:
    if dataset is None:
        try:
            return load_spect_tc99m_practical_dataset(SPECT_PRACTICAL_DATASET_PATH)
        except SpectPracticalTransmissionError as exc:
            raise SpectBarrierScheduleError(str(exc)) from exc
    if not isinstance(dataset, LoadedSpectPracticalDataset):
        raise SpectBarrierScheduleError(
            "dataset must be a validated LoadedSpectPracticalDataset."
        )
    return dataset


def _row_from_result(
    index: int,
    request: SpectBarrierScheduleRequest,
    result: SpectPracticalBarrierResult,
) -> SpectBarrierScheduleRow:
    return SpectBarrierScheduleRow(
        schedule_index=index,
        barrier_id=request.barrier_id,
        barrier_name=request.barrier_name,
        material_key=result.material_key,
        distance_m=result.distance_m,
        occupancy_factor=result.occupancy_factor,
        design_goal_uSv_per_week=result.design_goal_uSv_per_week,
        unshielded_weekly_dose_uSv_at_barrier=result.unshielded_weekly_dose_uSv_at_barrier,
        occupied_unshielded_weekly_dose_uSv=result.occupied_unshielded_weekly_dose_uSv,
        required_transmission=result.required_transmission,
        required_thickness_mm=result.required_thickness_mm,
        provided_thickness_mm=result.provided_thickness_mm,
        provided_transmission=result.provided_transmission,
        transmitted_weekly_dose_uSv=result.transmitted_weekly_dose_uSv,
        compliance_status=result.compliance_status,
        required_room_scatter_caution=result.required_room_scatter_caution,
        provided_room_scatter_caution=result.provided_room_scatter_caution,
        required_source_model_extrapolation=result.required_source_model_extrapolation,
        practical_record_id=result.practical_record_id,
        practical_provenance=result.practical_provenance,
        required_scope_note=result.required_scope_note,
        provided_scope_note=result.provided_scope_note,
    )


def calculate_spect_tc99m_barrier_schedule(
    source: SpectSourceDomain,
    barrier_requests: Sequence[SpectBarrierScheduleRequest] = (),
    *,
    dataset: LoadedSpectPracticalDataset | None = None,
) -> SpectBarrierScheduleResult:
    """Calculate the deterministic Step 5 multi-barrier Tc-99m schedule.

    Caller order is preserved exactly and frozen into ``schedule_index``.  No
    geometry/UI barrier ordering is inferred at this headless boundary.
    """

    if not isinstance(source, SpectSourceDomain):
        raise SpectBarrierScheduleError(
            "source must be a validated SpectSourceDomain instance."
        )
    requests = _validate_requests(barrier_requests)
    practical_dataset = _load_dataset(dataset)

    try:
        source_physics = calculate_spect_weekly_dose_at_1m(source)
    except SpectContractError as exc:
        raise SpectBarrierScheduleError(str(exc)) from exc

    rows: list[SpectBarrierScheduleRow] = []
    for index, request in enumerate(requests):
        try:
            calculation = calculate_spect_tc99m_practical_barrier(
                source,
                request.to_calculation_request(),
                dataset=practical_dataset,
            )
        except SpectPracticalBarrierError as exc:
            raise SpectBarrierScheduleError(
                f"barrier_requests[{index}] ({request.barrier_id}): {exc}"
            ) from exc
        if calculation.adapter_status != SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS:
            raise SpectBarrierScheduleError(
                f"barrier_requests[{index}] returned unsupported Step 4 status "
                f"{calculation.adapter_status!r}."
            )
        if calculation.source_physics != source_physics:
            raise SpectBarrierScheduleError(
                f"barrier_requests[{index}] source physics does not match the schedule source."
            )
        rows.append(_row_from_result(index, request, calculation))

    row_tuple = tuple(rows)
    return SpectBarrierScheduleResult(
        contract_version=SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION,
        status=SPECT_BARRIER_SCHEDULE_STATUS,
        production_eligible=False,
        ordering_basis="caller_request_order",
        source_physics=source_physics,
        rows=row_tuple,
        pass_count=sum(row.compliance_status == "PASS" for row in row_tuple),
        fail_count=sum(row.compliance_status == "FAIL" for row in row_tuple),
        not_assessed_count=sum(
            row.compliance_status == "NOT_ASSESSED" for row in row_tuple
        ),
        requires_room_scatter_review=any(
            row.required_room_scatter_caution
            or row.provided_room_scatter_caution is True
            for row in row_tuple
        ),
        contains_source_model_extrapolation=any(
            row.required_source_model_extrapolation for row in row_tuple
        ),
    )
