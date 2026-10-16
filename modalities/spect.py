"""SPECT source-domain and controlled production-host physics boundary.



SPECT is admitted to the production host for durable working state, gated

Tc-99m production calculation, and in-app Results. The legacy generic source

calculator remains deliberately blocked, and issued PDF/export/certification

remain closed behind their dedicated output gates.



There is deliberately no separate uptake phase in the SPECT model.  The

activity supplied to this Step 1 source contract is the activity reference used

at the start of the modelled imaging/exposure interval, and physical decay is

integrated only across that interval.



CT components of hybrid SPECT/CT rooms remain the responsibility of the CT

modality/database.

"""



from __future__ import annotations



from dataclasses import dataclass

from math import exp, isfinite, log

from pathlib import Path

from typing import Any, Mapping



from engine.barrier_input_contract import BarrierSourceInput

from engine.isotropic_barrier_solver import (

    ISOTROPIC_NON_BEAM_SOLVER_MODE,

    IsotropicBarrierDesign,

    IsotropicBarrierGeometry,

    IsotropicBarrierSolverInput,

    IsotropicBarrierSolverResult,

    TvlAttenuationInput,

    solve_isotropic_non_beam_barrier,

)

from engine.spect_radionuclide_data import load_frozen_spect_radionuclide_dataset

from modalities.base import (

    DeclarativeModalityPlugin,

    GeometryUISpec,

    LayoutRenderSpec,

    ModalitySpec,

    ReportWordingSpec,

    SourceSpec,

)





SPECT_MODALITY_ID = "SPECT"

SPECT_SOURCE_TYPE = "spect_patient"

SPECT_CALCULATION_BLOCK_REASON = (

    "SPECT generic source calculation remains disabled; use the gated Step 26 production dispatch path."

)

SPECT_ISSUED_OUTPUT_BLOCK_REASON = (

    "SPECT production calculation and in-app Results are enabled, but issued PDF, machine export, "

    "certification, and signature workflows remain closed."

)

SPECT_PHYSICS_CONTRACT_VERSION = 1

SPECT_BARRIER_ADAPTER_CONTRACT_VERSION = 1

SPECT_RADIONUCLIDE_DATASET_PATH = (

    Path(__file__).resolve().parents[1]

    / "data"

    / "spect"

    / "spect_radionuclide_physics_approved_frozen.json"

)





class SpectContractError(ValueError):

    """Raised when a SPECT source-domain request is invalid."""





_SPECT_RADIONUCLIDE_DATASET = load_frozen_spect_radionuclide_dataset(

    SPECT_RADIONUCLIDE_DATASET_PATH

)

SPECT_RADIONUCLIDE_DATASET_METADATA = _SPECT_RADIONUCLIDE_DATASET.metadata

SPECT_RADIONUCLIDES = _SPECT_RADIONUCLIDE_DATASET.records





@dataclass(frozen=True)

class SpectSourceDomain:

    """Single-interval SPECT patient-source input contract.



    Step 1 intentionally has no uptake phase, uptake delay, voiding factor, or

    room-mode split.  ``imaging_duration_h`` is the only time interval included

    in the headless source workload calculation.

    """



    radionuclide: str

    administered_activity_mbq: float

    patients_per_week: float

    imaging_duration_h: float



    def __post_init__(self) -> None:

        radionuclide = str(self.radionuclide).strip()

        if radionuclide not in SPECT_RADIONUCLIDES:

            supported = ", ".join(SPECT_RADIONUCLIDES)

            raise SpectContractError(

                f"Unsupported SPECT radionuclide {radionuclide!r}; supported values: {supported}."

            )

        _require_positive("administered_activity_mbq", self.administered_activity_mbq)

        _require_positive("patients_per_week", self.patients_per_week)

        _require_positive("imaging_duration_h", self.imaging_duration_h)



    @property

    def radionuclide_spec(self):

        return SPECT_RADIONUCLIDES[str(self.radionuclide).strip()]





@dataclass(frozen=True)

class SpectPhysicsResult:

    """Deterministic Tc-99m source workload result at 1 m."""



    contract_version: int

    radionuclide: str

    radiation_type: str

    tvl_key: str

    administered_activity_mbq: float

    patients_per_week: float

    imaging_duration_h: float

    decay_integrated_hours: float

    weekly_dose_uSv_at_1m: float

    calculation_basis: str = "single_imaging_interval_decay_integrated_point_source_at_1m"





@dataclass(frozen=True)

class SpectBarrierCalculationResult:

    """SPECT-owned wrapper around one modality-neutral isotropic barrier solve."""



    adapter_contract_version: int

    solver_result: IsotropicBarrierSolverResult





def _require_positive(name: str, value: float) -> float:

    try:

        numeric = float(value)

    except (TypeError, ValueError) as exc:

        raise SpectContractError(f"{name} must be numeric.") from exc

    if not isfinite(numeric):

        raise SpectContractError(f"{name} must be finite.")

    if numeric <= 0.0:

        raise SpectContractError(f"{name} must be greater than zero.")

    return numeric





