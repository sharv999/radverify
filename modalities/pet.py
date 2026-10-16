"""PET source-domain, physics, and controlled production-host contracts.

PET participates in the normal desktop host for working-project persistence,
gated replay-verified calculation, and in-app Results.  The legacy generic
source-calculation route remains deliberately blocked, and issued PDF, machine
export, certification, and signatures remain outside this controlled scope.

Any CT component of a PET/CT installation continues to be assessed through the
existing CT modality and CT scanner database until a composite workflow is
introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from math import exp, isfinite, log
from typing import Any, Mapping, Sequence

from engine.pet_radionuclide_data import load_production_pet_radionuclide_dataset
from engine.pet_calculation_input_provenance import (
    load_pet_calculation_input_provenance_manifest,
    validate_pet_calculation_input_provenance,
)
from engine.isotropic_barrier_solver import ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION

from modalities.base import (
    DeclarativeModalityPlugin,
    LayoutRenderSpec,
    ModalitySpec,
    ReportWordingSpec,
    SourceSpec,
)


PET_MODALITY_ID = "PET"
PET_SOURCE_TYPE = "pet_patient"
PET_CALCULATION_BLOCK_REASON = (
    "The legacy generic PET source-calculation route is disabled. "
    "Production PET calculations must use the dedicated replay-verified PET dispatch boundary."
)
PET_ISSUED_OUTPUT_BLOCK_REASON = (
    "PET working-project persistence, gated production calculation, and in-app Results are enabled; "
    "issued PDF, machine export, certification, and signatures remain disabled."
)
PET_PHYSICS_CONTRACT_VERSION = 2
PET_BARRIER_ADAPTER_CONTRACT_VERSION = 1
PET_ATTENUATION_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "pet"
    / "pet_511kev_attenuation_production_approved.json"
)
PET_ATTENUATION_TVL_KEY = "pet_511kev"
PET_ATTENUATION_RADIATION_TYPE = "annihilation_511kev"
PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "pet"
    / "pet_calculation_input_provenance_manifest.json"
)
PET_RADIONUCLIDE_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "pet"
    / "pet_radionuclide_physics_approved.json"
)


class PetContractError(ValueError):
    """Raised when pre-production PET source inputs violate the contract."""


@dataclass(frozen=True)
class PetRadionuclide:
    """Immutable physics data required by the PET patient-source calculator."""

    code: str
    display_name: str
    half_life_h: float
    dose_rate_constant_uSv_h_per_MBq_at_1m: float
    radiation_type: str
    tvl_key: str
    half_life_provenance: Any
    dose_rate_provenance: Any


_PET_RADIONUCLIDE_DATASET = load_production_pet_radionuclide_dataset(PET_RADIONUCLIDE_DATASET_PATH)
PET_RADIONUCLIDE_DATASET_METADATA = _PET_RADIONUCLIDE_DATASET.metadata
PET_RADIONUCLIDES: Mapping[str, PetRadionuclide] = {
    code: PetRadionuclide(
        code=record.code,
        display_name=record.display_name,
        half_life_h=record.half_life_h,
        dose_rate_constant_uSv_h_per_MBq_at_1m=record.dose_rate_constant_uSv_h_per_MBq_at_1m,
        radiation_type=record.radiation_type,
        tvl_key=record.tvl_key,
        half_life_provenance=record.half_life_provenance,
        dose_rate_provenance=record.dose_rate_provenance,
    )
    for code, record in _PET_RADIONUCLIDE_DATASET.records.items()
}

PET_CALCULATION_INPUT_PROVENANCE_MANIFEST = load_pet_calculation_input_provenance_manifest(
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
)


@dataclass(frozen=True)
class PetExposurePhase:
    """One patient-location phase contributing to a barrier workload.

    ``start_time_h`` is measured from administration, so physical decay before
    the phase begins is included automatically. ``duration_h`` is the time spent
    in the phase. ``activity_retention_factor`` is an additional biological or
    procedural activity-retention multiplier applied to that phase (for example,
    0.85 after voiding) and must be in the interval (0, 1].
    """

    name: str
    start_time_h: float
    duration_h: float
    activity_retention_factor: float = 1.0

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise PetContractError("PET exposure phase name must not be blank.")
        _require_non_negative("start_time_h", self.start_time_h)
        _require_positive("duration_h", self.duration_h)
        if not 0.0 < float(self.activity_retention_factor) <= 1.0:
            raise PetContractError("activity_retention_factor must be greater than 0 and less than or equal to 1.")


@dataclass(frozen=True)
class PetSourceDomain:
    """Validated pre-production PET patient-source input contract."""

    radionuclide: str
    injected_activity_mbq: float
    patients_per_week: float
    exposure_phases: tuple[PetExposurePhase, ...]
    residual_activity_factor: float = 1.0

    def __post_init__(self) -> None:
        radionuclide = str(self.radionuclide).strip()
        if radionuclide not in PET_RADIONUCLIDES:
            supported = ", ".join(PET_RADIONUCLIDES)
            raise PetContractError(
                f"Unsupported PET radionuclide {radionuclide!r}; supported values: {supported}."
            )
        _require_positive("injected_activity_mbq", self.injected_activity_mbq)
        _require_positive("patients_per_week", self.patients_per_week)
        if not self.exposure_phases:
            raise PetContractError("At least one PET exposure phase is required.")
        if not 0.0 < float(self.residual_activity_factor) <= 1.0:
            raise PetContractError(
                "residual_activity_factor must be greater than 0 and less than or equal to 1."
            )
        names = [phase.name.strip().casefold() for phase in self.exposure_phases]
        if len(names) != len(set(names)):
            raise PetContractError("PET exposure phase names must be unique.")
        ordered = sorted(self.exposure_phases, key=lambda item: float(item.start_time_h))
        if tuple(ordered) != tuple(self.exposure_phases):
            raise PetContractError("PET exposure phases must be ordered by start time.")
        for previous, current in zip(ordered, ordered[1:]):
            previous_end = float(previous.start_time_h) + float(previous.duration_h)
            if float(current.start_time_h) < previous_end:
                raise PetContractError("PET exposure phases must not overlap.")

    @property
    def radionuclide_spec(self) -> PetRadionuclide:
        return PET_RADIONUCLIDES[str(self.radionuclide).strip()]


@dataclass(frozen=True)
class PetPhaseDoseResult:
    name: str
    start_time_h: float
    duration_h: float
    activity_retention_factor: float
    decay_integrated_hours: float
    weekly_dose_uSv_at_1m: float


@dataclass(frozen=True)
class PetPhysicsResult:
    """Deterministic output contract for the PET unshielded workload model."""

    contract_version: int
    radionuclide: str
    radiation_type: str
    tvl_key: str
    weekly_dose_uSv_at_1m: float
    phase_results: tuple[PetPhaseDoseResult, ...]
    calculation_basis: str = "decay_integrated_point_source_at_1m"


def _require_non_negative(name: str, value: float) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PetContractError(f"{name} must be numeric.") from exc
    if not isfinite(numeric):
        raise PetContractError(f"{name} must be finite.")
    if numeric < 0.0:
        raise PetContractError(f"{name} must be greater than or equal to zero.")


def _require_positive(name: str, value: float) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PetContractError(f"{name} must be numeric.") from exc
    if not isfinite(numeric):
        raise PetContractError(f"{name} must be finite.")
    if numeric <= 0.0:
        raise PetContractError(f"{name} must be greater than zero.")


def pet_source_domain_from_params(params: Mapping[str, Any]) -> PetSourceDomain:
    """Build and validate the PET source-domain contract from serialisable data."""

    phase_payloads = params.get("exposure_phases", ())
    if isinstance(phase_payloads, (str, bytes)) or not isinstance(phase_payloads, Sequence):
        raise PetContractError("exposure_phases must be a sequence of phase mappings.")

    phases: list[PetExposurePhase] = []
    for index, payload in enumerate(phase_payloads):
        if not isinstance(payload, Mapping):
            raise PetContractError(f"exposure_phases[{index}] must be a mapping.")
        try:
            phases.append(
                PetExposurePhase(
                    name=str(payload.get("name", "")),
                    start_time_h=float(payload.get("start_time_h", 0.0)),
                    duration_h=float(payload.get("duration_h", 0.0)),
                    activity_retention_factor=float(payload.get("activity_retention_factor", 1.0)),
                )
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, PetContractError):
                raise
            raise PetContractError(f"exposure_phases[{index}] contains a non-numeric value.") from exc

    try:
        return PetSourceDomain(
            radionuclide=str(params.get("radionuclide", "")),
            injected_activity_mbq=float(params.get("injected_activity_mbq", 0.0)),
            patients_per_week=float(params.get("patients_per_week", 0.0)),
            residual_activity_factor=float(params.get("residual_activity_factor", 1.0)),
            exposure_phases=tuple(phases),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, PetContractError):
            raise
        raise PetContractError("PET source parameters contain a non-numeric value.") from exc


def calculate_pet_decay_factor_at_time(half_life_h: float, time_after_administration_h: float) -> float:
    """Return the physical-decay fraction remaining at an absolute time after administration.

    This is the phase-start decay factor only. It does not include biological
    clearance/voiding and is separate from the decay integral over a phase
    duration.
    """

    _require_positive("half_life_h", half_life_h)
    _require_non_negative("time_after_administration_h", time_after_administration_h)
    decay_constant_h_inv = log(2.0) / float(half_life_h)
    return exp(-decay_constant_h_inv * float(time_after_administration_h))


def _decay_integrated_hours(half_life_h: float, start_time_h: float, duration_h: float) -> float:
    """Return the exact integral of physical-decay fraction over one phase."""

    if duration_h == 0.0:
        return 0.0
    decay_constant_h_inv = log(2.0) / half_life_h
    phase_start_fraction = exp(-decay_constant_h_inv * start_time_h)
    phase_end_fraction = exp(-decay_constant_h_inv * (start_time_h + duration_h))
    return (phase_start_fraction - phase_end_fraction) / decay_constant_h_inv


def calculate_pet_weekly_dose_at_1m(source: PetSourceDomain) -> PetPhysicsResult:
    """Calculate unshielded PET weekly dose at 1 m for the validated source.

    This deliberately stops at the source workload boundary.  It does not solve
    barrier transmission or thickness and is not connected to production
    calculation dispatch.
    """

    radionuclide = source.radionuclide_spec
    phase_results: list[PetPhaseDoseResult] = []
    total_weekly_dose = 0.0

    for phase in source.exposure_phases:
        integrated_h = _decay_integrated_hours(
            radionuclide.half_life_h,
            float(phase.start_time_h),
            float(phase.duration_h),
        )
        weekly_dose = (
            radionuclide.dose_rate_constant_uSv_h_per_MBq_at_1m
            * float(source.injected_activity_mbq)
            * float(source.residual_activity_factor)
            * float(source.patients_per_week)
            * float(phase.activity_retention_factor)
            * integrated_h
        )
        total_weekly_dose += weekly_dose
        phase_results.append(
            PetPhaseDoseResult(
                name=phase.name,
                start_time_h=float(phase.start_time_h),
                duration_h=float(phase.duration_h),
                activity_retention_factor=float(phase.activity_retention_factor),
                decay_integrated_hours=integrated_h,
                weekly_dose_uSv_at_1m=weekly_dose,
            )
        )

    return PetPhysicsResult(
        contract_version=PET_PHYSICS_CONTRACT_VERSION,
        radionuclide=radionuclide.code,
        radiation_type=radionuclide.radiation_type,
        tvl_key=radionuclide.tvl_key,
        weekly_dose_uSv_at_1m=total_weekly_dose,
        phase_results=tuple(phase_results),
    )



def pet_physics_result_to_barrier_source_input(
    result: PetPhysicsResult,
    *,
    source_name: str = "PET Patient Source",
):
    """Translate PET workload output into the generic barrier-source contract.

    This is a pre-production adapter only.  It does not register a PET dose
    model, call the production shielding engine, solve material thickness, or
    make PET eligible for report generation.
    """

    from engine.barrier_input_contract import BarrierSourceInput

    if int(result.contract_version) != PET_PHYSICS_CONTRACT_VERSION:
        raise PetContractError(
            f"Unsupported PET physics contract version {result.contract_version!r}."
        )

    return BarrierSourceInput(
        source_name=source_name,
        source_type=PET_SOURCE_TYPE,
        radiation_type=result.radiation_type,
        tvl_key=result.tvl_key,
        weekly_dose_uSv_at_1m=result.weekly_dose_uSv_at_1m,
        contribution_group="pet_patient",
        solver_mode="isotropic_non_beam_tvl",
        distance_exponent=2.0,
        use_factor=1.0,
    )


@dataclass(frozen=True)
class PetBarrierCalculationResult:
    """Auditable pre-production PET barrier result.

    The wrapper preserves the approved dataset identity and sign-off metadata
    alongside the generic isotropic solver result.  It is intentionally not
    consumed by the UI, project schema, production dispatch, or reports.
    """

    dataset_id: str
    dataset_revision: str
    approved_by: str
    approved_date: str
    solver_result: object


def load_pet_approved_attenuation_dataset():
    """Load the production-approved PET 511 keV dataset, fail closed.

    The path and loader are owned by the PET modality boundary.  No
    ``allow_unapproved`` escape hatch is exposed here.
    """

    from engine.material_attenuation_data import load_material_attenuation_dataset

    dataset = load_material_attenuation_dataset(PET_ATTENUATION_DATASET_PATH)
    if not dataset.metadata.production_approved:
        raise PetContractError("PET attenuation dataset is not production approved.")
    try:
        validate_pet_calculation_input_provenance(
            PET_CALCULATION_INPUT_PROVENANCE_MANIFEST,
            radionuclide_dataset=_PET_RADIONUCLIDE_DATASET,
            attenuation_dataset=dataset,
            attenuation_dataset_path=PET_ATTENUATION_DATASET_PATH,
            physics_contract_version=PET_PHYSICS_CONTRACT_VERSION,
            solver_contract_version=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
        )
    except ValueError as exc:
        raise PetContractError(str(exc)) from exc
    return dataset


def resolve_pet_attenuation_record(
    result: PetPhysicsResult,
    *,
    material_key: str,
):
    """Resolve one approved 511 keV attenuation record for a PET result."""

    from engine.material_attenuation_data import MaterialAttenuationDataError

    if int(result.contract_version) != PET_PHYSICS_CONTRACT_VERSION:
        raise PetContractError(
            f"Unsupported PET physics contract version {result.contract_version!r}."
        )
    if result.tvl_key != PET_ATTENUATION_TVL_KEY:
        raise PetContractError(
            f"PET physics result tvl_key must be {PET_ATTENUATION_TVL_KEY!r}."
        )
    if result.radiation_type != PET_ATTENUATION_RADIATION_TYPE:
        raise PetContractError(
            "PET physics result radiation_type must be "
            f"{PET_ATTENUATION_RADIATION_TYPE!r}."
        )

    dataset = load_pet_approved_attenuation_dataset()
    try:
        record = dataset.library.lookup(
            tvl_key=result.tvl_key,
            material_key=material_key,
            radiation_type=result.radiation_type,
        )
    except MaterialAttenuationDataError as exc:
        raise PetContractError(str(exc)) from exc
    if record.radionuclides and result.radionuclide not in record.radionuclides:
        raise PetContractError(
            f"Attenuation record {record.record_id!r} does not apply to "
            f"PET radionuclide {result.radionuclide!r}."
        )
    return dataset, record


def build_pet_isotropic_barrier_solver_input(
    result: PetPhysicsResult,
    *,
    material_key: str,
    distance_m: float,
    occupancy_factor: float,
    design_goal_uSv_per_week: float,
    provided_thickness_mm: float | None = None,
    source_name: str = "PET Patient Source",
):
    """Build generic solver input using only the approved PET dataset."""

    from engine.isotropic_barrier_solver import (
        IsotropicBarrierDesign,
        IsotropicBarrierGeometry,
        IsotropicBarrierSolverInput,
    )
    from engine.material_attenuation_data import attenuation_record_to_solver_input

    _dataset, record = resolve_pet_attenuation_record(
        result, material_key=material_key
    )
    return IsotropicBarrierSolverInput(
        source=pet_physics_result_to_barrier_source_input(
            result, source_name=source_name
        ),
        geometry=IsotropicBarrierGeometry(distance_m=distance_m),
        design=IsotropicBarrierDesign(
            design_goal_uSv_per_week=design_goal_uSv_per_week,
            occupancy_factor=occupancy_factor,
        ),
        attenuation=attenuation_record_to_solver_input(record),
        provided_thickness_mm=provided_thickness_mm,
    )


def solve_pet_isotropic_barrier(
    result: PetPhysicsResult,
    *,
    material_key: str,
    distance_m: float,
    occupancy_factor: float,
    design_goal_uSv_per_week: float,
    provided_thickness_mm: float | None = None,
    source_name: str = "PET Patient Source",
) -> PetBarrierCalculationResult:
    """Run the isolated PET-to-generic-solver path with audit metadata.

    This function is a modality-boundary contract only.  It is not registered
    with the production shielding engine and is not reachable from the UI or
    report pipeline.
    """

    from engine.isotropic_barrier_solver import solve_isotropic_non_beam_barrier

    dataset, _record = resolve_pet_attenuation_record(
        result, material_key=material_key
    )
    solver_input = build_pet_isotropic_barrier_solver_input(
        result,
        material_key=material_key,
        distance_m=distance_m,
        occupancy_factor=occupancy_factor,
        design_goal_uSv_per_week=design_goal_uSv_per_week,
        provided_thickness_mm=provided_thickness_mm,
        source_name=source_name,
    )
    return PetBarrierCalculationResult(
        dataset_id=dataset.metadata.dataset_id,
        dataset_revision=dataset.metadata.revision,
        approved_by=dataset.metadata.approved_by,
        approved_date=dataset.metadata.approved_date,
        solver_result=solve_isotropic_non_beam_barrier(solver_input),
    )

def pet_source_readiness_result(
    source_type: str,
    source_params: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return controlled production-host readiness while keeping issued output closed."""

    del source_params
    source_name = str(context.get("source_name", "PET Patient Source") or "PET Patient Source")
    room_name = str(context.get("room_name", "PET Room") or "PET Room")
    warning_text = (
        f"{room_name}: {PET_ISSUED_OUTPUT_BLOCK_REASON}"
        if room_name
        else PET_ISSUED_OUTPUT_BLOCK_REASON
    )
    return {
        "source_type": str(source_type or PET_SOURCE_TYPE),
        "source_name": source_name,
        "room_name": room_name,
        "overall_status": "REVIEW",
        "status": "REVIEW",
        "blocking": False,
        "output_blocking": True,
        "basis": "production_host_results_only",
        "message": PET_ISSUED_OUTPUT_BLOCK_REASON,
        "checks": [
            {
                "name": "PET production host integration",
                "status": "PASS",
                "detail": "Working-project persistence, gated production calculation, and in-app Results are enabled.",
            },
            {
                "name": "PET issued-output integration",
                "status": "REVIEW",
                "detail": PET_ISSUED_OUTPUT_BLOCK_REASON,
            },
        ],
        "errors": [],
        "warnings": [warning_text],
        "notes": [
            PET_CALCULATION_BLOCK_REASON,
            PET_ISSUED_OUTPUT_BLOCK_REASON,
        ],
    }


