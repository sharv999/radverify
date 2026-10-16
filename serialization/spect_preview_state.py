"""Separate non-production persistence contract for the SPECT UI preview.

Step 14 adds a canonical SHA-256 integrity digest to the dedicated preview
payload. The payload remains deliberately excluded from normal Project/Room
serialization, Results, reports, and production modality dispatch.

Schema versions 1-3 remain readable. New Step 15 saves use schema version 4,
carry physics provenance/compatibility metadata, and require a matching digest.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from engine.spect_preview_compatibility import (
    SpectPreviewCompatibilityError,
    current_spect_preview_physics_compatibility,
    validate_spect_preview_physics_compatibility,
)

SPECT_PREVIEW_STATE_SCHEMA = "radshield_spect_ui_preview_state_v1"
SPECT_PREVIEW_STATE_VERSION = 4
SPECT_PREVIEW_STATE_BASELINE = "spect-ui-preview-v9-physics-compatibility"

SPECT_PREVIEW_STATE_V3_VERSION = 3
SPECT_PREVIEW_STATE_V3_BASELINE = "spect-ui-preview-v8-payload-integrity"
SPECT_PREVIEW_FILE_EXTENSION = ".spectpreview.json"

SPECT_PREVIEW_STATE_V2_VERSION = 2
SPECT_PREVIEW_STATE_V2_BASELINE = "spect-ui-preview-v7-persisted-source-position"
SPECT_PREVIEW_STATE_LEGACY_VERSION = 1
SPECT_PREVIEW_STATE_LEGACY_BASELINE = "spect-ui-preview-v4-dedicated-save-load"


class SpectPreviewStateError(ValueError):
    """Raised when a SPECT preview-state payload is invalid."""


SPECT_PREVIEW_COMPATIBILITY_CURRENT = "current"
SPECT_PREVIEW_COMPATIBILITY_LEGACY = "legacy_compatible"


@dataclass(frozen=True)
class SpectPreviewLoadResult:
    """Validated preview snapshot plus presentation-only compatibility status."""

    snapshot: "SpectPreviewStateSnapshot"
    compatibility_status: str
    schema_version: int
    message: str


def _canonical_room_name(value: Any) -> str:
    if not isinstance(value, str):
        raise SpectPreviewStateError("room_name must be a string.")
    if not value or value != value.strip():
        raise SpectPreviewStateError("room_name must be non-empty and have no surrounding whitespace.")
    return value


def _canonical_coordinate_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise SpectPreviewStateError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise SpectPreviewStateError(f"{name} must be non-empty and have no surrounding whitespace.")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise SpectPreviewStateError(f"{name} must be a finite numeric string.") from exc
    if not number.is_finite():
        raise SpectPreviewStateError(f"{name} must be finite.")
    if number < 0:
        raise SpectPreviewStateError(f"{name} must be non-negative.")
    if number == 0:
        return "0"
    canonical = format(number.normalize(), "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    return canonical


@dataclass(frozen=True)
class SpectPreviewRoomPositionSnapshot:
    """Raw non-production preview source coordinates for one named room."""

    room_name: str
    source_x_m: str
    source_y_m: str

    def __post_init__(self) -> None:
        room_name = _canonical_room_name(self.room_name)
        source_x_m = _canonical_coordinate_text("source_x_m", self.source_x_m)
        source_y_m = _canonical_coordinate_text("source_y_m", self.source_y_m)
        object.__setattr__(self, "room_name", room_name)
        object.__setattr__(self, "source_x_m", source_x_m)
        object.__setattr__(self, "source_y_m", source_y_m)


@dataclass(frozen=True)
class SpectPreviewStateSnapshot:
    """Dedicated non-production source inputs and preview room positions."""

    administered_activity_mbq: str
    patients_per_week: str
    imaging_duration_h: str
    room_positions: tuple[SpectPreviewRoomPositionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "administered_activity_mbq",
            "patients_per_week",
            "imaging_duration_h",
        ):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise SpectPreviewStateError(f"{name} must be a string.")
            if value == "":
                raise SpectPreviewStateError(f"{name} must not be empty.")

        if not isinstance(self.room_positions, tuple):
            raise SpectPreviewStateError("room_positions must be a tuple.")
        names: set[str] = set()
        previous: str | None = None
        for position in self.room_positions:
            if not isinstance(position, SpectPreviewRoomPositionSnapshot):
                raise SpectPreviewStateError(
                    "room_positions must contain SpectPreviewRoomPositionSnapshot values."
                )
            key = position.room_name.casefold()
            if key in names:
                raise SpectPreviewStateError(
                    f"Duplicate SPECT preview room position {position.room_name!r}."
                )
            if previous is not None and key < previous:
                raise SpectPreviewStateError("room_positions must use canonical room-name order.")
            names.add(key)
            previous = key


def _source_inputs_to_dict(state: SpectPreviewStateSnapshot) -> dict[str, str]:
    return {
        "administered_activity_mbq": state.administered_activity_mbq,
        "patients_per_week": state.patients_per_week,
        "imaging_duration_h": state.imaging_duration_h,
    }


def _state_payload_without_integrity(
    state: SpectPreviewStateSnapshot,
    *,
    schema_version: int = SPECT_PREVIEW_STATE_VERSION,
    preview_baseline: str = SPECT_PREVIEW_STATE_BASELINE,
    include_physics_compatibility: bool = True,
) -> dict[str, Any]:
    payload = {
        "schema": SPECT_PREVIEW_STATE_SCHEMA,
        "schema_version": schema_version,
        "preview_baseline": preview_baseline,
        "production_eligible": False,
        "normal_project_state": False,
        "source_inputs": _source_inputs_to_dict(state),
        "preview_geometry": {
            "room_positions": [
                {
                    "room_name": position.room_name,
                    "source_x_m": position.source_x_m,
                    "source_y_m": position.source_y_m,
                }
                for position in state.room_positions
            ]
        },
    }
    if include_physics_compatibility:
        payload["physics_compatibility"] = current_spect_preview_physics_compatibility()
    return payload


def _canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        text = json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SpectPreviewStateError(
            "SPECT preview payload cannot be canonicalized for integrity checking."
        ) from exc
    return text.encode("utf-8")


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()


def spect_preview_state_to_dict(state: SpectPreviewStateSnapshot) -> dict[str, Any]:
    if not isinstance(state, SpectPreviewStateSnapshot):
        raise SpectPreviewStateError("state must be a SpectPreviewStateSnapshot.")
    payload = _state_payload_without_integrity(state)
    payload["integrity"] = {
        "algorithm": "sha256",
        "payload_sha256": _payload_sha256(payload),
    }
    return payload


def _validate_common_nonproduction_flags(payload: Mapping[str, Any]) -> None:
    if payload.get("production_eligible") is not False:
        raise SpectPreviewStateError("SPECT preview state must remain explicitly non-production.")
    if payload.get("normal_project_state") is not False:
        raise SpectPreviewStateError("SPECT preview state must remain outside normal project state.")


def _source_snapshot_from_payload(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    raw = payload.get("source_inputs")
    if not isinstance(raw, Mapping):
        raise SpectPreviewStateError("SPECT preview source_inputs must be an object.")
    expected_keys = {"administered_activity_mbq", "patients_per_week", "imaging_duration_h"}
    if set(raw) != expected_keys:
        raise SpectPreviewStateError("SPECT preview source_inputs is not canonical.")
    values = (
        raw.get("administered_activity_mbq"),
        raw.get("patients_per_week"),
        raw.get("imaging_duration_h"),
    )
    for name, value in zip(
        ("administered_activity_mbq", "patients_per_week", "imaging_duration_h"), values
    ):
        if not isinstance(value, str):
            raise SpectPreviewStateError(f"{name} must be a string.")
        if value == "":
            raise SpectPreviewStateError(f"{name} must not be empty.")
    return values


def _room_positions_from_payload(payload: Mapping[str, Any]) -> tuple[SpectPreviewRoomPositionSnapshot, ...]:
    geometry = payload.get("preview_geometry")
    if not isinstance(geometry, Mapping):
        raise SpectPreviewStateError("SPECT preview preview_geometry must be an object.")
    if set(geometry) != {"room_positions"}:
        raise SpectPreviewStateError("SPECT preview preview_geometry is not canonical.")
    raw_positions = geometry.get("room_positions")
    if not isinstance(raw_positions, list):
        raise SpectPreviewStateError("SPECT preview room_positions must be an array.")

    positions: list[SpectPreviewRoomPositionSnapshot] = []
    for raw in raw_positions:
        if not isinstance(raw, Mapping):
            raise SpectPreviewStateError("Each SPECT preview room position must be an object.")
        position = SpectPreviewRoomPositionSnapshot(
            room_name=raw.get("room_name"),
            source_x_m=raw.get("source_x_m"),
            source_y_m=raw.get("source_y_m"),
        )
        if dict(raw) != {
            "room_name": position.room_name,
            "source_x_m": position.source_x_m,
            "source_y_m": position.source_y_m,
        }:
            raise SpectPreviewStateError("SPECT preview room position is not canonical.")
        positions.append(position)
    return tuple(positions)




def _validate_v3_integrity(payload: Mapping[str, Any]) -> None:
    integrity = payload.get("integrity")
    if not isinstance(integrity, Mapping):
        raise SpectPreviewStateError("SPECT preview integrity metadata is required for schema v3.")
    if set(integrity) != {"algorithm", "payload_sha256"}:
        raise SpectPreviewStateError("SPECT preview integrity metadata is not canonical.")
    if integrity.get("algorithm") != "sha256":
        raise SpectPreviewStateError("Unsupported SPECT preview integrity algorithm.")
    digest = integrity.get("payload_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SpectPreviewStateError("SPECT preview payload_sha256 must be 64 lowercase hex characters.")

    unsigned = dict(payload)
    unsigned.pop("integrity", None)
    expected = _payload_sha256(unsigned)
    if not hmac.compare_digest(digest, expected):
        raise SpectPreviewStateError(
            "SPECT preview integrity check failed: payload SHA-256 does not match."
        )


def _v2_state_from_dict(payload: Mapping[str, Any]) -> SpectPreviewStateSnapshot:
    if payload.get("preview_baseline") != SPECT_PREVIEW_STATE_V2_BASELINE:
        raise SpectPreviewStateError(
            f"Unsupported SPECT preview baseline {payload.get('preview_baseline')!r}."
        )
    _validate_common_nonproduction_flags(payload)
    activity, patients, duration = _source_snapshot_from_payload(payload)
    state = SpectPreviewStateSnapshot(
        administered_activity_mbq=activity,
        patients_per_week=patients,
        imaging_duration_h=duration,
        room_positions=_room_positions_from_payload(payload),
    )
    expected = _state_payload_without_integrity(
        state,
        schema_version=SPECT_PREVIEW_STATE_V2_VERSION,
        preview_baseline=SPECT_PREVIEW_STATE_V2_BASELINE,
        include_physics_compatibility=False,
    )
    if dict(payload) != expected:
        raise SpectPreviewStateError("SPECT preview v2 state is not canonical after validation.")
    return state


def _legacy_state_from_dict(payload: Mapping[str, Any]) -> SpectPreviewStateSnapshot:
    if payload.get("preview_baseline") != SPECT_PREVIEW_STATE_LEGACY_BASELINE:
        raise SpectPreviewStateError(
            f"Unsupported SPECT preview baseline {payload.get('preview_baseline')!r}."
        )
    _validate_common_nonproduction_flags(payload)
    activity, patients, duration = _source_snapshot_from_payload(payload)
    expected = {
        "schema": SPECT_PREVIEW_STATE_SCHEMA,
        "schema_version": SPECT_PREVIEW_STATE_LEGACY_VERSION,
        "preview_baseline": SPECT_PREVIEW_STATE_LEGACY_BASELINE,
        "production_eligible": False,
        "normal_project_state": False,
        "source_inputs": {
            "administered_activity_mbq": activity,
            "patients_per_week": patients,
            "imaging_duration_h": duration,
        },
    }
    if dict(payload) != expected:
        raise SpectPreviewStateError("Legacy SPECT preview state is not canonical after validation.")
    return SpectPreviewStateSnapshot(activity, patients, duration, ())



def _v3_state_from_dict(payload: Mapping[str, Any]) -> SpectPreviewStateSnapshot:
    if payload.get("preview_baseline") != SPECT_PREVIEW_STATE_V3_BASELINE:
        raise SpectPreviewStateError(
            f"Unsupported SPECT preview baseline {payload.get('preview_baseline')!r}."
        )
    _validate_v3_integrity(payload)
    _validate_common_nonproduction_flags(payload)
    activity, patients, duration = _source_snapshot_from_payload(payload)
    state = SpectPreviewStateSnapshot(
        administered_activity_mbq=activity,
        patients_per_week=patients,
        imaging_duration_h=duration,
        room_positions=_room_positions_from_payload(payload),
    )
    expected = _state_payload_without_integrity(
        state,
        schema_version=SPECT_PREVIEW_STATE_V3_VERSION,
        preview_baseline=SPECT_PREVIEW_STATE_V3_BASELINE,
        include_physics_compatibility=False,
    )
    expected["integrity"] = {
        "algorithm": "sha256",
        "payload_sha256": _payload_sha256(expected),
    }
    if dict(payload) != expected:
        raise SpectPreviewStateError("SPECT preview v3 state is not canonical after validation.")
    return state


def spect_preview_state_from_dict(payload: Mapping[str, Any]) -> SpectPreviewStateSnapshot:
    if not isinstance(payload, Mapping):
        raise SpectPreviewStateError("SPECT preview state must be an object.")
    if payload.get("schema") != SPECT_PREVIEW_STATE_SCHEMA:
        raise SpectPreviewStateError(
            f"Unsupported SPECT preview schema {payload.get('schema')!r}."
        )

    version = payload.get("schema_version")
    if version == SPECT_PREVIEW_STATE_LEGACY_VERSION:
        return _legacy_state_from_dict(payload)
    if version == SPECT_PREVIEW_STATE_V2_VERSION:
        return _v2_state_from_dict(payload)
    if version == SPECT_PREVIEW_STATE_V3_VERSION:
        return _v3_state_from_dict(payload)
    if version != SPECT_PREVIEW_STATE_VERSION:
        raise SpectPreviewStateError(f"Unsupported SPECT preview schema version {version!r}.")
    if payload.get("preview_baseline") != SPECT_PREVIEW_STATE_BASELINE:
        raise SpectPreviewStateError(
            f"Unsupported SPECT preview baseline {payload.get('preview_baseline')!r}."
        )

    _validate_v3_integrity(payload)
    try:
        validate_spect_preview_physics_compatibility(payload.get("physics_compatibility"))
    except SpectPreviewCompatibilityError as exc:
        raise SpectPreviewStateError(str(exc)) from exc
    _validate_common_nonproduction_flags(payload)
    activity, patients, duration = _source_snapshot_from_payload(payload)
    state = SpectPreviewStateSnapshot(
        administered_activity_mbq=activity,
        patients_per_week=patients,
        imaging_duration_h=duration,
        room_positions=_room_positions_from_payload(payload),
    )
    if dict(payload) != spect_preview_state_to_dict(state):
        raise SpectPreviewStateError("SPECT preview state is not canonical after validation.")
    return state


def save_spect_preview_state(path: str | Path, state: SpectPreviewStateSnapshot) -> Path:
    destination = Path(path)
    payload = spect_preview_state_to_dict(state)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def _load_spect_preview_payload(path: str | Path) -> tuple[Path, Mapping[str, Any]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectPreviewStateError(f"Unable to load SPECT preview state {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise SpectPreviewStateError("SPECT preview state must be an object.")
    return source, payload


def spect_preview_compatibility_status_for_version(version: Any) -> tuple[str, str]:
    """Classify an already-validated preview schema for UI presentation only."""

    if version == SPECT_PREVIEW_STATE_VERSION:
        return (
            SPECT_PREVIEW_COMPATIBILITY_CURRENT,
            "Current — physics provenance matches the installed SPECT preview stack.",
        )
    if version in {
        SPECT_PREVIEW_STATE_LEGACY_VERSION,
        SPECT_PREVIEW_STATE_V2_VERSION,
        SPECT_PREVIEW_STATE_V3_VERSION,
    }:
        return (
            SPECT_PREVIEW_COMPATIBILITY_LEGACY,
            f"Legacy-compatible — schema v{version} validated, but predates current physics provenance metadata.",
        )
    raise SpectPreviewStateError(f"Unsupported SPECT preview schema version {version!r}.")


def load_spect_preview_state_with_status(path: str | Path) -> SpectPreviewLoadResult:
    """Load a preview file and expose its compatibility class for the UI.

    Validation remains fail-closed in ``spect_preview_state_from_dict``.  This
    helper adds presentation metadata only and does not enter project state.
    """

    _source, payload = _load_spect_preview_payload(path)
    snapshot = spect_preview_state_from_dict(payload)
    version = payload.get("schema_version")
    status, message = spect_preview_compatibility_status_for_version(version)
    return SpectPreviewLoadResult(
        snapshot=snapshot,
        compatibility_status=status,
        schema_version=int(version),
        message=message,
    )


def load_spect_preview_state(path: str | Path) -> SpectPreviewStateSnapshot:
    _source, payload = _load_spect_preview_payload(path)
    return spect_preview_state_from_dict(payload)
