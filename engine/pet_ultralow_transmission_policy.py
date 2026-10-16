"""Approved PET Step 39 ultralow-transmission report-acceptance policy.

This policy does not change PET shielding physics.  It classifies canonical
PET Results rows at the future issueable-report boundary.

The approved PET attenuation dataset is a reduced piecewise-TVL representation
of AAPM TG-108 broad-beam 511 keV transmission data rather than a direct
Archer-equation implementation.  RadShield therefore adopts a conservative
software-validation boundary: automatic issueable acceptance is not permitted
when the *required* transmission is at or below 0.01.  This 1% value is a
RadShield validation/reporting policy, not a claim that TG-108 defines a
physical 1% validity limit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Mapping

PET_ULTRALOW_TRANSMISSION_POLICY_VERSION = 1
PET_ULTRALOW_TRANSMISSION_POLICY_STATUS = "approved_locked"
PET_ULTRALOW_TRANSMISSION_THRESHOLD = 0.01
PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED = True
PET_ULTRALOW_TRANSMISSION_REVIEW_STATUS = "PHYSICIST_REVIEW_REQUIRED"
PET_ULTRALOW_TRANSMISSION_POLICY_BASIS = (
    "RadShield production-report validation boundary for the approved reduced TG-108 "
    "piecewise-TVL PET attenuation model: automatic issueable acceptance is blocked "
    "when required transmission B is at or below 0.01. This is a software-validation "
    "policy, not a TG-108 physical threshold."
)


class PetUltralowTransmissionPolicyError(ValueError):
    """Raised when a PET Results row cannot be classified safely."""


@dataclass(frozen=True)
class PetProductionBarrierPolicyDecision:
    barrier_name: str
    status: str
    automatic_assessment_allowed: bool
    production_transmitted_dose_reportable: bool
    decision_basis: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_number(row: Mapping[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise PetUltralowTransmissionPolicyError(f"PET Results field {key!r} must be numeric.") from exc
    if not isfinite(value):
        raise PetUltralowTransmissionPolicyError(f"PET Results field {key!r} must be finite.")
    return value


def _optional_finite_number(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetUltralowTransmissionPolicyError(f"PET Results field {key!r} must be numeric or null.") from exc
    if not isfinite(number):
        raise PetUltralowTransmissionPolicyError(f"PET Results field {key!r} must be finite.")
    return number


def assess_pet_production_barrier_policy(row: Mapping[str, Any]) -> PetProductionBarrierPolicyDecision:
    """Classify one canonical PET Results row for future issueable reporting.

    PASS/FAIL above the supported boundary is based on provided thickness versus
    required thickness.  A numerical transmitted dose at/below 1% provided
    transmission is never used as issueable acceptance evidence.
    """
    if not isinstance(row, Mapping):
        raise PetUltralowTransmissionPolicyError("row must be a mapping.")

    barrier_name = str(row.get("barrier_name", "") or "").strip()
    if not barrier_name:
        raise PetUltralowTransmissionPolicyError("PET Results barrier_name must not be blank.")

    required_transmission = _finite_number(row, "barrier_transmission_factor_B")
    required_thickness = _finite_number(row, "required_thickness_mm")
    if not 0.0 < required_transmission <= 1.0:
        raise PetUltralowTransmissionPolicyError("PET required transmission must be in (0, 1].")
    if required_thickness < 0.0:
        raise PetUltralowTransmissionPolicyError("PET required thickness must be non-negative.")

    if required_transmission <= PET_ULTRALOW_TRANSMISSION_THRESHOLD:
        return PetProductionBarrierPolicyDecision(
            barrier_name=barrier_name,
            status=PET_ULTRALOW_TRANSMISSION_REVIEW_STATUS,
            automatic_assessment_allowed=False,
            production_transmitted_dose_reportable=False,
            decision_basis=(
                "Required PET transmission B is at/below the approved 0.01 RadShield validation boundary; "
                "automatic issueable acceptance is blocked and physicist review is required."
            ),
        )

    provided_thickness = _optional_finite_number(row, "provided_thickness_mm")
    provided_transmission = _optional_finite_number(row, "provided_transmission")
    if provided_thickness is None:
        return PetProductionBarrierPolicyDecision(
            barrier_name=barrier_name,
            status="NOT_ASSESSED",
            automatic_assessment_allowed=True,
            production_transmitted_dose_reportable=False,
            decision_basis="No provided PET barrier thickness was supplied.",
        )
    if provided_thickness < 0.0:
        raise PetUltralowTransmissionPolicyError("PET provided thickness must be non-negative.")
    if provided_transmission is not None and not 0.0 < provided_transmission <= 1.0:
        raise PetUltralowTransmissionPolicyError("PET provided transmission must be in (0, 1].")

    status = "PASS" if provided_thickness >= required_thickness else "FAIL"
    reportable = (
        provided_transmission is not None
        and provided_transmission > PET_ULTRALOW_TRANSMISSION_THRESHOLD
    )
    return PetProductionBarrierPolicyDecision(
        barrier_name=barrier_name,
        status=status,
        automatic_assessment_allowed=True,
        production_transmitted_dose_reportable=reportable,
        decision_basis=(
            "PET production assessment is based on provided thickness versus required thickness above the "
            "0.01 required-transmission validation boundary. Any modeled dose associated with provided "
            "transmission at/below 0.01 is suppressed as issueable acceptance evidence."
        ),
    )
