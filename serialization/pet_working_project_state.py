"""Persistence-only PET working-project state.

This module stores exactly one PET source per room inside the ordinary editable
working-project JSON. It deliberately stores inputs only: no barrier results or
report payload. The durable state supports the controlled production-host scope
for persistence, gated calculation, and in-app Results while issued output stays
disabled.

Schema v3 records those current host semantics explicitly. Legacy v2 payloads
remain readable and are canonicalised to v3 when saved again.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from engine.pet_calculation_input_provenance import (
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID,
    PET_CALCULATION_INPUT_PROVENANCE_REVISION,
)
from geometry.pet_preview_position import PetPreviewPosition
from modalities.pet import PetExposurePhase, PetSourceDomain


PET_WORKING_PROJECT_STATE_KEY = "pet_single_source"
PET_WORKING_PROJECT_STATE_SCHEMA = "radshield_pet_working_source_v3"
PET_WORKING_PROJECT_STATE_VERSION = 3
PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA = "radshield_pet_working_source_v2"
PET_WORKING_PROJECT_STATE_LEGACY_VERSION = 2


class PetWorkingProjectStateError(ValueError):
    """Raised when persisted PET working state is invalid."""


@dataclass(frozen=True)
class PetWorkingProjectState:
    source: PetSourceDomain
    position: PetPreviewPosition

    def __post_init__(self) -> None:
        if not isinstance(self.source, PetSourceDomain):
            raise PetWorkingProjectStateError("source must be a validated PetSourceDomain.")
        if not isinstance(self.position, PetPreviewPosition):
            raise PetWorkingProjectStateError("position must be a PetPreviewPosition.")


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetWorkingProjectStateError(f"{field} must be numeric.") from exc
    if not isfinite(number):
        raise PetWorkingProjectStateError(f"{field} must be finite.")
    return number


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PetWorkingProjectStateError(f"{field} must not be blank.")
    return text


def pet_working_project_state_to_dict(state: PetWorkingProjectState) -> dict[str, Any]:
    source = state.source
    return {
        "schema": PET_WORKING_PROJECT_STATE_SCHEMA,
        "schema_version": PET_WORKING_PROJECT_STATE_VERSION,
        "production_host_enabled": True,
        "production_calculation_enabled": True,
        "issued_output_enabled": False,
        "single_source_per_room": True,
        "provenance_manifest": {
            "manifest_id": PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID,
            "revision": PET_CALCULATION_INPUT_PROVENANCE_REVISION,
        },
        "position": {
            "x_from_west_m": float(state.position.x_from_west_m),
            "y_from_south_m": float(state.position.y_from_south_m),
            "height_above_ffl_m": float(state.position.height_above_ffl_m),
        },
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
    }


def pet_working_project_state_from_dict(payload: Mapping[str, Any]) -> PetWorkingProjectState:
    if not isinstance(payload, Mapping):
        raise PetWorkingProjectStateError("PET working-project state must be an object.")
    schema = payload.get("schema")
    version = payload.get("schema_version")
    if (schema, version) == (PET_WORKING_PROJECT_STATE_SCHEMA, PET_WORKING_PROJECT_STATE_VERSION):
        expected = {
            "schema", "schema_version", "production_host_enabled",
            "production_calculation_enabled", "issued_output_enabled",
            "single_source_per_room", "provenance_manifest", "position", "source",
        }
        if set(payload) != expected:
            raise PetWorkingProjectStateError("PET working-project state contains missing or unexpected fields.")
        if payload.get("production_host_enabled") is not True:
            raise PetWorkingProjectStateError("PET working-project state must declare the controlled production host enabled.")
        if payload.get("production_calculation_enabled") is not True:
            raise PetWorkingProjectStateError("PET working-project state must declare gated production calculation enabled.")
        if payload.get("issued_output_enabled") is not False:
            raise PetWorkingProjectStateError("PET working-project state must keep issued output disabled.")
    elif (schema, version) == (PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA, PET_WORKING_PROJECT_STATE_LEGACY_VERSION):
        expected = {
            "schema", "schema_version", "production_eligible", "single_source_per_room",
            "provenance_manifest", "position", "source",
        }
        if set(payload) != expected:
            raise PetWorkingProjectStateError("Legacy PET working-project state contains missing or unexpected fields.")
        if payload.get("production_eligible") is not False:
            raise PetWorkingProjectStateError("Legacy PET working-project production_eligible flag must remain false.")
    else:
        raise PetWorkingProjectStateError("Unsupported PET working-project state schema/version.")
    if payload.get("single_source_per_room") is not True:
        raise PetWorkingProjectStateError("PET working-project state must contain exactly one source per room.")

    provenance = payload.get("provenance_manifest")
    if not isinstance(provenance, Mapping):
        raise PetWorkingProjectStateError("PET working-project provenance manifest identity is required.")
    if provenance.get("manifest_id") != PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID:
        raise PetWorkingProjectStateError("PET working-project provenance manifest ID does not match the frozen manifest.")
    if provenance.get("revision") != PET_CALCULATION_INPUT_PROVENANCE_REVISION:
        raise PetWorkingProjectStateError("PET working-project provenance manifest revision does not match the frozen manifest.")

    position_raw = payload.get("position")
    if not isinstance(position_raw, Mapping):
        raise PetWorkingProjectStateError("PET working-project position is required.")
    position = PetPreviewPosition(
        x_from_west_m=_number(position_raw.get("x_from_west_m"), "position.x_from_west_m"),
        y_from_south_m=_number(position_raw.get("y_from_south_m"), "position.y_from_south_m"),
        height_above_ffl_m=_number(position_raw.get("height_above_ffl_m"), "position.height_above_ffl_m"),
    )

    source_raw = payload.get("source")
    if not isinstance(source_raw, Mapping):
        raise PetWorkingProjectStateError("PET working-project source is required.")
    phases_raw = source_raw.get("exposure_phases")
    if not isinstance(phases_raw, list):
        raise PetWorkingProjectStateError("source.exposure_phases must be an array.")
    try:
        source = PetSourceDomain(
            radionuclide=_text(source_raw.get("radionuclide"), "source.radionuclide"),
            injected_activity_mbq=_number(source_raw.get("injected_activity_mbq"), "source.injected_activity_mbq"),
            patients_per_week=_number(source_raw.get("patients_per_week"), "source.patients_per_week"),
            residual_activity_factor=_number(source_raw.get("residual_activity_factor"), "source.residual_activity_factor"),
            exposure_phases=tuple(
                PetExposurePhase(
                    name=_text(item.get("name"), f"source.exposure_phases[{index}].name"),
                    start_time_h=_number(item.get("start_time_h"), f"source.exposure_phases[{index}].start_time_h"),
                    duration_h=_number(item.get("duration_h"), f"source.exposure_phases[{index}].duration_h"),
                    activity_retention_factor=_number(item.get("activity_retention_factor"), f"source.exposure_phases[{index}].activity_retention_factor"),
                )
                for index, item in enumerate(phases_raw)
                if isinstance(item, Mapping)
            ),
        )
    except Exception as exc:
        if isinstance(exc, PetWorkingProjectStateError):
            raise
        raise PetWorkingProjectStateError(str(exc)) from exc

    state = PetWorkingProjectState(source=source, position=position)
    if (schema, version) == (PET_WORKING_PROJECT_STATE_SCHEMA, PET_WORKING_PROJECT_STATE_VERSION) and dict(payload) != pet_working_project_state_to_dict(state):
        raise PetWorkingProjectStateError("PET working-project state is not canonical after validation.")
    return state


def get_room_pet_working_state(room: Any) -> PetWorkingProjectState | None:
    modality_state = getattr(room, "modality_state", {}) or {}
    if not isinstance(modality_state, Mapping):
        return None
    payload = modality_state.get(PET_WORKING_PROJECT_STATE_KEY)
    if payload is None:
        return None
    return pet_working_project_state_from_dict(payload)


def set_room_pet_working_state(room: Any, state: PetWorkingProjectState) -> None:
    modality_state = dict(getattr(room, "modality_state", {}) or {})
    modality_state[PET_WORKING_PROJECT_STATE_KEY] = pet_working_project_state_to_dict(state)
    room.modality_state = modality_state