def spect_source_domain_from_params(params: Mapping[str, Any]) -> SpectSourceDomain:

    """Build the Step 1 SPECT source domain from serialisable values."""



    if not isinstance(params, Mapping):

        raise SpectContractError("SPECT source parameters must be a mapping.")

    try:

        return SpectSourceDomain(

            radionuclide=str(params.get("radionuclide", "")),

            administered_activity_mbq=float(params.get("administered_activity_mbq", 0.0)),

            patients_per_week=float(params.get("patients_per_week", 0.0)),

            imaging_duration_h=float(params.get("imaging_duration_h", 0.0)),

        )

    except (TypeError, ValueError) as exc:

        if isinstance(exc, SpectContractError):

            raise

        raise SpectContractError("SPECT source parameters contain a non-numeric value.") from exc





def calculate_spect_weekly_dose_at_1m(source: SpectSourceDomain) -> SpectPhysicsResult:

    """Calculate decay-integrated weekly SPECT patient dose at 1 m.



    No uptake interval is modelled.  Decay integration begins at the start of

    the SPECT imaging/exposure interval and runs for ``imaging_duration_h``.

    """



    if not isinstance(source, SpectSourceDomain):

        raise SpectContractError("source must be a validated SpectSourceDomain instance.")

    spec = source.radionuclide_spec

    decay_constant_h_inv = log(2.0) / float(spec.half_life_h)

    duration_h = float(source.imaging_duration_h)

    decay_integrated_hours = (1.0 - exp(-decay_constant_h_inv * duration_h)) / decay_constant_h_inv

    weekly_dose = (

        float(spec.dose_rate_constant_uSv_h_per_MBq_at_1m)

        * float(source.administered_activity_mbq)

        * float(source.patients_per_week)

        * decay_integrated_hours

    )

    return SpectPhysicsResult(

        contract_version=SPECT_PHYSICS_CONTRACT_VERSION,

        radionuclide=spec.code,

        radiation_type=spec.radiation_type,

        tvl_key=spec.tvl_key,

        administered_activity_mbq=float(source.administered_activity_mbq),

        patients_per_week=float(source.patients_per_week),

        imaging_duration_h=duration_h,

        decay_integrated_hours=decay_integrated_hours,

        weekly_dose_uSv_at_1m=weekly_dose,

    )





def spect_barrier_source_input(

    physics: SpectPhysicsResult,

    *,

    source_name: str = "SPECT Patient Source",

) -> BarrierSourceInput:

    """Adapt SPECT workload physics to the modality-neutral barrier contract."""



    if not isinstance(physics, SpectPhysicsResult):

        raise SpectContractError("physics must be a SpectPhysicsResult.")

    return BarrierSourceInput(

        source_name=source_name,

        source_type=SPECT_SOURCE_TYPE,

        radiation_type=physics.radiation_type,

        tvl_key=physics.tvl_key,

        weekly_dose_uSv_at_1m=physics.weekly_dose_uSv_at_1m,

        contribution_group="spect_patient",

        solver_mode=ISOTROPIC_NON_BEAM_SOLVER_MODE,

        distance_exponent=2.0,

        use_factor=1.0,

    )





def solve_spect_isotropic_barrier(

    physics: SpectPhysicsResult,

    *,

    attenuation: TvlAttenuationInput,

    distance_m: float,

    occupancy_factor: float,

    design_goal_uSv_per_week: float,

    provided_thickness_mm: float | None = None,

    source_name: str = "SPECT Patient Source",

) -> SpectBarrierCalculationResult:

    """Solve one headless SPECT barrier using caller-supplied attenuation data.



    Step 1 intentionally does not ship an approved SPECT attenuation library.

    The explicit attenuation argument keeps the physics and generic barrier

    boundary testable without silently promoting unverified material data.

    """



    if not isinstance(attenuation, TvlAttenuationInput):

        raise SpectContractError("attenuation must be a TvlAttenuationInput.")

    try:

        solved = solve_isotropic_non_beam_barrier(

            IsotropicBarrierSolverInput(

                source=spect_barrier_source_input(physics, source_name=source_name),

                geometry=IsotropicBarrierGeometry(distance_m=distance_m),

                design=IsotropicBarrierDesign(

                    design_goal_uSv_per_week=design_goal_uSv_per_week,

                    occupancy_factor=occupancy_factor,

                ),

                attenuation=attenuation,

                provided_thickness_mm=provided_thickness_mm,

            )

        )

    except ValueError as exc:

        raise SpectContractError(str(exc)) from exc

    return SpectBarrierCalculationResult(

        adapter_contract_version=SPECT_BARRIER_ADAPTER_CONTRACT_VERSION,

        solver_result=solved,

    )





