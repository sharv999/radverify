"""Approved SPECT Step 25 low-transmission production policy.

This module resolves the Step 24 production-policy blocker without enabling
SPECT production dispatch.  It classifies already-calculated Step 5 schedule
rows for future production use.  No attenuation or dose physics is performed
here.

Policy basis (Oumano et al., JACMP 2025): ceiling/floor scatter becomes
increasingly important as transmission approaches 1% and dominates below that
region, so the one-dimensional Archer barrier curve must not be used to claim
arbitrarily low total room dose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.spect_barrier_schedule import SpectBarrierScheduleResult, SpectBarrierScheduleRow

SPECT_LOW_TRANSMISSION_POLICY_VERSION = 1
SPECT_LOW_TRANSMISSION_POLICY_STATUS = "approved_locked"
SPECT_LOW_TRANSMISSION_THRESHOLD = 0.01
SPECT_LOW_TRANSMISSION_POLICY_APPROVED = True
SPECT_LOW_TRANSMISSION_REVIEW_STATUS = "ENGINEERING_REVIEW_REQUIRED"
SPECT_LOW_TRANSMISSION_POLICY_BASIS = (
    "Oumano et al., J Appl Clin Med Phys. 2025;26(5):e70084, reports that ceiling/floor "
    "scatter increasingly contributes as barrier transmission decreases and dominates below "
    "about 0.01; automatic production sizing/acceptance is therefore not permitted when the "
    "required transmission is at or below 0.01."
)


@dataclass(frozen=True)
class SpectProductionBarrierPolicyDecision:
    barrier_id: str
    barrier_name: str
    status: str
    automatic_assessment_allowed: bool
    production_transmitted_dose_reportable: bool
    decision_basis: str


@dataclass(frozen=True)
class SpectLowTransmissionPolicyAssessment:
    policy_version: int
    policy_status: str
    threshold: float
    approved: bool
    automatic_production_assessment_allowed: bool
    review_required_count: int
    decisions: tuple[SpectProductionBarrierPolicyDecision, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "policy_status": self.policy_status,
            "threshold": self.threshold,
            "approved": self.approved,
            "automatic_production_assessment_allowed": self.automatic_production_assessment_allowed,
            "review_required_count": self.review_required_count,
            "decisions": [
                {
                    "barrier_id": d.barrier_id,
                    "barrier_name": d.barrier_name,
                    "status": d.status,
                    "automatic_assessment_allowed": d.automatic_assessment_allowed,
                    "production_transmitted_dose_reportable": d.production_transmitted_dose_reportable,
                    "decision_basis": d.decision_basis,
                }
                for d in self.decisions
            ],
        }


def assess_spect_production_barrier_policy(
    row: SpectBarrierScheduleRow,
) -> SpectProductionBarrierPolicyDecision:
    """Classify one Step 5 row under the approved Step 25 production policy.

    The function intentionally does not use ``transmitted_weekly_dose_uSv`` to
    decide PASS/FAIL.  Above the 1% required-transmission boundary, an installed
    barrier is assessed by comparing provided thickness with the required
    thickness calculated in the supported region.  If the *provided* Archer
    transmission falls to <=1%, that low numerical dose prediction is not
    reportable as production evidence, even though the thickness comparison
    remains valid.
    """

    if not isinstance(row, SpectBarrierScheduleRow):
        raise TypeError("row must be a SpectBarrierScheduleRow.")

    if (
        row.required_transmission <= SPECT_LOW_TRANSMISSION_THRESHOLD
        or row.required_source_model_extrapolation
    ):
        return SpectProductionBarrierPolicyDecision(
            barrier_id=row.barrier_id,
            barrier_name=row.barrier_name,
            status=SPECT_LOW_TRANSMISSION_REVIEW_STATUS,
            automatic_assessment_allowed=False,
            production_transmitted_dose_reportable=False,
            decision_basis=(
                "Required transmission is at/below 0.01 (or outside the supported source-model range); "
                "automatic production sizing/acceptance is blocked and a geometry-specific scatter assessment is required."
            ),
        )

    if row.provided_thickness_mm is None:
        return SpectProductionBarrierPolicyDecision(
            barrier_id=row.barrier_id,
            barrier_name=row.barrier_name,
            status="NOT_ASSESSED",
            automatic_assessment_allowed=True,
            production_transmitted_dose_reportable=False,
            decision_basis="No provided barrier thickness was supplied.",
        )

    status = "PASS" if row.provided_thickness_mm >= row.required_thickness_mm else "FAIL"
    reportable = not (
        row.provided_room_scatter_caution is True
        or (
            row.provided_transmission is not None
            and row.provided_transmission <= SPECT_LOW_TRANSMISSION_THRESHOLD
        )
    )
    return SpectProductionBarrierPolicyDecision(
        barrier_id=row.barrier_id,
        barrier_name=row.barrier_name,
        status=status,
        automatic_assessment_allowed=True,
        production_transmitted_dose_reportable=reportable,
        decision_basis=(
            "Production PASS/FAIL is based on provided thickness versus required thickness calculated above the 1% "
            "required-transmission boundary. Low modeled provided-transmission dose, if any, is not used as acceptance evidence."
        ),
    )


def assess_spect_low_transmission_policy(
    schedule: SpectBarrierScheduleResult,
) -> SpectLowTransmissionPolicyAssessment:
    """Apply the Step 25 policy to a complete deterministic Step 5 schedule."""

    if not isinstance(schedule, SpectBarrierScheduleResult):
        raise TypeError("schedule must be a SpectBarrierScheduleResult.")
    decisions = tuple(assess_spect_production_barrier_policy(row) for row in schedule.rows)
    review_count = sum(not d.automatic_assessment_allowed for d in decisions)
    return SpectLowTransmissionPolicyAssessment(
        policy_version=SPECT_LOW_TRANSMISSION_POLICY_VERSION,
        policy_status=SPECT_LOW_TRANSMISSION_POLICY_STATUS,
        threshold=SPECT_LOW_TRANSMISSION_THRESHOLD,
        approved=SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
        automatic_production_assessment_allowed=(review_count == 0),
        review_required_count=review_count,
        decisions=decisions,
    )
