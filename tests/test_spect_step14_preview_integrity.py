"""Tests for SPECT Step 14 preview payload integrity / tamper detection."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from serialization.spect_preview_state import (
    SPECT_PREVIEW_STATE_BASELINE,
    SPECT_PREVIEW_STATE_SCHEMA,
    SPECT_PREVIEW_STATE_V2_BASELINE,
    SPECT_PREVIEW_STATE_V2_VERSION,
    SPECT_PREVIEW_STATE_V3_BASELINE,
    SPECT_PREVIEW_STATE_V3_VERSION,
    SPECT_PREVIEW_STATE_VERSION,
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    load_spect_preview_state,
    save_spect_preview_state,
    spect_preview_state_from_dict,
    spect_preview_state_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]


def _state() -> SpectPreviewStateSnapshot:
    return SpectPreviewStateSnapshot(
        "600",
        "20",
        "0.5",
        room_positions=(
            SpectPreviewRoomPositionSnapshot("Room A", "1.25", "2.5"),
            SpectPreviewRoomPositionSnapshot("Room B", "3", "4"),
        ),
    )


def test_step14_v3_contract_has_mandatory_sha256_integrity_metadata():
    payload = spect_preview_state_to_dict(_state())

    assert SPECT_PREVIEW_STATE_VERSION == 4
    assert SPECT_PREVIEW_STATE_V3_VERSION == 3
    assert SPECT_PREVIEW_STATE_V3_BASELINE == "spect-ui-preview-v8-payload-integrity"
    assert payload["schema"] == SPECT_PREVIEW_STATE_SCHEMA
    assert payload["schema_version"] == 4
    assert payload["integrity"]["algorithm"] == "sha256"
    digest = payload["integrity"]["payload_sha256"]
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert spect_preview_state_from_dict(payload) == _state()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p["source_inputs"].__setitem__("patients_per_week", "21"),
        lambda p: p["preview_geometry"]["room_positions"][0].__setitem__("source_x_m", "1.5"),
        lambda p: p.__setitem__("production_eligible", True),
        lambda p: p.__setitem__("normal_project_state", True),
        lambda p: p.__setitem__("preview_baseline", "tampered"),
        lambda p: p.__setitem__("unexpected", "field"),
    ],
)
def test_step14_any_unsigned_payload_mutation_fails_closed(mutator):
    payload = spect_preview_state_to_dict(_state())
    mutator(payload)
    with pytest.raises(SpectPreviewStateError):
        spect_preview_state_from_dict(payload)


def test_step14_removing_or_altering_integrity_metadata_fails_closed():
    payload = spect_preview_state_to_dict(_state())
    payload.pop("integrity")
    with pytest.raises(SpectPreviewStateError, match="integrity metadata is required"):
        spect_preview_state_from_dict(payload)

    payload = spect_preview_state_to_dict(_state())
    payload["integrity"]["payload_sha256"] = "0" * 64
    with pytest.raises(SpectPreviewStateError, match="integrity check failed"):
        spect_preview_state_from_dict(payload)

    payload = spect_preview_state_to_dict(_state())
    payload["integrity"]["algorithm"] = "SHA-256"
    with pytest.raises(SpectPreviewStateError, match="integrity algorithm"):
        spect_preview_state_from_dict(payload)


def test_step14_digest_is_canonical_and_independent_of_json_key_order():
    payload = spect_preview_state_to_dict(_state())
    reordered = {key: payload[key] for key in reversed(list(payload))}
    reordered["source_inputs"] = {
        key: payload["source_inputs"][key]
        for key in reversed(list(payload["source_inputs"]))
    }
    assert spect_preview_state_from_dict(reordered) == _state()


def test_step14_save_load_save_remains_byte_deterministic_with_integrity(tmp_path):
    first = tmp_path / "first.spectpreview.json"
    second = tmp_path / "second.spectpreview.json"
    save_spect_preview_state(first, _state())
    save_spect_preview_state(second, load_spect_preview_state(first))
    assert first.read_bytes() == second.read_bytes()

    on_disk = json.loads(first.read_text(encoding="utf-8"))
    assert on_disk["integrity"]["payload_sha256"] == spect_preview_state_to_dict(_state())["integrity"]["payload_sha256"]


def test_step14_existing_hardened_v2_files_remain_readable():
    state = _state()
    current = spect_preview_state_to_dict(state)
    payload = deepcopy(current)
    payload.pop("integrity")
    payload.pop("physics_compatibility")
    payload["schema_version"] = SPECT_PREVIEW_STATE_V2_VERSION
    payload["preview_baseline"] = SPECT_PREVIEW_STATE_V2_BASELINE

    assert spect_preview_state_from_dict(payload) == state


def test_step14_v2_cannot_claim_v3_without_integrity():
    state = _state()
    current = spect_preview_state_to_dict(state)
    current.pop("integrity")
    with pytest.raises(SpectPreviewStateError, match="integrity metadata is required"):
        spect_preview_state_from_dict(current)


def test_step14_integrity_tokens_stay_out_of_normal_project_report_and_engine_paths():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "payload_sha256" not in text
        assert "spect-ui-preview-v8-payload-integrity" not in text
