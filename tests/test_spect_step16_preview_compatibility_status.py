"""Tests for SPECT Step 16 preview compatibility status presentation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from serialization.spect_preview_state import (
    SPECT_PREVIEW_COMPATIBILITY_CURRENT,
    SPECT_PREVIEW_COMPATIBILITY_LEGACY,
    SPECT_PREVIEW_STATE_V3_BASELINE,
    SPECT_PREVIEW_STATE_V3_VERSION,
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    load_spect_preview_state_with_status,
    save_spect_preview_state,
    spect_preview_state_to_dict,
)
from tabs import spect_preview_panel

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self._value = value
    def get(self):
        return self._value
    def set(self, value):
        self._value = value


def _state():
    return SpectPreviewStateSnapshot(
        "600",
        "20",
        "0.5",
        room_positions=(SpectPreviewRoomPositionSnapshot("Room A", "1", "2"),),
    )


def _rehash(payload: dict) -> None:
    unsigned = deepcopy(payload)
    unsigned.pop("integrity", None)
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    payload["integrity"]["payload_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def test_step16_current_v4_file_surfaces_current_status(tmp_path):
    path = tmp_path / "current.spectpreview.json"
    save_spect_preview_state(path, _state())

    result = load_spect_preview_state_with_status(path)

    assert result.snapshot == _state()
    assert result.compatibility_status == SPECT_PREVIEW_COMPATIBILITY_CURRENT
    assert result.schema_version == 4
    assert result.message.startswith("Current")
    assert "physics provenance matches" in result.message


def test_step16_validated_v3_file_surfaces_legacy_compatible_status(tmp_path):
    payload = spect_preview_state_to_dict(_state())
    payload.pop("physics_compatibility")
    payload["schema_version"] = SPECT_PREVIEW_STATE_V3_VERSION
    payload["preview_baseline"] = SPECT_PREVIEW_STATE_V3_BASELINE
    _rehash(payload)
    path = tmp_path / "legacy.spectpreview.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = load_spect_preview_state_with_status(path)

    assert result.snapshot == _state()
    assert result.compatibility_status == SPECT_PREVIEW_COMPATIBILITY_LEGACY
    assert result.schema_version == 3
    assert result.message.startswith("Legacy-compatible")
    assert "predates current physics provenance metadata" in result.message


def test_step16_incompatible_v4_file_remains_fail_closed(tmp_path):
    payload = spect_preview_state_to_dict(_state())
    payload["physics_compatibility"]["model_contracts"][
        "barrier_schedule_contract_version"
    ] = 999
    _rehash(payload)
    path = tmp_path / "incompatible.spectpreview.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SpectPreviewStateError, match="different SPECT dataset or model revision"):
        load_spect_preview_state_with_status(path)


def test_step16_ui_marks_rejected_load_without_applying_preview_state(monkeypatch):
    app = SimpleNamespace(spect_preview_compatibility_status_var=_Var())
    applied = []

    monkeypatch.setattr(
        spect_preview_panel.filedialog,
        "askopenfilename",
        lambda **_kwargs: "bad.spectpreview.json",
    )
    monkeypatch.setattr(
        spect_preview_panel,
        "load_spect_preview_state_with_status",
        lambda _path: (_ for _ in ()).throw(
            SpectPreviewStateError(
                "SPECT preview physics compatibility check failed: "
                "the snapshot was created against a different SPECT dataset or model revision."
            )
        ),
    )
    monkeypatch.setattr(
        spect_preview_panel,
        "apply_spect_preview_snapshot",
        lambda *_args, **_kwargs: applied.append(True),
    )
    monkeypatch.setattr(spect_preview_panel.messagebox, "showerror", lambda *_args, **_kwargs: None)

    spect_preview_panel.load_spect_preview_from_ui(app)

    assert applied == []
    assert app.spect_preview_compatibility_status_var.get().startswith("Rejected")
    assert "different SPECT dataset or model revision" in app.spect_preview_compatibility_status_var.get()


def test_step16_compatibility_ui_state_stays_out_of_project_report_and_production_paths():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "spect_preview_compatibility_status_var" not in text
        assert "Legacy-compatible" not in text