def spect_source_readiness_result(

    source_type: str,

    params: Mapping[str, Any],

    context: Mapping[str, Any],

) -> dict[str, Any]:

    """Return Step 34 host readiness while preserving the issued-output hard gate.



    The generic source calculator remains deliberately blocked; production SPECT

    calculations must enter through the Step 26 dispatch boundary.  Normal room,

    working-project and in-app Results host paths are now enabled, while issued

    outputs remain explicitly blocked until a later gate opens them.

    """

    source_name = str(context.get("source_name", "SPECT patient source") or "SPECT patient source")

    room_name = str(context.get("room_name", "SPECT Room") or "SPECT Room")

    warning_text = f"{room_name}: {SPECT_ISSUED_OUTPUT_BLOCK_REASON}" if room_name else SPECT_ISSUED_OUTPUT_BLOCK_REASON

    return {

        "source_type": str(source_type or SPECT_SOURCE_TYPE),

        "source_name": source_name,

        "room_name": room_name,

        "overall_status": "REVIEW",

        "status": "REVIEW",

        "blocking": False,

        "output_blocking": True,

        "basis": "production_host_results_only",

        "message": SPECT_ISSUED_OUTPUT_BLOCK_REASON,

        "checks": [

            {

                "name": "SPECT production host integration",

                "status": "PASS",

                "detail": "Working-project persistence, gated production calculation, and in-app Results are enabled.",

            },

            {

                "name": "SPECT issued-output integration",

                "status": "REVIEW",

                "detail": SPECT_ISSUED_OUTPUT_BLOCK_REASON,

            },

        ],

        "errors": [],

        "warnings": [warning_text],

        "notes": [

            SPECT_CALCULATION_BLOCK_REASON,

            SPECT_ISSUED_OUTPUT_BLOCK_REASON,

        ],

    }







def spect_source_dose_rate_constant_display(source: SpectSourceDomain) -> str:
    """Return the approved radionuclide dose-rate constant as display text."""
    value = float(source.radionuclide_spec.dose_rate_constant_uSv_h_per_MBq_at_1m)
    return f"{value:g} µSv/h/MBq @ 1 m"


def _spect_geometry_live_source_params(room: Any) -> dict[str, Any]:
    from serialization.spect_working_project_state import get_room_spect_working_state

    state = get_room_spect_working_state(room)
    if state is None:
        return {}
    return {
        "radionuclide": state.source.radionuclide_spec.code,
        "administered_activity_mbq": float(state.source.administered_activity_mbq),
        "dose_rate_constant_uSv_h_per_MBq_at_1m": float(
            state.source.radionuclide_spec.dose_rate_constant_uSv_h_per_MBq_at_1m
        ),
    }


SPECT_MODALITY = ModalitySpec(

    modality_id=SPECT_MODALITY_ID,

    display_name="SPECT",

    production_enabled=True,

    default_room_name="SPECT Room 1",

    expected_sources=(

        SourceSpec(

            source_type=SPECT_SOURCE_TYPE,

            label="SPECT Patient Source",

            role="spect_patient",

            form_kind="spect_working_state",

            dose_model="spect_patient_production_dispatch",

            default_tvl_key="tc99m_140kev",

            contribution_group="spect_patient",

            ncrp_solver_mode="",

            validation_kind="production_host_results_only",

            readiness_labels={

                "source": "SPECT patient source",

                "not_implemented": "SPECT desktop calculation not implemented",

            },

            readiness_validator=spect_source_readiness_result,

            calculation_blocked_reason=SPECT_CALCULATION_BLOCK_REASON,

        ),

    ),

    geometry_live_source_params_builder=_spect_geometry_live_source_params,
    geometry_ui=GeometryUISpec(),
    layout_rendering=LayoutRenderSpec(

        source_symbol_kind="point_source",

        show_radiation_symbol=True,

        show_patient_symbol=True,

        patient_symbol_offset_m=0.0,

        patient_marker_label="",
        patient_label_offset_px=42.0,

        reference_circle_anchor="source",

        preview_overlay_kind="spect",

        show_barrier_status_text=False,

        render_param_keys=("radionuclide", "administered_activity_mbq"),

    ),

    classification="spect_production_host_controlled",

    default_energy_label="Tc-99m / radionuclide dependent",

    default_solver_mode="spect_tc99m_practical_archer",

    controlled_area_required=True,

    patient_radioactivity_present=True,

    xray_generator_present=False,

    hybrid_ct_present=False,

    compliance_only=False,

    notes=(

        "Controlled SPECT production-host integration: working-project persistence, gated Tc-99m "

        "production calculation, and in-app Results are enabled. Issued PDF/export/certification "

        "remain closed. CT components of hybrid SPECT/CT assessments continue to use the CT modality."

    ),

    report_wording=ReportWordingSpec(

        report_title="Preliminary SPECT Shielding Schedule",

        report_subtitle="Controlled SPECT production-host assessment — issued output remains disabled",

        cover_introduction=SPECT_CALCULATION_BLOCK_REASON,

        limitation_bullets=(

            SPECT_CALCULATION_BLOCK_REASON,

            "The legacy Step 1 generic source calculator is retained as a blocked historical substrate; production calculations use the gated Step 26 dispatch path.",

            "Use the CT modality for any CT or CTAC shielding component until a composite workflow is introduced.",

        ),

        methodology_rows=(("SPECT", "Tc-99m production calculation uses the gated Step 26 dispatch path; issued PDF/export/certification remain disabled."),),

        construction_shielding_height_mm=2100,

    ),

)





SPECT_PLUGIN = DeclarativeModalityPlugin(SPECT_MODALITY)