def _pet_geometry_live_source_params(room: Any) -> dict[str, Any]:
    from serialization.pet_working_project_state import get_room_pet_working_state

    state = get_room_pet_working_state(room)
    if state is None:
        return {}
    return {
        "radionuclide": state.source.radionuclide_spec.code,
        "injected_activity_mbq": float(state.source.injected_activity_mbq),
    }


PET_MODALITY = ModalitySpec(
    modality_id=PET_MODALITY_ID,
    display_name="PET",
    production_enabled=True,
    default_room_name="PET Room 1",
    expected_sources=(
        SourceSpec(
            source_type=PET_SOURCE_TYPE,
            label="PET Patient Source",
            role="pet_patient",
            form_kind="pet_working_state",
            dose_model="pet_patient_production_dispatch",
            default_tvl_key=PET_ATTENUATION_TVL_KEY,
            contribution_group="pet_patient",
            ncrp_solver_mode="",
            validation_kind="production_host_results_only",
            readiness_labels={
                "source": "PET patient source",
                "not_implemented": "PET calculation not implemented",
            },
            readiness_validator=pet_source_readiness_result,
            calculation_blocked_reason=PET_CALCULATION_BLOCK_REASON,
        ),
    ),
    geometry_live_source_params_builder=_pet_geometry_live_source_params,
    layout_rendering=LayoutRenderSpec(
        source_symbol_kind="point_source",
        show_radiation_symbol=True,
        show_patient_symbol=True,
        patient_symbol_offset_m=0.0,
        patient_marker_label="",
        patient_label_offset_px=42.0,
        reference_circle_anchor="source",
        preview_overlay_kind="pet",
        show_barrier_status_text=False,
        render_param_keys=("radionuclide", "injected_activity_mbq"),
    ),
    classification="pet_production_host_controlled",
    default_energy_label="511 keV annihilation photons",
    default_solver_mode="pet_replay_verified_dispatch",
    controlled_area_required=True,
    patient_radioactivity_present=True,
    xray_generator_present=False,
    hybrid_ct_present=False,
    compliance_only=False,
    notes=(
        "Controlled PET production-host integration: working-project persistence, gated replay-verified "
        "production calculation, and in-app Results are enabled. Issued PDF/export/certification remain "
        "closed. CT components of hybrid PET/CT assessments continue to use the CT modality."
    ),
    report_wording=ReportWordingSpec(
        report_title="Preliminary PET Shielding Schedule",
        report_subtitle="Controlled PET production-host assessment — issued output remains disabled",
        cover_introduction=PET_ISSUED_OUTPUT_BLOCK_REASON,
        methodology_rows=(("PET", "Production PET calculation uses the dedicated replay-verified dispatch path; issued PDF/export/certification remain disabled."),),
        construction_shielding_height_mm=2100,
        limitation_bullets=(
            PET_CALCULATION_BLOCK_REASON,
            "The legacy generic PET source calculator remains blocked; production calculations use the dedicated replay-verified dispatch path.",
            "Use the CT modality for any PET/CT CT shielding component until a composite workflow is introduced.",
        ),
    ),
)


PET_PLUGIN = DeclarativeModalityPlugin(PET_MODALITY)
