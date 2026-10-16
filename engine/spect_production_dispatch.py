"""SPECT Step 26 isolated production calculation dispatch.

This is the first production-eligible SPECT calculation entry point.  It is
intentionally headless and narrow:

* input is validated Step 23 working state plus Step 5 barrier requests;
* Step 24/25 production readiness must pass;
* calculations use the Step 20 frozen Tc-99m practical dataset;
* the Step 25 low-transmission policy is applied to the calculated schedule;
* any row requiring geometry-specific review fails closed;
* Results, reports, PDF/CSV export, certification, and desktop modality
  registration remain outside this module.

The historical Step 5 schedule remains marked ``production_eligible=False``;
it is used here as the frozen calculation substrate.  Only the Step 26 wrapper
is a production dispatch result.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from engine.spect_barrier_calculation import SPECT_PRACTICAL_DATASET_PATH
from engine.spect_barrier_schedule import (
    SpectBarrierScheduleRequest,
    SpectBarrierScheduleResult,
    calculate_spect_tc99m_barrier_schedule,
)
from engine.spect_calculation_request_contract import (
    current_spect_calculation_physics_freeze,
    spect_calculation_request_to_dict,
)
from engine.spect_low_transmission_policy import (
    SpectLowTransmissionPolicyAssessment,
    assess_spect_low_transmission_policy,
)
from engine.spect_practical_transmission import load_frozen_spect_tc99m_practical_dataset
from engine.spect_production_dispatch_gate import (
    SpectProductionDispatchReadiness,
    require_spect_production_dispatch_enabled,
)
from engine.spect_working_project_request import build_spect_working_calculation_request
from serialization.spect_working_project_state import SpectWorkingProjectState


SPECT_PRODUCTION_DISPATCH_VERSION = 1
SPECT_PRODUCTION_RESULT_SCHEMA = "radshield_spect_production_calculation_result_v1"
SPECT_PRODUCTION_RESULT_VERSION = 1


class SpectProductionCalculationError(RuntimeError):
    """Base exception for Step 26 production-dispatch failures."""


class SpectProductionPolicyReviewRequiredError(SpectProductionCalculationError):
    """Raised when Step 25 requires geometry-specific review."""


@dataclass(frozen=True)
class SpectProductionCalculationResult:
    dispatch_version: int
    schema: str
    schema_version: int
    production_eligible: bool
    output_eligible: bool
    results_integration_enabled: bool
    report_integration_enabled: bool
    request_sha256: str
    physics_freeze: Mapping[str, Any]
    readiness: SpectProductionDispatchReadiness
    schedule: SpectBarrierScheduleResult
    low_transmission_policy: SpectLowTransmissionPolicyAssessment

    def as_dict(self) -> dict[str, Any]:
        """Return production-boundary metadata without inventing report payloads."""
        return {
            "dispatch_version": self.dispatch_version,
            "schema": self.schema,
            "schema_version": self.schema_version,
            "production_eligible": self.production_eligible,
            "output_eligible": self.output_eligible,
            "results_integration_enabled": self.results_integration_enabled,
            "report_integration_enabled": self.report_integration_enabled,
            "request_sha256": self.request_sha256,
            "physics_freeze": dict(self.physics_freeze),
            "readiness": self.readiness.as_dict(),
            "low_transmission_policy": self.low_transmission_policy.as_dict(),
            "schedule_status": self.schedule.status,
            "schedule_contract_version": self.schedule.contract_version,
            "barrier_count": len(self.schedule.rows),
        }


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dispatch_spect_production_calculation(
    state: SpectWorkingProjectState,
    barrier_requests: Sequence[SpectBarrierScheduleRequest],
) -> SpectProductionCalculationResult:
    """Execute the isolated Step 26 production SPECT calculation entry point.

    Automatic production dispatch is refused if Step 25 classifies any barrier
    as requiring geometry-specific review.  The caller receives no production
    result object in that case.
    """
    requests = tuple(barrier_requests)

    readiness = require_spect_production_dispatch_enabled(state, requests)

    envelope = build_spect_working_calculation_request(state, requests)
    canonical_request = spect_calculation_request_to_dict(envelope)

    dataset = load_frozen_spect_tc99m_practical_dataset(
        SPECT_PRACTICAL_DATASET_PATH
    )
    schedule = calculate_spect_tc99m_barrier_schedule(
        state.source,
        requests,
        dataset=dataset,
    )
    policy = assess_spect_low_transmission_policy(schedule)

    if not policy.automatic_production_assessment_allowed:
        barrier_ids = [
            decision.barrier_id
            for decision in policy.decisions
            if not decision.automatic_assessment_allowed
        ]
        joined = ", ".join(barrier_ids) or "unknown barrier"
        raise SpectProductionPolicyReviewRequiredError(
            "Automatic SPECT production calculation is blocked by the approved "
            "Step 25 low-transmission policy; geometry-specific medical-physics "
            f"review is required for: {joined}."
        )

    return SpectProductionCalculationResult(
        dispatch_version=SPECT_PRODUCTION_DISPATCH_VERSION,
        schema=SPECT_PRODUCTION_RESULT_SCHEMA,
        schema_version=SPECT_PRODUCTION_RESULT_VERSION,
        production_eligible=True,
        output_eligible=False,
        results_integration_enabled=False,
        report_integration_enabled=False,
        request_sha256=_canonical_sha256(canonical_request),
        physics_freeze=current_spect_calculation_physics_freeze(),
        readiness=readiness,
        schedule=schedule,
        low_transmission_policy=policy,
    )
