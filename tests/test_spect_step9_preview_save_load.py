"""Tests for SPECT Step 9 dedicated non-production preview save/load."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from serialization.spect_preview_state import (
    SPECT_PREVIEW_FILE_EXTENSION,
    SPECT_PREVIEW_STATE_BASELINE,
    SPECT_PREVIEW_STATE_LEGACY_BASELINE,
    SPECT_PREVIEW_STATE_LEGACY_VERSION,
    SPECT_PREVIEW_STATE_SCHEMA,
    SPECT_PREVIEW_STATE_VERSION,
    SpectPreviewStateError,
    SpectPreviewStateSnapshot,
    load_spect_preview_state,
    save_spect_preview_state,
    spect_preview_state_from_dict,
    spect_preview_state_to_dict,
)
from services.project_io import read_project_payload
from tabs.spect_preview_panel import (
    SPECT_UI_PERSISTED_PREVIEW_BASELINE,
    SPECT_UI_PERSISTED_PREVIEW_CONTRACT_VERSION,
    SpectPreviewSessionState,
    apply_spect_preview_snapshot,
    get_spect_preview_session_state,
    spect_preview_snapshot_from_app,
)


ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def _app(activity="600", patients="20", duration="0.5"):
    return SimpleNamespace(
        spect_preview_activity_var=_Var(activity),
        spect_preview_patients_var=_Var(patients),
        spect_preview_duration_var=_Var(duration),
    )


def test_step9_contract_and_extension_are_explicitly_preview_only():
    assert SPECT_UI_PERSISTED_PREVIEW_CONTRACT_VERSION == 4
    assert SPECT_UI_PERSISTED_PREVIEW_BASELINE == "spect-ui-preview-v4-dedicated-save-load"
    assert SPECT_PREVIEW_STATE_SCHEMA == "radshield_spect_ui_preview_state_v1"
    assert SPECT_PREVIEW_STATE_LEGACY_VERSION == 1
    assert SPECT_PREVIEW_STATE_LEGACY_BASELINE == SPECT_UI_PERSISTED_PREVIEW_BASELINE
    assert SPECT_PREVIEW_STATE_VERSION == 4
    assert SPECT_PREVIEW_STATE_BASELINE == "spect-ui-preview-v9-physics-compatibility"
    assert SPECT_PREVIEW_FILE_EXTENSION == ".spectpreview.json"


def test_step9_round_trip_preserves_raw_preview_strings(tmp_path):
    state = SpectPreviewStateSnapshot("abc", "27", "0.80")
    payload = spect_preview_state_to_dict(state)

    assert payload["production_eligible"] is False
    assert payload["normal_project_state"] is False
    assert payload["source_inputs"]["administered_activity_mbq"] == "abc"

    restored = spect_preview_state_from_dict(payload)
    assert restored == state

    path = tmp_path / "case.spectpreview.json"
    assert save_spect_preview_state(path, state) == path
    assert load_spect_preview_state(path) == state


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("schema_version", 99),
        ("preview_baseline", "wrong"),
        ("production_eligible", True),
        ("normal_project_state", True),
    ],
)
def test_step9_rejects_noncanonical_or_production_payloads(field, value):
    payload = spect_preview_state_to_dict(SpectPreviewStateSnapshot("600", "20", "0.5"))
    payload[field] = value
    with pytest.raises(SpectPreviewStateError):
        spect_preview_state_from_dict(payload)


def test_step9_snapshot_capture_and_restore_touch_only_preview_session_and_vars():
    app = _app("725", "24", "0.75")
    snapshot = spect_preview_snapshot_from_app(app)
    assert snapshot == SpectPreviewStateSnapshot("725", "24", "0.75")

    app.project = SimpleNamespace(project_name="unchanged")
    before_project = app.project
    apply_spect_preview_snapshot(app, SpectPreviewStateSnapshot("900", "30", "1.0"))

    state = get_spect_preview_session_state(app)
    assert state == SpectPreviewSessionState("900", "30", "1.0")
    assert app.spect_preview_activity_var.get() == "900"
    assert app.spect_preview_patients_var.get() == "30"
    assert app.spect_preview_duration_var.get() == "1.0"
    assert app.project is before_project


def test_step9_normal_project_open_rejects_spect_preview_with_specific_guidance(tmp_path):
    path = tmp_path / "case.spectpreview.json"
    save_spect_preview_state(path, SpectPreviewStateSnapshot("600", "20", "0.5"))

    with pytest.raises(ValueError) as exc_info:
        read_project_payload(path)

    message = str(exc_info.value)
    assert "SPECT development preview snapshot" in message
    assert "SPECT Preview panel" in message
    assert "Unsupported project schema version" not in message


def test_step9_preview_payload_is_not_part_of_normal_project_serializer_or_reports():
    forbidden_paths = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "app.py",
    ]
    forbidden_paths += list((ROOT / "reports").glob("*.py"))

    tokens = (
        "SPECT_PREVIEW_STATE_SCHEMA",
        "SpectPreviewStateSnapshot",
        ".spectpreview.json",
    )
    for path in forbidden_paths:
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text


def test_step9_panel_exposes_dedicated_save_load_but_retains_nonproduction_wording():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    assert "Save SPECT Preview..." in panel
    assert "Load SPECT Preview..." in panel
    assert ".spectpreview.json" in panel
    assert "normal project save" in panel
    assert "production" in panel.lower()
