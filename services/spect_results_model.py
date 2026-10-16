"""Step 27 production Results payload adapter for persisted SPECT working state.

This module opens the successful Step 26 production calculation wrapper to the
ordinary in-app Results presentation only. It does not participate in PDF/report
payload generation, machine-readable export, or certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

from engine.spect_production_room_adapter import build_spect_production_room_requests
from engine.spect_production_dispatch import (
    SpectProductionCalculationResult,
    dispatch_spect_production_calculation,
)
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_KEY,
    get_room_spect_working_state,
)
from services.spect_results_presentation_contract import (
    SPECT_RESULTS_PRESENTATION_BASELINE,
    SPECT_RESULTS_PRESENTATION_CONTRACT_VERSION,
)

SPECT_RESULTS_MODEL_CONTRACT_VERSION = 1
SPECT_RESULTS_PAYLOAD_SCHEMA = "radshield_spect_production_results_payload_v1"
SPECT_RESULTS_PAYLOAD_VERSION = 1


class SpectResultsModelError(ValueError):
    """Raised when persisted room state cannot produce Step 27 Results."""


@dataclass(frozen=True)
class SpectProductionResultsPayload:
    schema: str
    schema_version: int
    production_eligible: bool
    output_eligible: bool
    report_integration_enabled: bool
    certification_enabled: bool
    room_name: str
    request_sha256: str
    physics_freeze: Mapping[str, Any]
    rows: tuple[Dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "production_eligible": self.production_eligible,
            "output_eligible": self.output_eligible,
            "report_integration_enabled": self.report_integration_enabled,
            "certification_enabled": self.certification_enabled,
            "room_name": self.room_name,
            "request_sha256": self.request_sha256,
            "physics_freeze": dict(self.physics_freeze),
            "rows": [dict(row) for row in self.rows],
        }


def room_has_persisted_spect_working_state(room: Any) -> bool:
    modality_state = getattr(room, "modality_state", {}) or {}
    return isinstance(modality_state, Mapping) and SPECT_WORKING_PROJECT_STATE_KEY in modality_state



def _row_payload(barrier: Any, schedule_row: Any, decision: Any, dispatched: SpectProductionCalculationResult) -> Dict[str, Any]:
    required = float(schedule_row.required_thickness_mm)
    provided = float(schedule_row.provided_thickness_mm) if schedule_row.provided_thickness_mm is not None else None
    material_key = str(schedule_row.material_key)
    material = str(getattr(barrier, "material", "") or "")
    transmitted = (
        schedule_row.transmitted_weekly_dose_uSv
        if decision.production_transmitted_dose_reportable
        else None
    )
    margin = (provided - required) if provided is not None else None
    return {
        "results_model_contract_version": SPECT_RESULTS_MODEL_CONTRACT_VERSION,
        "results_presentation_contract_version": SPECT_RESULTS_PRESENTATION_CONTRACT_VERSION,
        "results_presentation_baseline": SPECT_RESULTS_PRESENTATION_BASELINE,
        "barrier_name": str(getattr(barrier, "name", "") or schedule_row.barrier_name),
        "barrier_id": schedule_row.barrier_id,
        "results_source": "spect_step26_production_dispatch",
        "source_type": "spect_patient",
        "solver_mode": "spect_tc99m_practical_archer",
        "material": material,
        "material_key": material_key,
        "distance_m": float(schedule_row.distance_m),
        "occupancy_factor": float(schedule_row.occupancy_factor),
        "design_goal_uSv_per_week": float(schedule_row.design_goal_uSv_per_week),
        "unshielded_weekly_dose_uSv": float(schedule_row.unshielded_weekly_dose_uSv_at_barrier),
        "occupied_unshielded_weekly_dose_uSv": float(schedule_row.occupied_unshielded_weekly_dose_uSv),
        "barrier_transmission_factor_B": float(schedule_row.required_transmission),
        "required_thickness_mm": required,
        "required_lead_mm": required if material_key == "lead" else None,
        "required_concrete_mm": required if material_key in {"concrete_1600kg_m3", "concrete_2300kg_m3"} else None,
        "provided_thickness_mm": provided,
        "provided_transmission": schedule_row.provided_transmission,
        "transmitted_dose_uSv_per_week": transmitted,
        "transmitted_dose_reportable": bool(decision.production_transmitted_dose_reportable),
        "compliance_status": str(decision.status),
        "margin_mm": margin,
        "source_contributions": "SPECT patient source",
        "dominant_source": "SPECT patient source",
        "notes": "IN-APP RESULTS ONLY — SPECT PDF/report, export and certification remain blocked.",
        "calculation_reasoning": (
            "Approved frozen Tc-99m source physics were scaled by source-to-barrier distance and occupancy, "
            "then assessed with the approved practical Archer transmission model and Step 25 production policy."
        ),
        "production_eligible": True,
        "output_eligible": False,
        "report_integration_enabled": False,
        "certification_enabled": False,
        "request_sha256": dispatched.request_sha256,
        "physics_freeze": dict(dispatched.physics_freeze),
        "policy_version": dispatched.low_transmission_policy.policy_version,
        "policy_status": dispatched.low_transmission_policy.policy_status,
        "policy_decision_basis": decision.decision_basis,
        "practical_record_id": schedule_row.practical_record_id,
        "practical_provenance": schedule_row.practical_provenance,
    }


def build_spect_production_results_payload(project: Any, room: Any) -> SpectProductionResultsPayload:
    del project  # room state is the durable Step 23 source boundary; kept for API symmetry.
    state = get_room_spect_working_state(room)
    if state is None:
        raise SpectResultsModelError("SPECT room has no persisted Step 23 working state.")
    requests = build_spect_production_room_requests(room)
    dispatched = dispatch_spect_production_calculation(state, requests)
    barriers = tuple(getattr(room, "barriers", ()) or ())
    if len(barriers) != len(dispatched.schedule.rows):
        raise SpectResultsModelError("SPECT Results barrier count does not match the production schedule.")
    decisions = dispatched.low_transmission_policy.decisions
    if len(decisions) != len(dispatched.schedule.rows):
        raise SpectResultsModelError("SPECT production policy decision count does not match the production schedule.")
    rows = tuple(
        _row_payload(barrier, schedule_row, decision, dispatched)
        for barrier, schedule_row, decision in zip(barriers, dispatched.schedule.rows, decisions)
    )
    return SpectProductionResultsPayload(
        schema=SPECT_RESULTS_PAYLOAD_SCHEMA,
        schema_version=SPECT_RESULTS_PAYLOAD_VERSION,
        production_eligible=True,
        output_eligible=False,
        report_integration_enabled=False,
        certification_enabled=False,
        room_name=str(getattr(room, "name", "") or ""),
        request_sha256=dispatched.request_sha256,
        physics_freeze=dict(dispatched.physics_freeze),
        rows=rows,
    )


def build_room_results_model(project: Any, room: Any, *, fallback_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not room_has_persisted_spect_working_state(room):
        return list(fallback_results or [])
    return [dict(row) for row in build_spect_production_results_payload(project, room).rows]
