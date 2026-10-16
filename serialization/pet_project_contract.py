"""Versioned PET project-domain serialization contract.

This module serializes the isolated PET source input, physics result, and
barrier-solver results into JSON-compatible dictionaries.  It is deliberately
separate from the production working-project schema, UI, calculation dispatch,
and report pipeline while PET remains a locked modality.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from engine.isotropic_barrier_solver import (
    ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
    ISOTROPIC_NON_BEAM_SOLVER_MODE,
    IsotropicBarrierSolverResult,
)
from modalities.pet import (
    PET_ATTENUATION_RADIATION_TYPE,
    PET_ATTENUATION_TVL_KEY,
    PET_BARRIER_ADAPTER_CONTRACT_VERSION,
    PET_PHYSICS_CONTRACT_VERSION,
    PET_SOURCE_TYPE,
    PetBarrierCalculationResult,
    PetExposurePhase,
    PetPhaseDoseResult,
    PetPhysicsResult,
    PetSourceDomain,
)


PET_PROJECT_SERIALIZATION_SCHEMA = "radshield_pet_project_domain_v2"
PET_PROJECT_SERIALIZATION_VERSION = 2


class PetProjectSerializationError(ValueError):
    """Raised when a PET project-domain payload violates the contract."""


@dataclass(frozen=True)
class PetProjectDomainSnapshot:
    """Validated serializable PET calculation snapshot.

    The snapshot is an isolated pre-production artifact.  It is not a
    ``models.shielding_models.Project`` and must not be passed to the working
    project serializer or report builder while PET remains non-production.
    """

    source: PetSourceDomain
    physics_result: PetPhysicsResult
    barrier_results: tuple[PetBarrierCalculationResult, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, PetSourceDomain):
            raise PetProjectSerializationError("source must be a PetSourceDomain.")
        if not isinstance(self.physics_result, PetPhysicsResult):
            raise PetProjectSerializationError(
                "physics_result must be a PetPhysicsResult."
            )
        if self.physics_result.radionuclide != self.source.radionuclide_spec.code:
            raise PetProjectSerializationError(
                "physics_result.radionuclide must match source.radionuclide."
            )
        if self.physics_result.radiation_type != PET_ATTENUATION_RADIATION_TYPE:
            raise PetProjectSerializationError(
                "physics_result has an invalid PET radiation_type."
            )
        if self.physics_result.tvl_key != PET_ATTENUATION_TVL_KEY:
            raise PetProjectSerializationError(
                "physics_result has an invalid PET tvl_key."
            )
        for result in self.barrier_results:
            if not isinstance(result, PetBarrierCalculationResult):
                raise PetProjectSerializationError(
                    "barrier_results must contain PetBarrierCalculationResult values."
                )
            solved = result.solver_result
            if not isinstance(solved, IsotropicBarrierSolverResult):
                raise PetProjectSerializationError(
                    "barrier result solver_result must be an IsotropicBarrierSolverResult."
                )
            if solved.source_type != PET_SOURCE_TYPE:
                raise PetProjectSerializationError(
                    "barrier result source_type must be 'pet_patient'."
                )
            if solved.radiation_type != self.physics_result.radiation_type:
                raise PetProjectSerializationError(
                    "barrier result radiation_type must match the PET physics result."
                )
            if solved.tvl_key != self.physics_result.tvl_key:
                raise PetProjectSerializationError(
                    "barrier result tvl_key must match the PET physics result."
                )


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetProjectSerializationError(f"{name} must be a mapping.")
    return value


def _sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PetProjectSerializationError(f"{name} must be a sequence.")
    return value


def _text(value: Any, name: str, *, allow_blank: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not allow_blank:
        raise PetProjectSerializationError(f"{name} must not be blank.")
    return text


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetProjectSerializationError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise PetProjectSerializationError(f"{name} must be finite.")
    return number


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise PetProjectSerializationError(f"{name} must be an integer.")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise PetProjectSerializationError(f"{name} must be an integer.") from exc
    if integer != value:
        raise PetProjectSerializationError(f"{name} must be an integer.")
    return integer


def _optional_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    return _number(value, name)


def _source_to_dict(source: PetSourceDomain) -> dict[str, Any]:
    return {
        "radionuclide": source.radionuclide_spec.code,
        "injected_activity_mbq": float(source.injected_activity_mbq),
        "patients_per_week": float(source.patients_per_week),
        "residual_activity_factor": float(source.residual_activity_factor),
        "exposure_phases": [
            {
                "name": phase.name,
                "start_time_h": float(phase.start_time_h),
                "duration_h": float(phase.duration_h),
                "activity_retention_factor": float(phase.activity_retention_factor),
            }
            for phase in source.exposure_phases
        ],
    }


def _source_from_dict(payload: Any) -> PetSourceDomain:
    data = _mapping(payload, "source")
    phases = []
    for index, item in enumerate(_sequence(data.get("exposure_phases"), "source.exposure_phases")):
        phase = _mapping(item, f"source.exposure_phases[{index}]")
        phases.append(
            PetExposurePhase(
                name=_text(phase.get("name"), f"source.exposure_phases[{index}].name"),
                start_time_h=_number(
                    phase.get("start_time_h"),
                    f"source.exposure_phases[{index}].start_time_h",
                ),
                duration_h=_number(
                    phase.get("duration_h"),
                    f"source.exposure_phases[{index}].duration_h",
                ),
                activity_retention_factor=_number(
                    phase.get("activity_retention_factor"),
                    f"source.exposure_phases[{index}].activity_retention_factor",
                ),
            )
        )
    return PetSourceDomain(
        radionuclide=_text(data.get("radionuclide"), "source.radionuclide"),
        injected_activity_mbq=_number(
            data.get("injected_activity_mbq"), "source.injected_activity_mbq"
        ),
        patients_per_week=_number(
            data.get("patients_per_week"), "source.patients_per_week"
        ),
        residual_activity_factor=_number(
            data.get("residual_activity_factor"),
            "source.residual_activity_factor",
        ),
        exposure_phases=tuple(phases),
    )


def _physics_to_dict(result: PetPhysicsResult) -> dict[str, Any]:
    return {
        "contract_version": int(result.contract_version),
        "radionuclide": result.radionuclide,
        "radiation_type": result.radiation_type,
        "tvl_key": result.tvl_key,
        "weekly_dose_uSv_at_1m": float(result.weekly_dose_uSv_at_1m),
        "calculation_basis": result.calculation_basis,
        "phase_results": [
            {
                "name": phase.name,
                "start_time_h": float(phase.start_time_h),
                "duration_h": float(phase.duration_h),
                "activity_retention_factor": float(phase.activity_retention_factor),
                "decay_integrated_hours": float(phase.decay_integrated_hours),
                "weekly_dose_uSv_at_1m": float(phase.weekly_dose_uSv_at_1m),
            }
            for phase in result.phase_results
        ],
    }


def _physics_from_dict(payload: Any) -> PetPhysicsResult:
    data = _mapping(payload, "physics_result")
    contract_version = _integer(
        data.get("contract_version"), "physics_result.contract_version"
    )
    if contract_version != PET_PHYSICS_CONTRACT_VERSION:
        raise PetProjectSerializationError(
            f"Unsupported PET physics contract version {contract_version!r}."
        )
    phase_results = []
    for index, item in enumerate(_sequence(data.get("phase_results"), "physics_result.phase_results")):
        phase = _mapping(item, f"physics_result.phase_results[{index}]")
        phase_results.append(
            PetPhaseDoseResult(
                name=_text(phase.get("name"), f"physics_result.phase_results[{index}].name"),
                start_time_h=_number(phase.get("start_time_h"), f"physics_result.phase_results[{index}].start_time_h"),
                duration_h=_number(phase.get("duration_h"), f"physics_result.phase_results[{index}].duration_h"),
                activity_retention_factor=_number(phase.get("activity_retention_factor"), f"physics_result.phase_results[{index}].activity_retention_factor"),
                decay_integrated_hours=_number(phase.get("decay_integrated_hours"), f"physics_result.phase_results[{index}].decay_integrated_hours"),
                weekly_dose_uSv_at_1m=_number(phase.get("weekly_dose_uSv_at_1m"), f"physics_result.phase_results[{index}].weekly_dose_uSv_at_1m"),
            )
        )
    result = PetPhysicsResult(
        contract_version=contract_version,
        radionuclide=_text(data.get("radionuclide"), "physics_result.radionuclide"),
        radiation_type=_text(data.get("radiation_type"), "physics_result.radiation_type"),
        tvl_key=_text(data.get("tvl_key"), "physics_result.tvl_key"),
        weekly_dose_uSv_at_1m=_number(data.get("weekly_dose_uSv_at_1m"), "physics_result.weekly_dose_uSv_at_1m"),
        phase_results=tuple(phase_results),
        calculation_basis=_text(data.get("calculation_basis"), "physics_result.calculation_basis"),
    )
    if result.radiation_type != PET_ATTENUATION_RADIATION_TYPE:
        raise PetProjectSerializationError("physics_result has an invalid PET radiation_type.")
    if result.tvl_key != PET_ATTENUATION_TVL_KEY:
        raise PetProjectSerializationError("physics_result has an invalid PET tvl_key.")
    return result


_SOLVER_FIELDS = (
    "contract_version", "solver_mode", "source_name", "source_type",
    "radiation_type", "tvl_key", "material_key", "attenuation_record_id",
    "attenuation_provenance", "distance_m", "occupancy_factor",
    "design_goal_uSv_per_week", "unshielded_weekly_dose_uSv_at_barrier",
    "occupied_unshielded_weekly_dose_uSv", "required_transmission",
    "required_tvl_count", "required_thickness_mm", "provided_thickness_mm",
    "provided_transmission", "transmitted_weekly_dose_uSv", "compliance_status",
)


def _barrier_to_dict(result: PetBarrierCalculationResult) -> dict[str, Any]:
    solved = result.solver_result
    return {
        "adapter_contract_version": PET_BARRIER_ADAPTER_CONTRACT_VERSION,
        "dataset": {
            "dataset_id": result.dataset_id,
            "dataset_revision": result.dataset_revision,
            "approved_by": result.approved_by,
            "approved_date": result.approved_date,
        },
        "solver_result": {field: getattr(solved, field) for field in _SOLVER_FIELDS},
    }


def _barrier_from_dict(payload: Any, index: int) -> PetBarrierCalculationResult:
    data = _mapping(payload, f"barrier_results[{index}]")
    adapter_version = _integer(
        data.get("adapter_contract_version"),
        f"barrier_results[{index}].adapter_contract_version",
    )
    if adapter_version != PET_BARRIER_ADAPTER_CONTRACT_VERSION:
        raise PetProjectSerializationError(
            f"Unsupported PET barrier adapter contract version {adapter_version!r}."
        )
    dataset = _mapping(data.get("dataset"), f"barrier_results[{index}].dataset")
    solved = _mapping(data.get("solver_result"), f"barrier_results[{index}].solver_result")
    solver_version = _integer(solved.get("contract_version"), f"barrier_results[{index}].solver_result.contract_version")
    if solver_version != ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION:
        raise PetProjectSerializationError(
            f"Unsupported isotropic solver contract version {solver_version!r}."
        )
    solver_mode = _text(solved.get("solver_mode"), f"barrier_results[{index}].solver_result.solver_mode")
    if solver_mode != ISOTROPIC_NON_BEAM_SOLVER_MODE:
        raise PetProjectSerializationError("PET barrier result has an invalid solver_mode.")
    source_type = _text(solved.get("source_type"), f"barrier_results[{index}].solver_result.source_type")
    if source_type != PET_SOURCE_TYPE:
        raise PetProjectSerializationError("PET barrier result has an invalid source_type.")
    result = IsotropicBarrierSolverResult(
        contract_version=solver_version,
        solver_mode=solver_mode,
        source_name=_text(solved.get("source_name"), f"barrier_results[{index}].solver_result.source_name"),
        source_type=source_type,
        radiation_type=_text(solved.get("radiation_type"), f"barrier_results[{index}].solver_result.radiation_type"),
        tvl_key=_text(solved.get("tvl_key"), f"barrier_results[{index}].solver_result.tvl_key"),
        material_key=_text(solved.get("material_key"), f"barrier_results[{index}].solver_result.material_key"),
        attenuation_record_id=_text(solved.get("attenuation_record_id"), f"barrier_results[{index}].solver_result.attenuation_record_id"),
        attenuation_provenance=_text(solved.get("attenuation_provenance"), f"barrier_results[{index}].solver_result.attenuation_provenance"),
        distance_m=_number(solved.get("distance_m"), f"barrier_results[{index}].solver_result.distance_m"),
        occupancy_factor=_number(solved.get("occupancy_factor"), f"barrier_results[{index}].solver_result.occupancy_factor"),
        design_goal_uSv_per_week=_number(solved.get("design_goal_uSv_per_week"), f"barrier_results[{index}].solver_result.design_goal_uSv_per_week"),
        unshielded_weekly_dose_uSv_at_barrier=_number(solved.get("unshielded_weekly_dose_uSv_at_barrier"), f"barrier_results[{index}].solver_result.unshielded_weekly_dose_uSv_at_barrier"),
        occupied_unshielded_weekly_dose_uSv=_number(solved.get("occupied_unshielded_weekly_dose_uSv"), f"barrier_results[{index}].solver_result.occupied_unshielded_weekly_dose_uSv"),
        required_transmission=_number(solved.get("required_transmission"), f"barrier_results[{index}].solver_result.required_transmission"),
        required_tvl_count=_number(solved.get("required_tvl_count"), f"barrier_results[{index}].solver_result.required_tvl_count"),
        required_thickness_mm=_number(solved.get("required_thickness_mm"), f"barrier_results[{index}].solver_result.required_thickness_mm"),
        provided_thickness_mm=_optional_number(solved.get("provided_thickness_mm"), f"barrier_results[{index}].solver_result.provided_thickness_mm"),
        provided_transmission=_optional_number(solved.get("provided_transmission"), f"barrier_results[{index}].solver_result.provided_transmission"),
        transmitted_weekly_dose_uSv=_optional_number(solved.get("transmitted_weekly_dose_uSv"), f"barrier_results[{index}].solver_result.transmitted_weekly_dose_uSv"),
        compliance_status=_text(solved.get("compliance_status"), f"barrier_results[{index}].solver_result.compliance_status"),
    )
    if result.radiation_type != PET_ATTENUATION_RADIATION_TYPE:
        raise PetProjectSerializationError("PET barrier result has an invalid radiation_type.")
    if result.tvl_key != PET_ATTENUATION_TVL_KEY:
        raise PetProjectSerializationError("PET barrier result has an invalid tvl_key.")
    return PetBarrierCalculationResult(
        dataset_id=_text(dataset.get("dataset_id"), f"barrier_results[{index}].dataset.dataset_id"),
        dataset_revision=_text(dataset.get("dataset_revision"), f"barrier_results[{index}].dataset.dataset_revision"),
        approved_by=_text(dataset.get("approved_by"), f"barrier_results[{index}].dataset.approved_by"),
        approved_date=_text(dataset.get("approved_date"), f"barrier_results[{index}].dataset.approved_date"),
        solver_result=result,
    )


def pet_project_snapshot_to_dict(snapshot: PetProjectDomainSnapshot) -> dict[str, Any]:
    """Return a JSON-compatible, versioned PET project-domain payload."""

    if not isinstance(snapshot, PetProjectDomainSnapshot):
        raise PetProjectSerializationError(
            "snapshot must be a PetProjectDomainSnapshot."
        )
    return {
        "schema": PET_PROJECT_SERIALIZATION_SCHEMA,
        "schema_version": PET_PROJECT_SERIALIZATION_VERSION,
        "production_eligible": False,
        "source": _source_to_dict(snapshot.source),
        "physics_result": _physics_to_dict(snapshot.physics_result),
        "barrier_results": [
            _barrier_to_dict(result) for result in snapshot.barrier_results
        ],
    }


def pet_project_snapshot_from_dict(payload: Any) -> PetProjectDomainSnapshot:
    """Validate and reconstruct a PET project-domain snapshot."""

    data = _mapping(payload, "PET project-domain payload")
    if _text(data.get("schema"), "schema") != PET_PROJECT_SERIALIZATION_SCHEMA:
        raise PetProjectSerializationError("Unsupported PET serialization schema.")
    version = _integer(data.get("schema_version"), "schema_version")
    if version != PET_PROJECT_SERIALIZATION_VERSION:
        raise PetProjectSerializationError(
            f"Unsupported PET serialization schema version {version!r}."
        )
    if data.get("production_eligible") is not False:
        raise PetProjectSerializationError(
            "PET project-domain payload must remain production_eligible=false."
        )
    source = _source_from_dict(data.get("source"))
    physics = _physics_from_dict(data.get("physics_result"))
    barriers = tuple(
        _barrier_from_dict(item, index)
        for index, item in enumerate(
            _sequence(data.get("barrier_results"), "barrier_results")
        )
    )
    return PetProjectDomainSnapshot(
        source=source,
        physics_result=physics,
        barrier_results=barriers,
    )
