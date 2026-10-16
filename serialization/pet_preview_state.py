"""Separate non-production persistence contract for the PET UI preview.

The v2 envelope stores one validated PET patient/source workload, one PET
patient/source position, and a replay snapshot of the room-derived barrier
requests. It remains outside the production project schema and report path.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from geometry.pet_preview_position import PetPreviewPosition
from serialization.pet_calculation_request_contract import (
    PetCalculationRequestEnvelope,
    PetCalculationRequestSerializationError,
    pet_calculation_request_from_dict,
    pet_calculation_request_to_dict,
)

PET_PREVIEW_STATE_SCHEMA = "radshield_pet_ui_preview_state_v2"
PET_PREVIEW_STATE_VERSION = 2
PET_PREVIEW_STATE_BASELINE = "pet-ui-preview-v10-ui-freeze"
PET_PREVIEW_FILE_EXTENSION = ".petpreview.json"


class PetPreviewStateError(ValueError):
    """Raised when a PET preview-state file is invalid."""


@dataclass(frozen=True)
class PetPreviewStateSnapshot:
    """One non-production PET source per room preview state."""

    request: PetCalculationRequestEnvelope
    position: PetPreviewPosition

    def __post_init__(self) -> None:
        if not isinstance(self.request, PetCalculationRequestEnvelope):
            raise PetPreviewStateError("request must be a validated PET calculation request.")
        if not isinstance(self.position, PetPreviewPosition):
            raise PetPreviewStateError("position must be a PetPreviewPosition.")


def pet_preview_state_to_dict(state: PetPreviewStateSnapshot) -> dict[str, Any]:
    """Serialize validated single-source preview inputs into the v2 envelope."""
    if not isinstance(state, PetPreviewStateSnapshot):
        raise PetPreviewStateError("state must be a PetPreviewStateSnapshot.")
    return {
        "schema": PET_PREVIEW_STATE_SCHEMA,
        "schema_version": PET_PREVIEW_STATE_VERSION,
        "preview_baseline": PET_PREVIEW_STATE_BASELINE,
        "production_eligible": False,
        "single_source_per_room": True,
        "position": {
            "x_from_west_m": float(state.position.x_from_west_m),
            "y_from_south_m": float(state.position.y_from_south_m),
            "height_above_ffl_m": float(state.position.height_above_ffl_m),
        },
        "request": pet_calculation_request_to_dict(state.request),
    }


def pet_preview_state_from_dict(payload: Mapping[str, Any]) -> PetPreviewStateSnapshot:
    """Validate and reconstruct a canonical v2 preview-state payload."""
    if not isinstance(payload, Mapping):
        raise PetPreviewStateError("PET preview state must be an object.")
    if payload.get("schema") != PET_PREVIEW_STATE_SCHEMA:
        raise PetPreviewStateError(f"Unsupported PET preview schema {payload.get('schema')!r}.")
    if payload.get("schema_version") != PET_PREVIEW_STATE_VERSION:
        raise PetPreviewStateError(
            f"Unsupported PET preview schema version {payload.get('schema_version')!r}."
        )
    if payload.get("preview_baseline") != PET_PREVIEW_STATE_BASELINE:
        raise PetPreviewStateError(
            f"Unsupported PET preview baseline {payload.get('preview_baseline')!r}."
        )
    if payload.get("production_eligible") is not False:
        raise PetPreviewStateError("PET preview state must remain explicitly non-production.")
    if payload.get("single_source_per_room") is not True:
        raise PetPreviewStateError("PET preview state must contain exactly one source per room.")

    position_payload = payload.get("position")
    if not isinstance(position_payload, Mapping):
        raise PetPreviewStateError("PET preview state position must be an object.")
    try:
        position = PetPreviewPosition(
            x_from_west_m=float(position_payload.get("x_from_west_m")),
            y_from_south_m=float(position_payload.get("y_from_south_m")),
            height_above_ffl_m=float(position_payload.get("height_above_ffl_m")),
        )
    except (TypeError, ValueError) as exc:
        raise PetPreviewStateError("PET preview position values must be numeric.") from exc

    request_payload = payload.get("request")
    if not isinstance(request_payload, Mapping):
        raise PetPreviewStateError("PET preview state request must be an object.")
    try:
        request = pet_calculation_request_from_dict(request_payload)
    except PetCalculationRequestSerializationError as exc:
        raise PetPreviewStateError(str(exc)) from exc
    state = PetPreviewStateSnapshot(request=request, position=position)
    if dict(payload) != pet_preview_state_to_dict(state):
        raise PetPreviewStateError("PET preview state is not canonical after validation.")
    return state


def save_pet_preview_state(path: str | Path, state: PetPreviewStateSnapshot) -> Path:
    """Write a validated preview state atomically to a separate JSON file."""
    destination = Path(path)
    payload = pet_preview_state_to_dict(state)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_pet_preview_state(path: str | Path) -> PetPreviewStateSnapshot:
    """Load and validate a separate PET preview-state file."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetPreviewStateError(f"Unable to load PET preview state {source}: {exc}") from exc
    return pet_preview_state_from_dict(payload)
