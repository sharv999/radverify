import json

import pytest

from geometry.pet_preview_position import PetPreviewPosition
from serialization.pet_preview_state import (
    PET_PREVIEW_FILE_EXTENSION,
    PET_PREVIEW_STATE_BASELINE,
    PetPreviewStateError,
    PetPreviewStateSnapshot,
    load_pet_preview_state,
    pet_preview_state_from_dict,
    pet_preview_state_to_dict,
    save_pet_preview_state,
)
from tabs.pet_preview_panel import build_pet_preview_request_envelope
from tests.test_pet_ui_preview import _barriers, _values


def _state():
    return PetPreviewStateSnapshot(
        request=build_pet_preview_request_envelope(_values(), _barriers()),
        position=PetPreviewPosition(2.25, 3.5, 1.0),
    )


def test_pet_preview_state_round_trip_is_canonical_single_source_and_nonproduction(tmp_path):
    state = _state()
    payload = pet_preview_state_to_dict(state)
    assert payload["preview_baseline"] == PET_PREVIEW_STATE_BASELINE == "pet-ui-preview-v10-ui-freeze"
    assert payload["production_eligible"] is False
    assert payload["single_source_per_room"] is True
    assert payload["position"] == {
        "x_from_west_m": 2.25,
        "y_from_south_m": 3.5,
        "height_above_ffl_m": 1.0,
    }
    assert payload["request"]["production_eligible"] is False

    restored = pet_preview_state_from_dict(payload)
    assert pet_preview_state_to_dict(restored) == payload

    path = tmp_path / f"case{PET_PREVIEW_FILE_EXTENSION}"
    save_pet_preview_state(path, state)
    assert path.is_file()
    assert pet_preview_state_to_dict(load_pet_preview_state(path)) == payload
    json.loads(path.read_text(encoding="utf-8"))


def test_pet_preview_state_rejects_production_multi_source_or_noncanonical_payload():
    payload = pet_preview_state_to_dict(_state())
    payload["production_eligible"] = True
    with pytest.raises(PetPreviewStateError, match="non-production"):
        pet_preview_state_from_dict(payload)

    payload = pet_preview_state_to_dict(_state())
    payload["single_source_per_room"] = False
    with pytest.raises(PetPreviewStateError, match="exactly one source"):
        pet_preview_state_from_dict(payload)

    payload = pet_preview_state_to_dict(_state())
    payload["unexpected"] = "field"
    with pytest.raises(PetPreviewStateError, match="not canonical"):
        pet_preview_state_from_dict(payload)


def test_pet_preview_state_rejects_invalid_request_or_position_data():
    payload = pet_preview_state_to_dict(_state())
    payload["request"]["source"]["residual_activity_factor"] = 1.5
    with pytest.raises(PetPreviewStateError, match="residual_activity_factor"):
        pet_preview_state_from_dict(payload)

    payload = pet_preview_state_to_dict(_state())
    payload["position"]["x_from_west_m"] = "not-a-number"
    with pytest.raises(PetPreviewStateError, match="position values must be numeric"):
        pet_preview_state_from_dict(payload)
