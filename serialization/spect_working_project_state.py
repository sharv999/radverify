"""Durable SPECT working-project source state.

Step 23 permits validated SPECT source/workload inputs to live under
``Room.modality_state`` in an ordinary RadShield working-project file.

This durable state supports the controlled SPECT production-host scope:
working-project persistence, gated production calculation, and in-app Results.
It does not enable issued PDF, machine export, or certification. Preview-only
what-if geometry remains in ``.spectpreview.json``; normal room/barrier geometry
continues to use the existing project model.

Schema v2 records the current host/calculation meaning explicitly. Legacy v1
payloads remain readable for backward compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from engine.spect_calculation_request_contract import (
    SPECT_CALCULATION_REQUEST_SCHEMA,
    SPECT_CALCULATION_REQUEST_VERSION,
    current_spect_calculation_physics_freeze,
)
from modalities.spect import SpectSourceDomain


SPECT_WORKING_PROJECT_STATE_KEY = "spect_patient_working_source"
SPECT_WORKING_PROJECT_STATE_SCHEMA = "radshield_spect_working_source_v2"
SPECT_WORKING_PROJECT_STATE_VERSION = 2
SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA = "radshield_spect_working_source_v1"
SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION = 1


class SpectWorkingProjectStateError(ValueError):
    """Raised when durable SPECT working-project state is invalid."""


@dataclass(frozen=True)
class SpectWorkingProjectState:
    source: SpectSourceDomain
    physics_freeze: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.source, SpectSourceDomain):
            raise SpectWorkingProjectStateError("source must be a validated SpectSourceDomain.")
        if dict(self.physics_freeze) != current_spect_calculation_physics_freeze():
            raise SpectWorkingProjectStateError(
                "SPECT working-project physics freeze does not match the installed Step 20 freeze."
            )


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectWorkingProjectStateError(f"{field} must be numeric.") from exc
    if not isfinite(number):
        raise SpectWorkingProjectStateError(f"{field} must be finite.")
    return number


def spect_working_project_state_to_dict(state: SpectWorkingProjectState) -> dict[str, Any]:
    if not isinstance(state, SpectWorkingProjectState):
        raise SpectWorkingProjectStateError("state must be a SpectWorkingProjectState.")
    source = state.source
    return {
        "schema": SPECT_WORKING_PROJECT_STATE_SCHEMA,
        "schema_version": SPECT_WORKING_PROJECT_STATE_VERSION,
        "production_host_enabled": True,
        "production_calculation_enabled": True,
        "issued_output_enabled": False,
        "physics_freeze": dict(state.physics_freeze),
        "request_contract": {
            "schema": SPECT_CALCULATION_REQUEST_SCHEMA,
            "schema_version": SPECT_CALCULATION_REQUEST_VERSION,
        },
        "source": {
            "radionuclide": source.radionuclide_spec.code,
            "administered_activity_mbq": float(source.administered_activity_mbq),
            "patients_per_week": float(source.patients_per_week),
            "imaging_duration_h": float(source.imaging_duration_h),
        },
    }


def spect_working_project_state_from_dict(payload: Mapping[str, Any]) -> SpectWorkingProjectState:
    if not isinstance(payload, Mapping):
        raise SpectWorkingProjectStateError("SPECT working-project state must be an object.")

    schema = payload.get("schema")
    version = payload.get("schema_version")
    if (schema, version) == (
        SPECT_WORKING_PROJECT_STATE_SCHEMA,
        SPECT_WORKING_PROJECT_STATE_VERSION,
    ):
        expected = {
            "schema",
            "schema_version",
            "production_host_enabled",
            "production_calculation_enabled",
            "issued_output_enabled",
            "physics_freeze",
            "request_contract",
            "source",
        }
        if set(payload) != expected:
            raise SpectWorkingProjectStateError(
                "SPECT working-project state contains missing or unexpected fields."
            )
        if payload.get("production_host_enabled") is not True:
            raise SpectWorkingProjectStateError(
                "SPECT working-project state must declare the controlled production host enabled."
            )
        if payload.get("production_calculation_enabled") is not True:
            raise SpectWorkingProjectStateError(
                "SPECT working-project state must declare gated production calculation enabled."
            )
        if payload.get("issued_output_enabled") is not False:
            raise SpectWorkingProjectStateError(
                "SPECT working-project state must keep issued output disabled."
            )
    elif (schema, version) == (
        SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
        SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION,
    ):
        expected = {
            "schema",
            "schema_version",
            "production_eligible",
            "calculation_dispatch_enabled",
            "output_enabled",
            "physics_freeze",
            "request_contract",
            "source",
        }
        if set(payload) != expected:
            raise SpectWorkingProjectStateError(
                "Legacy SPECT working-project state contains missing or unexpected fields."
            )
        if payload.get("production_eligible") is not False:
            raise SpectWorkingProjectStateError(
                "Legacy SPECT working-project production_eligible flag must remain false."
            )
        if payload.get("calculation_dispatch_enabled") is not False:
            raise SpectWorkingProjectStateError(
                "Legacy SPECT working-project calculation_dispatch_enabled flag must remain false."
            )
        if payload.get("output_enabled") is not False:
            raise SpectWorkingProjectStateError(
                "Legacy SPECT working-project output_enabled flag must remain false."
            )
    else:
        raise SpectWorkingProjectStateError("Unsupported SPECT working-project state schema/version.")

    request_contract = payload.get("request_contract")
    if not isinstance(request_contract, Mapping):
        raise SpectWorkingProjectStateError("SPECT request contract identity is required.")
    if dict(request_contract) != {
        "schema": SPECT_CALCULATION_REQUEST_SCHEMA,
        "schema_version": SPECT_CALCULATION_REQUEST_VERSION,
    }:
        raise SpectWorkingProjectStateError(
            "SPECT working-project request contract does not match the installed Step 21 contract."
        )

    freeze = payload.get("physics_freeze")
    if not isinstance(freeze, Mapping) or dict(freeze) != current_spect_calculation_physics_freeze():
        raise SpectWorkingProjectStateError(
            "SPECT working-project physics freeze does not match the installed Step 20 freeze."
        )

    source_raw = payload.get("source")
    if not isinstance(source_raw, Mapping):
        raise SpectWorkingProjectStateError("SPECT working-project source is required.")
    if set(source_raw) != {
        "radionuclide",
        "administered_activity_mbq",
        "patients_per_week",
        "imaging_duration_h",
    }:
        raise SpectWorkingProjectStateError(
            "SPECT working-project source contains missing or unexpected fields."
        )

    try:
        source = SpectSourceDomain(
            radionuclide=str(source_raw.get("radionuclide") or "").strip(),
            administered_activity_mbq=_number(
                source_raw.get("administered_activity_mbq"),
                "source.administered_activity_mbq",
            ),
            patients_per_week=_number(
                source_raw.get("patients_per_week"),
                "source.patients_per_week",
            ),
            imaging_duration_h=_number(
                source_raw.get("imaging_duration_h"),
                "source.imaging_duration_h",
            ),
        )
    except Exception as exc:
        if isinstance(exc, SpectWorkingProjectStateError):
            raise
        raise SpectWorkingProjectStateError(str(exc)) from exc

    state = SpectWorkingProjectState(source=source, physics_freeze=dict(freeze))
    if (schema, version) == (
        SPECT_WORKING_PROJECT_STATE_SCHEMA,
        SPECT_WORKING_PROJECT_STATE_VERSION,
    ) and dict(payload) != spect_working_project_state_to_dict(state):
        raise SpectWorkingProjectStateError(
            "SPECT working-project state is valid but not canonical."
        )
    return state


def new_spect_working_project_state(source: SpectSourceDomain) -> SpectWorkingProjectState:
    return SpectWorkingProjectState(
        source=source,
        physics_freeze=current_spect_calculation_physics_freeze(),
    )


def get_room_spect_working_state(room: Any) -> SpectWorkingProjectState | None:
    modality_state = getattr(room, "modality_state", {}) or {}
    if not isinstance(modality_state, Mapping):
        return None
    payload = modality_state.get(SPECT_WORKING_PROJECT_STATE_KEY)
    if payload is None:
        return None
    return spect_working_project_state_from_dict(payload)


def set_room_spect_working_state(room: Any, state: SpectWorkingProjectState) -> None:
    if str(getattr(room, "modality", "") or "").strip().upper() != "SPECT":
        raise SpectWorkingProjectStateError(
            "SPECT working-project state may only be attached to a SPECT room."
        )
    modality_state = dict(getattr(room, "modality_state", {}) or {})
    modality_state[SPECT_WORKING_PROJECT_STATE_KEY] = spect_working_project_state_to_dict(state)
    room.modality_state = modality_state


def validate_project_spect_working_states(project: Any) -> None:
    """Fail closed on malformed/stale SPECT working state during project load."""
    for room in list(getattr(project, "rooms", []) or []):
        modality_state = getattr(room, "modality_state", {}) or {}
        if not isinstance(modality_state, Mapping):
            continue
        if SPECT_WORKING_PROJECT_STATE_KEY not in modality_state:
            continue
        if str(getattr(room, "modality", "") or "").strip().upper() != "SPECT":
            raise SpectWorkingProjectStateError(
                f"{getattr(room, 'name', 'Room')}: SPECT working state is attached to a non-SPECT room."
            )
        get_room_spect_working_state(room)
