"""Canonical non-production SPECT practical calculation request/replay contract.

Step 21 freezes a deterministic request/output boundary around the Step 20
physics-approved/frozen Tc-99m source and practical-transmission datasets.
It remains disconnected from production project persistence, UI dispatch,
Results, and reports.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.spect_barrier_schedule import (
    SpectBarrierScheduleRequest,
    SpectBarrierScheduleResult,
    calculate_spect_tc99m_barrier_schedule,
)
from engine.spect_practical_transmission import load_frozen_spect_tc99m_practical_dataset
from engine.spect_barrier_calculation import SPECT_PRACTICAL_DATASET_PATH
from modalities.spect import SpectSourceDomain

SPECT_CALCULATION_REQUEST_SCHEMA = "radshield_spect_practical_calculation_request_v1"
SPECT_CALCULATION_REQUEST_VERSION = 1
SPECT_CALCULATION_RESULT_SCHEMA = "radshield_spect_practical_calculation_result_v1"
SPECT_CALCULATION_RESULT_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
SPECT_PHYSICS_MANIFEST_PATH = ROOT / "data" / "spect" / "spect_physics_approval_manifest.json"

class SpectCalculationRequestError(ValueError):
    pass

@dataclass(frozen=True)
class SpectCalculationRequestEnvelope:
    source: SpectSourceDomain
    barrier_requests: tuple[SpectBarrierScheduleRequest, ...]
    physics_freeze: Mapping[str, Any]

@dataclass(frozen=True)
class SpectCalculationReplayResult:
    request: SpectCalculationRequestEnvelope
    schedule: SpectBarrierScheduleResult
    payload: Mapping[str, Any]
    replay_verified: bool = True


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _manifest() -> dict[str, Any]:
    payload = json.loads(SPECT_PHYSICS_MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("status") != "approved_locked_verified_nonproduction" or payload.get("production_enabled") is not False:
        raise SpectCalculationRequestError("SPECT Step 20 physics manifest is not an approved non-production freeze.")
    return payload


def current_spect_calculation_physics_freeze() -> dict[str, Any]:
    manifest = _manifest()
    datasets = manifest["datasets"]
    return {
        "freeze_id": manifest["freeze_id"],
        "radionuclide_source": {
            key: datasets["radionuclide_source"][key]
            for key in ("dataset_id", "revision", "records_sha256", "canonical_payload_sha256")
        },
        "practical_transmission": {
            key: datasets["practical_transmission"][key]
            for key in ("dataset_id", "revision", "records_sha256", "canonical_payload_sha256")
        },
    }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpectCalculationRequestError(f"{field} must be an object.")
    return value


def _number(value: Any, field: str) -> float:
    try: number = float(value)
    except (TypeError, ValueError) as exc: raise SpectCalculationRequestError(f"{field} must be numeric.") from exc
    if not isfinite(number): raise SpectCalculationRequestError(f"{field} must be finite.")
    return number


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise SpectCalculationRequestError(f"{field} must be a non-blank string.")
    return value.strip()


def spect_calculation_request_to_dict(request: SpectCalculationRequestEnvelope) -> dict[str, Any]:
    if not isinstance(request, SpectCalculationRequestEnvelope): raise SpectCalculationRequestError("request must be a SpectCalculationRequestEnvelope.")
    source = request.source
    return {
        "schema": SPECT_CALCULATION_REQUEST_SCHEMA,
        "schema_version": SPECT_CALCULATION_REQUEST_VERSION,
        "production_eligible": False,
        "physics_freeze": dict(request.physics_freeze),
        "source": {
            "radionuclide": source.radionuclide_spec.code,
            "administered_activity_mbq": float(source.administered_activity_mbq),
            "patients_per_week": float(source.patients_per_week),
            "imaging_duration_h": float(source.imaging_duration_h),
        },
        "barrier_requests": [
            {
                "barrier_id": b.barrier_id,
                "barrier_name": b.barrier_name,
                "material_key": b.material_key,
                "distance_m": float(b.distance_m),
                "occupancy_factor": float(b.occupancy_factor),
                "design_goal_uSv_per_week": float(b.design_goal_uSv_per_week),
                "provided_thickness_mm": None if b.provided_thickness_mm is None else float(b.provided_thickness_mm),
                "source_name": b.source_name,
            } for b in request.barrier_requests
        ],
    }


def spect_calculation_request_from_dict(payload: Mapping[str, Any]) -> SpectCalculationRequestEnvelope:
    root = _mapping(payload, "SPECT calculation request")
    expected = {"schema","schema_version","production_eligible","physics_freeze","source","barrier_requests"}
    if set(root) != expected: raise SpectCalculationRequestError("SPECT calculation request contains missing or unexpected fields.")
    if root["schema"] != SPECT_CALCULATION_REQUEST_SCHEMA or root["schema_version"] != SPECT_CALCULATION_REQUEST_VERSION:
        raise SpectCalculationRequestError("Unsupported SPECT practical calculation request schema/version.")
    if root["production_eligible"] is not False: raise SpectCalculationRequestError("SPECT practical calculation requests must remain explicitly non-production.")
    supplied_freeze = dict(_mapping(root["physics_freeze"], "physics_freeze"))
    if supplied_freeze != current_spect_calculation_physics_freeze():
        raise SpectCalculationRequestError("SPECT calculation request physics freeze does not match the installed Step 20 physics freeze.")
    s = _mapping(root["source"], "source")
    if set(s) != {"radionuclide","administered_activity_mbq","patients_per_week","imaging_duration_h"}: raise SpectCalculationRequestError("source contains missing or unexpected fields.")
    try:
        source = SpectSourceDomain(_text(s["radionuclide"],"source.radionuclide"), _number(s["administered_activity_mbq"],"source.administered_activity_mbq"), _number(s["patients_per_week"],"source.patients_per_week"), _number(s["imaging_duration_h"],"source.imaging_duration_h"))
    except ValueError as exc: raise SpectCalculationRequestError(str(exc)) from exc
    raw_barriers = root["barrier_requests"]
    if isinstance(raw_barriers,(str,bytes)) or not isinstance(raw_barriers,Sequence): raise SpectCalculationRequestError("barrier_requests must be an array.")
    barriers=[]
    expected_b={"barrier_id","barrier_name","material_key","distance_m","occupancy_factor","design_goal_uSv_per_week","provided_thickness_mm","source_name"}
    for i, raw in enumerate(raw_barriers):
        b=_mapping(raw,f"barrier_requests[{i}]")
        if set(b)!=expected_b: raise SpectCalculationRequestError(f"barrier_requests[{i}] contains missing or unexpected fields.")
        provided = None if b["provided_thickness_mm"] is None else _number(b["provided_thickness_mm"],f"barrier_requests[{i}].provided_thickness_mm")
        try:
            barriers.append(SpectBarrierScheduleRequest(
                barrier_id=_text(b["barrier_id"],f"barrier_requests[{i}].barrier_id"), barrier_name=_text(b["barrier_name"],f"barrier_requests[{i}].barrier_name"), material_key=_text(b["material_key"],f"barrier_requests[{i}].material_key"), distance_m=_number(b["distance_m"],f"barrier_requests[{i}].distance_m"), occupancy_factor=_number(b["occupancy_factor"],f"barrier_requests[{i}].occupancy_factor"), design_goal_uSv_per_week=_number(b["design_goal_uSv_per_week"],f"barrier_requests[{i}].design_goal_uSv_per_week"), provided_thickness_mm=provided, source_name=_text(b["source_name"],f"barrier_requests[{i}].source_name")
            ))
        except ValueError as exc: raise SpectCalculationRequestError(str(exc)) from exc
    envelope=SpectCalculationRequestEnvelope(source,tuple(barriers),supplied_freeze)
    if spect_calculation_request_to_dict(envelope) != dict(root): raise SpectCalculationRequestError("SPECT calculation request is valid but not canonical.")
    return envelope


def _physics_to_dict(p) -> dict[str, Any]:
    return {k:getattr(p,k) for k in ("contract_version","radionuclide","radiation_type","tvl_key","administered_activity_mbq","patients_per_week","imaging_duration_h","decay_integrated_hours","weekly_dose_uSv_at_1m","calculation_basis")}


def _schedule_to_dict(schedule: SpectBarrierScheduleResult) -> dict[str, Any]:
    rows=[]
    for r in schedule.rows:
        rows.append({name:getattr(r,name) for name in r.__dataclass_fields__})
    return {
        "contract_version": schedule.contract_version, "status": schedule.status, "production_eligible": schedule.production_eligible,
        "ordering_basis": schedule.ordering_basis, "source_physics": _physics_to_dict(schedule.source_physics), "rows": rows,
        "pass_count":schedule.pass_count,"fail_count":schedule.fail_count,"not_assessed_count":schedule.not_assessed_count,
        "requires_room_scatter_review":schedule.requires_room_scatter_review,"contains_source_model_extrapolation":schedule.contains_source_model_extrapolation,
    }


def replay_spect_calculation_request(payload: Mapping[str, Any]) -> SpectCalculationReplayResult:
    request=spect_calculation_request_from_dict(payload)
    dataset=load_frozen_spect_tc99m_practical_dataset(SPECT_PRACTICAL_DATASET_PATH)
    first=calculate_spect_tc99m_barrier_schedule(request.source,request.barrier_requests,dataset=dataset)
    second=calculate_spect_tc99m_barrier_schedule(request.source,request.barrier_requests,dataset=dataset)
    first_dict=_schedule_to_dict(first); second_dict=_schedule_to_dict(second)
    if first_dict != second_dict: raise SpectCalculationRequestError("SPECT calculation request replay was not deterministic.")
    canonical_request=spect_calculation_request_to_dict(request)
    result_payload={
        "schema":SPECT_CALCULATION_RESULT_SCHEMA,"schema_version":SPECT_CALCULATION_RESULT_VERSION,"production_eligible":False,
        "request_sha256":_canonical_sha256(canonical_request),"physics_freeze":current_spect_calculation_physics_freeze(),"schedule":first_dict,"replay_verified":True,
    }
    return SpectCalculationReplayResult(request,first,result_payload,True)


def load_and_replay_spect_calculation_request(path: str|Path) -> SpectCalculationReplayResult:
    try: payload=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise SpectCalculationRequestError(f"Unable to load SPECT calculation request {path}.") from exc
    if not isinstance(payload,dict): raise SpectCalculationRequestError("SPECT calculation request root must be an object.")
    return replay_spect_calculation_request(payload)
