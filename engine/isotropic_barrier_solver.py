"""Pure contract and solver for isotropic, non-beam radiation sources.

This module is deliberately independent of CT scatter and X-ray primary-beam
solvers.  It accepts a modality-neutral ``BarrierSourceInput`` whose workload
has already been calculated at 1 m, then applies barrier geometry, occupancy,
design goal and TVL attenuation data.

The contract is suitable for PET patient sources and, later, SPECT patient or
administered-activity sources.  It contains no UI, modality registry, report,
project-serialization or production-dispatch logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log10

from engine.barrier_input_contract import BarrierInputContractError, BarrierSourceInput


ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION = 1
ISOTROPIC_NON_BEAM_SOLVER_MODE = "isotropic_non_beam_tvl"


class IsotropicBarrierSolverError(ValueError):
    """Raised when isotropic barrier-solver input violates the contract."""


def _finite(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IsotropicBarrierSolverError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise IsotropicBarrierSolverError(f"{name} must be finite.")
    return number


def _positive(name: str, value: float) -> float:
    number = _finite(name, value)
    if number <= 0.0:
        raise IsotropicBarrierSolverError(f"{name} must be greater than zero.")
    return number


def _unit_interval(name: str, value: float) -> float:
    number = _finite(name, value)
    if not 0.0 <= number <= 1.0:
        raise IsotropicBarrierSolverError(f"{name} must be between 0 and 1 inclusive.")
    return number


def _required_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise IsotropicBarrierSolverError(f"{name} must not be blank.")
    return text


@dataclass(frozen=True)
class IsotropicBarrierGeometry:
    """Source-to-assessment-point geometry for one barrier."""

    distance_m: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance_m", _positive("distance_m", self.distance_m))


@dataclass(frozen=True)
class IsotropicBarrierDesign:
    """Protection target applied at the occupied side of one barrier."""

    design_goal_uSv_per_week: float
    occupancy_factor: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "design_goal_uSv_per_week",
            _positive("design_goal_uSv_per_week", self.design_goal_uSv_per_week),
        )
        object.__setattr__(
            self,
            "occupancy_factor",
            _unit_interval("occupancy_factor", self.occupancy_factor),
        )


@dataclass(frozen=True)
class TvlAttenuationInput:
    """Material attenuation data for the source radiation/TVL identity.

    ``tvl1_mm`` applies to the first decade of attenuation. ``tvle_mm`` applies
    to each subsequent decade.  Equal values represent a single-TVL model.
    """

    material_key: str
    tvl_key: str
    tvl1_mm: float
    tvle_mm: float
    attenuation_record_id: str = ""
    attenuation_provenance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "material_key", _required_text("material_key", self.material_key))
        object.__setattr__(self, "tvl_key", _required_text("tvl_key", self.tvl_key))
        object.__setattr__(self, "tvl1_mm", _positive("tvl1_mm", self.tvl1_mm))
        object.__setattr__(self, "tvle_mm", _positive("tvle_mm", self.tvle_mm))
        object.__setattr__(self, "attenuation_record_id", str(self.attenuation_record_id or "").strip())
        object.__setattr__(self, "attenuation_provenance", str(self.attenuation_provenance or "").strip())
        if bool(self.attenuation_record_id) != bool(self.attenuation_provenance):
            raise IsotropicBarrierSolverError(
                "attenuation_record_id and attenuation_provenance must either both be supplied or both be blank."
            )


@dataclass(frozen=True)
class IsotropicBarrierSolverInput:
    """Complete input boundary for one isotropic/non-beam barrier solve."""

    source: BarrierSourceInput
    geometry: IsotropicBarrierGeometry
    design: IsotropicBarrierDesign
    attenuation: TvlAttenuationInput
    provided_thickness_mm: float | None = None
    contract_version: int = ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source, BarrierSourceInput):
            raise IsotropicBarrierSolverError("source must be a BarrierSourceInput.")
        if self.source.solver_mode != ISOTROPIC_NON_BEAM_SOLVER_MODE:
            raise IsotropicBarrierSolverError(
                "source.solver_mode must be 'isotropic_non_beam_tvl'."
            )
        if self.attenuation.tvl_key != self.source.tvl_key:
            raise IsotropicBarrierSolverError(
                "attenuation.tvl_key must match source.tvl_key."
            )
        if self.provided_thickness_mm is not None:
            thickness = _finite("provided_thickness_mm", self.provided_thickness_mm)
            if thickness < 0.0:
                raise IsotropicBarrierSolverError(
                    "provided_thickness_mm must be greater than or equal to zero."
                )
            object.__setattr__(self, "provided_thickness_mm", thickness)
        if int(self.contract_version) != ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION:
            raise IsotropicBarrierSolverError(
                "Unsupported isotropic barrier solver contract version "
                f"{self.contract_version!r}."
            )


@dataclass(frozen=True)
class IsotropicBarrierSolverResult:
    """Deterministic output for one isotropic/non-beam barrier solve."""

    contract_version: int
    solver_mode: str
    source_name: str
    source_type: str
    radiation_type: str
    tvl_key: str
    material_key: str
    attenuation_record_id: str
    attenuation_provenance: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    unshielded_weekly_dose_uSv_at_barrier: float
    occupied_unshielded_weekly_dose_uSv: float
    required_transmission: float
    required_tvl_count: float
    required_thickness_mm: float
    provided_thickness_mm: float | None
    provided_transmission: float | None
    transmitted_weekly_dose_uSv: float | None
    compliance_status: str


def _thickness_from_transmission(transmission: float, tvl1_mm: float, tvle_mm: float) -> float:
    if transmission >= 1.0:
        return 0.0
    tvl_count = -log10(transmission)
    if tvl_count <= 1.0:
        return tvl_count * tvl1_mm
    return tvl1_mm + (tvl_count - 1.0) * tvle_mm


def _transmission_from_thickness(thickness_mm: float, tvl1_mm: float, tvle_mm: float) -> float:
    if thickness_mm <= 0.0:
        return 1.0
    if thickness_mm <= tvl1_mm:
        tvl_count = thickness_mm / tvl1_mm
    else:
        tvl_count = 1.0 + (thickness_mm - tvl1_mm) / tvle_mm
    return 10.0 ** (-tvl_count)


def solve_isotropic_non_beam_barrier(
    solver_input: IsotropicBarrierSolverInput,
) -> IsotropicBarrierSolverResult:
    """Solve one TVL-based barrier for an isotropic/non-beam source.

    The source workload is first scaled from 1 m to the barrier assessment
    distance using the source-owned distance exponent.  Occupancy and use
    factor are then applied.  The required broad-beam transmission is capped at
    1.0, and TVL1/TVLe interpolation produces the required material thickness.
    """

    try:
        dose_at_barrier = solver_input.source.weekly_dose_uSv_at_distance(
            solver_input.geometry.distance_m
        )
    except BarrierInputContractError as exc:
        raise IsotropicBarrierSolverError(str(exc)) from exc

    occupied_unshielded = (
        dose_at_barrier
        * solver_input.source.use_factor
        * solver_input.design.occupancy_factor
    )

    if occupied_unshielded <= 0.0:
        required_transmission = 1.0
    else:
        required_transmission = min(
            1.0,
            solver_input.design.design_goal_uSv_per_week / occupied_unshielded,
        )

    required_tvl_count = max(0.0, -log10(required_transmission))
    required_thickness = _thickness_from_transmission(
        required_transmission,
        solver_input.attenuation.tvl1_mm,
        solver_input.attenuation.tvle_mm,
    )

    provided_transmission = None
    transmitted_weekly_dose = None
    compliance_status = "NOT_ASSESSED"
    if solver_input.provided_thickness_mm is not None:
        provided_transmission = _transmission_from_thickness(
            solver_input.provided_thickness_mm,
            solver_input.attenuation.tvl1_mm,
            solver_input.attenuation.tvle_mm,
        )
        transmitted_weekly_dose = occupied_unshielded * provided_transmission
        compliance_status = (
            "PASS"
            if transmitted_weekly_dose <= solver_input.design.design_goal_uSv_per_week
            else "FAIL"
        )

    return IsotropicBarrierSolverResult(
        contract_version=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
        solver_mode=ISOTROPIC_NON_BEAM_SOLVER_MODE,
        source_name=solver_input.source.source_name,
        source_type=solver_input.source.source_type,
        radiation_type=solver_input.source.radiation_type,
        tvl_key=solver_input.source.tvl_key,
        material_key=solver_input.attenuation.material_key,
        attenuation_record_id=solver_input.attenuation.attenuation_record_id,
        attenuation_provenance=solver_input.attenuation.attenuation_provenance,
        distance_m=solver_input.geometry.distance_m,
        occupancy_factor=solver_input.design.occupancy_factor,
        design_goal_uSv_per_week=solver_input.design.design_goal_uSv_per_week,
        unshielded_weekly_dose_uSv_at_barrier=dose_at_barrier,
        occupied_unshielded_weekly_dose_uSv=occupied_unshielded,
        required_transmission=required_transmission,
        required_tvl_count=required_tvl_count,
        required_thickness_mm=required_thickness,
        provided_thickness_mm=solver_input.provided_thickness_mm,
        provided_transmission=provided_transmission,
        transmitted_weekly_dose_uSv=transmitted_weekly_dose,
        compliance_status=compliance_status,
    )
