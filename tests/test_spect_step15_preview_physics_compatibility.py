"""Tests for SPECT Step 15 preview physics provenance / compatibility metadata."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from engine.spect_preview_compatibility import current_spect_preview_physics_compatibility
from serialization.spect_preview_state import (
    SPECT_PREVIEW_STATE_BASELINE,
    SPECT_PREVIEW_STATE_V3_BASELINE,
    SPECT_PREVIEW_STATE_V3_VERSION,
    SPECT_PREVIEW_STATE_VERSION,
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    spect_preview_state_from_dict,
    spect_preview_state_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]


def _state() -> SpectPreviewStateSnapshot:
    return SpectPreviewStateSnapshot(
        "600", "20", "0.5",
        room_positions=(SpectPreviewRoomPositionSnapshot("Room A", "1.25", "2.5"),),
    )


def _rehash(payload: dict) -> None:
    unsigned = deepcopy(payload)
    unsigned.pop("integrity", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    payload["integrity"]["payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_step15_v4_records_current_spect_dataset_and_model_provenance():
    payload = spect_preview_state_to_dict(_state())
    compat = payload["physics_compatibility"]

    assert SPECT_PREVIEW_STATE_VERSION == 4
    assert SPECT_PREVIEW_STATE_BASELINE == "spect-ui-preview-v9-physics-compatibility"
    assert compat == current_spect_preview_physics_compatibility()
    assert set(compat) == {
        "contract_version",
        "radionuclide_dataset",
        "attenuation_dataset",
        "practical_transmission_dataset",
        "model_contracts",
    }
    assert len(compat["radionuclide_dataset"]["file_sha256"]) == 64
    assert len(compat["attenuation_dataset"]["records_sha256"]) == 64
    assert len(compat["practical_transmission_dataset"]["records_sha256"]) == 64
    assert spect_preview_state_from_dict(payload) == _state()


@pytest.mark.parametrize(
    "path,new_value",
    [
        (("radionuclide_dataset", "revision"), "different-revision"),
        (("attenuation_dataset", "records_sha256"), "0" * 64),
        (("practical_transmission_dataset", "revision"), "different-revision"),
        (("model_contracts", "barrier_schedule_contract_version"), 999),
    ],
)
def test_step15_rehashed_but_physics_incompatible_v4_payload_fails_closed(path, new_value):
    payload = spect_preview_state_to_dict(_state())
    payload["physics_compatibility"][path[0]][path[1]] = new_value
    _rehash(payload)
    with pytest.raises(SpectPreviewStateError, match="different SPECT dataset or model revision"):
        spect_preview_state_from_dict(payload)


def test_step15_missing_or_extra_compatibility_metadata_fails_closed_even_if_rehashed():
    payload = spect_preview_state_to_dict(_state())
    payload.pop("physics_compatibility")
    _rehash(payload)
    with pytest.raises(SpectPreviewStateError, match="physics_compatibility"):
        spect_preview_state_from_dict(payload)

    payload = spect_preview_state_to_dict(_state())
    payload["physics_compatibility"]["unexpected"] = "field"
    _rehash(payload)
    with pytest.raises(SpectPreviewStateError, match="different SPECT dataset or model revision"):
        spect_preview_state_from_dict(payload)


def test_step15_existing_schema_v3_integrity_files_remain_readable_without_compatibility_metadata():
    current = spect_preview_state_to_dict(_state())
    legacy = deepcopy(current)
    legacy.pop("physics_compatibility")
    legacy["schema_version"] = SPECT_PREVIEW_STATE_V3_VERSION
    legacy["preview_baseline"] = SPECT_PREVIEW_STATE_V3_BASELINE
    _rehash(legacy)

    assert spect_preview_state_from_dict(legacy) == _state()


def test_step15_compatibility_metadata_is_covered_by_integrity_digest():
    payload = spect_preview_state_to_dict(_state())
    payload["physics_compatibility"]["radionuclide_dataset"]["revision"] = "tampered"
    with pytest.raises(SpectPreviewStateError, match="integrity check failed"):
        spect_preview_state_from_dict(payload)


def test_step15_preview_provenance_tokens_stay_out_of_normal_project_report_paths():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "physics_compatibility" not in text
        assert "spect-ui-preview-v9-physics-compatibility" not in text
