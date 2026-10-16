"""Generic, UI-independent source input contract for barrier calculations.

This module defines the narrow boundary between a modality-owned workload
calculation and a future generic barrier solver.  It contains no modality
registry, UI, report, project-serialization, or production-dispatch logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


BARRIER_SOURCE_INPUT_CONTRACT_VERSION = 1


class BarrierInputContractError(ValueError):
    """Raised when a modality supplies invalid generic barrier-solver input."""


def _required_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise BarrierInputContractError(f"{name} must not be blank.")
    return text


def _finite_non_negative(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise BarrierInputContractError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise BarrierInputContractError(f"{name} must be finite.")
    if number < 0.0:
        raise BarrierInputContractError(f"{name} must be greater than or equal to zero.")
    return number


@dataclass(frozen=True)
class BarrierSourceInput:
    """Modality-neutral input supplied to a isotropic/non-beam barrier solver.

    ``weekly_dose_uSv_at_1m`` is the unshielded weekly ambient-dose-equivalent
    workload at the source reference distance of 1 m.  The isotropic/non-beam barrier
    solver may apply geometry, occupancy, design goal and material attenuation,
    but those barrier-specific values are intentionally outside this source
    contract.
    """

    source_name: str
    source_type: str
    radiation_type: str
    tvl_key: str
    weekly_dose_uSv_at_1m: float
    contribution_group: str
    solver_mode: str
    distance_exponent: float = 2.0
    use_factor: float = 1.0
    contract_version: int = BARRIER_SOURCE_INPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_name", _required_text("source_name", self.source_name))
        object.__setattr__(self, "source_type", _required_text("source_type", self.source_type))
        object.__setattr__(self, "radiation_type", _required_text("radiation_type", self.radiation_type))
        object.__setattr__(self, "tvl_key", _required_text("tvl_key", self.tvl_key))
        object.__setattr__(
            self,
            "contribution_group",
            _required_text("contribution_group", self.contribution_group),
        )
        object.__setattr__(self, "solver_mode", _required_text("solver_mode", self.solver_mode))
        object.__setattr__(
            self,
            "weekly_dose_uSv_at_1m",
            _finite_non_negative("weekly_dose_uSv_at_1m", self.weekly_dose_uSv_at_1m),
        )
        exponent = _finite_non_negative("distance_exponent", self.distance_exponent)
        if exponent <= 0.0:
            raise BarrierInputContractError("distance_exponent must be greater than zero.")
        object.__setattr__(self, "distance_exponent", exponent)
        use_factor = _finite_non_negative("use_factor", self.use_factor)
        if use_factor > 1.0:
            raise BarrierInputContractError("use_factor must be between 0 and 1 inclusive.")
        object.__setattr__(self, "use_factor", use_factor)
        if int(self.contract_version) != BARRIER_SOURCE_INPUT_CONTRACT_VERSION:
            raise BarrierInputContractError(
                "Unsupported barrier source input contract version "
                f"{self.contract_version!r}."
            )

    def weekly_dose_uSv_at_distance(self, distance_m: float) -> float:
        """Return the unshielded weekly dose at a positive source distance."""

        try:
            distance = float(distance_m)
        except (TypeError, ValueError) as exc:
            raise BarrierInputContractError("distance_m must be numeric.") from exc
        if not isfinite(distance):
            raise BarrierInputContractError("distance_m must be finite.")
        if distance <= 0.0:
            raise BarrierInputContractError("distance_m must be greater than zero.")
        return self.weekly_dose_uSv_at_1m / (distance ** self.distance_exponent)
