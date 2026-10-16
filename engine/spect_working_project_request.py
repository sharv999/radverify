"""Step 23 reconstruction adapter from durable SPECT working state to Step 21 request.

This module belongs to the headless calculation boundary, not serialization.
Normal project persistence stores source/workload only; existing room/barrier
geometry is adapted separately into Step 5 barrier requests.
"""
from __future__ import annotations

from typing import Sequence

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest
from engine.spect_calculation_request_contract import (
    SpectCalculationRequestEnvelope,
    spect_calculation_request_to_dict,
)
from serialization.spect_working_project_state import (
    SpectWorkingProjectState,
    SpectWorkingProjectStateError,
)


def build_spect_working_calculation_request(
    state: SpectWorkingProjectState,
    barrier_requests: Sequence[SpectBarrierScheduleRequest],
) -> SpectCalculationRequestEnvelope:
    """Reconstruct and validate the exact Step 21 canonical request boundary."""
    if not isinstance(state, SpectWorkingProjectState):
        raise SpectWorkingProjectStateError("state must be a SpectWorkingProjectState.")
    requests = tuple(barrier_requests)
    for index, item in enumerate(requests):
        if not isinstance(item, SpectBarrierScheduleRequest):
            raise SpectWorkingProjectStateError(
                f"barrier_requests[{index}] must be a SpectBarrierScheduleRequest."
            )
    envelope = SpectCalculationRequestEnvelope(
        source=state.source,
        barrier_requests=requests,
        physics_freeze=dict(state.physics_freeze),
    )
    spect_calculation_request_to_dict(envelope)
    return envelope
