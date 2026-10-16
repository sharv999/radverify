"""Versioned serialization contract for isolated PET calculation requests.

The contract stores only validated PET source-domain inputs and validated
barrier requests.  Deserialization reconstructs those domain objects, and the
replay helper invokes the isolated PET calculation service to produce a
replay-verified, non-production result snapshot.

This module is deliberately separate from the Tk UI, production working-project
serializer, production shielding dispatch, and report pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

from modalities.pet import PetContractError, PetExposurePhase, PetSourceDomain
from services.pet_calculation_service import (
    PetBarrierCalculationRequest,
    PetCalculationServiceError,
    PetCalculationServiceResult,
    run_pet_calculation_service,
)


PET_CALCULATION_REQUEST_SCHEMA = "radshield_pet_calculation_request_v2"
PET_CALCULATION_REQUEST_VERSION = 2


class PetCalculationRequestSerializationError(ValueError):
    """Raised when a serialized PET calculation request is invalid."""


@dataclass(frozen=True)
class PetCalculationRequestEnvelope:
    """Validated, serializable PET calculation-service request."""

    source: PetSourceDomain
    barrier_requests: tuple[PetBarrierCalculationRequest, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, PetSourceDomain):
            raise PetCalculationRequestSerializationError(
                "source must be a validated PetSourceDomain."
            )
        for index, request in enumerate(self.barrier_requests):
            if not isinstance(request, PetBarrierCalculationRequest):
                raise PetCalculationRequestSerializationError(
                    f"barrier_requests[{index}] must be a PetBarrierCalculationRequest."
                )


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetCalculationRequestSerializationError(f"{name} must be an object.")
    return value


def _sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PetCalculationRequestSerializationError(f"{name} must be an array.")
    return value


def _text(value: Any, name: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise PetCalculationRequestSerializationError(f"{name} must not be blank.")
    return text


def _number(value: Any, name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PetCalculationRequestSerializationError(f"{name} must be numeric.") from exc
    if not isfinite(numeric):
        raise PetCalculationRequestSerializationError(f"{name} must be finite.")
    return numeric


def pet_calculation_request_to_dict(
    request: PetCalculationRequestEnvelope,
) -> dict[str, Any]:
    """Serialize one validated PET calculation request to clean JSON data."""

    if not isinstance(request, PetCalculationRequestEnvelope):
        raise PetCalculationRequestSerializationError(
            "request must be a PetCalculationRequestEnvelope."
        )

    source = request.source
    return {
        "schema": PET_CALCULATION_REQUEST_SCHEMA,
        "schema_version": PET_CALCULATION_REQUEST_VERSION,
        "production_eligible": False,
        "source": {
            "radionuclide": source.radionuclide_spec.code,
            "injected_activity_mbq": float(source.injected_activity_mbq),
            "patients_per_week": float(source.patients_per_week),
            "residual_activity_factor": float(source.residual_activity_factor),
            "exposure_phases": [
                {
                    "name": phase.name,
                    "start_time_h": float(phase.start_time_h),
                    "duration_h": float(phase.duration_h),
                    "activity_retention_factor": float(phase.activity_retention_factor),
                }
                for phase in source.exposure_phases
            ],
        },
        "barrier_requests": [
            {
                "material_key": item.material_key,
                "distance_m": float(item.distance_m),
                "occupancy_factor": float(item.occupancy_factor),
                "design_goal_uSv_per_week": float(item.design_goal_uSv_per_week),
                "provided_thickness_mm": (
                    None
                    if item.provided_thickness_mm is None
                    else float(item.provided_thickness_mm)
                ),
                "source_name": item.source_name,
            }
            for item in request.barrier_requests
        ],
    }


def pet_calculation_request_from_dict(
    payload: Mapping[str, Any],
) -> PetCalculationRequestEnvelope:
    """Validate and reconstruct one serialized PET calculation request."""

    root = _mapping(payload, "PET calculation request")
    if root.get("schema") != PET_CALCULATION_REQUEST_SCHEMA:
        raise PetCalculationRequestSerializationError(
            f"Unsupported PET calculation request schema {root.get('schema')!r}."
        )
    if root.get("schema_version") != PET_CALCULATION_REQUEST_VERSION:
        raise PetCalculationRequestSerializationError(
            f"Unsupported PET calculation request version {root.get('schema_version')!r}."
        )
    if root.get("production_eligible") is not False:
        raise PetCalculationRequestSerializationError(
            "PET calculation requests must remain explicitly non-production."
        )

    source_data = _mapping(root.get("source"), "source")
    phases_data = _sequence(source_data.get("exposure_phases"), "source.exposure_phases")
    try:
        phases = tuple(
            PetExposurePhase(
                name=_text(_mapping(item, f"source.exposure_phases[{index}]").get("name"), f"source.exposure_phases[{index}].name"),
                start_time_h=_number(_mapping(item, f"source.exposure_phases[{index}]").get("start_time_h"), f"source.exposure_phases[{index}].start_time_h"),
                duration_h=_number(_mapping(item, f"source.exposure_phases[{index}]").get("duration_h"), f"source.exposure_phases[{index}].duration_h"),
                activity_retention_factor=_number(_mapping(item, f"source.exposure_phases[{index}]").get("activity_retention_factor"), f"source.exposure_phases[{index}].activity_retention_factor"),
            )
            for index, item in enumerate(phases_data)
        )
        source = PetSourceDomain(
            radionuclide=_text(source_data.get("radionuclide"), "source.radionuclide"),
            injected_activity_mbq=_number(source_data.get("injected_activity_mbq"), "source.injected_activity_mbq"),
            patients_per_week=_number(source_data.get("patients_per_week"), "source.patients_per_week"),
            residual_activity_factor=_number(source_data.get("residual_activity_factor"), "source.residual_activity_factor"),
            exposure_phases=phases,
        )
    except PetContractError as exc:
        raise PetCalculationRequestSerializationError(str(exc)) from exc

    requests_data = _sequence(root.get("barrier_requests"), "barrier_requests")
    requests: list[PetBarrierCalculationRequest] = []
    for index, item in enumerate(requests_data):
        data = _mapping(item, f"barrier_requests[{index}]")
        provided = data.get("provided_thickness_mm")
        try:
            requests.append(
                PetBarrierCalculationRequest(
                    material_key=_text(data.get("material_key"), f"barrier_requests[{index}].material_key"),
                    distance_m=_number(data.get("distance_m"), f"barrier_requests[{index}].distance_m"),
                    occupancy_factor=_number(data.get("occupancy_factor"), f"barrier_requests[{index}].occupancy_factor"),
                    design_goal_uSv_per_week=_number(data.get("design_goal_uSv_per_week"), f"barrier_requests[{index}].design_goal_uSv_per_week"),
                    provided_thickness_mm=(
                        None
                        if provided is None
                        else _number(provided, f"barrier_requests[{index}].provided_thickness_mm")
                    ),
                    source_name=_text(data.get("source_name"), f"barrier_requests[{index}].source_name"),
                )
            )
        except PetCalculationServiceError as exc:
            raise PetCalculationRequestSerializationError(str(exc)) from exc

    return PetCalculationRequestEnvelope(source=source, barrier_requests=tuple(requests))


def replay_pet_calculation_request(
    payload: Mapping[str, Any],
) -> PetCalculationServiceResult:
    """Reconstruct and execute one serialized PET service request headlessly."""

    request = pet_calculation_request_from_dict(payload)
    normalized = pet_calculation_request_to_dict(request)
    if dict(payload) != normalized:
        raise PetCalculationRequestSerializationError(
            "PET calculation request is not canonical after validation."
        )
    try:
        return run_pet_calculation_service(request.source, request.barrier_requests)
    except PetCalculationServiceError as exc:
        raise PetCalculationRequestSerializationError(str(exc)) from exc


def load_and_replay_pet_calculation_request(
    path: str | Path,
) -> PetCalculationServiceResult:
    """Load a JSON PET request from disk and execute it headlessly."""

    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetCalculationRequestSerializationError(
            f"Unable to load PET calculation request {source_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise PetCalculationRequestSerializationError(
            "PET calculation request JSON root must be an object."
        )
    return replay_pet_calculation_request(payload)
