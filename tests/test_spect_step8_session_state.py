"""Tests for SPECT Step 8 session-only preview state retention."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tabs.spect_preview_panel import (
    SPECT_UI_SESSION_PREVIEW_BASELINE,
    SPECT_UI_SESSION_PREVIEW_CONTRACT_VERSION,
    SpectPreviewError,
    SpectPreviewSessionState,
    capture_spect_preview_session_state,
    get_spect_preview_session_state,
    spect_preview_source_from_app,
)


ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def _app_with_vars(activity="600", patients="20", duration="0.5"):
    return SimpleNamespace(
        spect_preview_activity_var=_Var(activity),
        spect_preview_patients_var=_Var(patients),
        spect_preview_duration_var=_Var(duration),
    )


def test_step8_contract_is_session_only_nonproduction_state():
    assert SPECT_UI_SESSION_PREVIEW_CONTRACT_VERSION == 3
    assert SPECT_UI_SESSION_PREVIEW_BASELINE == "spect-ui-preview-v3-session-only-state"


def test_step8_session_state_defaults_match_step7_preview_defaults():
    state = SpectPreviewSessionState()
    assert state.administered_activity_mbq == "600"
    assert state.patients_per_week == "20"
    assert state.imaging_duration_h == "0.5"


def test_step8_session_state_is_created_once_and_owned_only_by_app_instance():
    app = SimpleNamespace()
    first = get_spect_preview_session_state(app)
    first.administered_activity_mbq = "725"
    second = get_spect_preview_session_state(app)
    other = get_spect_preview_session_state(SimpleNamespace())

    assert second is first
    assert second.administered_activity_mbq == "725"
    assert other is not first
    assert other.administered_activity_mbq == "600"


def test_step8_capture_mirrors_raw_entry_values_without_forcing_validation():
    app = _app_with_vars("abc", "27", "0.8")
    state = capture_spect_preview_session_state(app)

    assert state.administered_activity_mbq == "abc"
    assert state.patients_per_week == "27"
    assert state.imaging_duration_h == "0.8"


def test_step8_source_adapter_uses_retained_state_when_panel_vars_are_absent():
    app = SimpleNamespace(
        _spect_preview_session_state=SpectPreviewSessionState("750", "24", "0.75")
    )
    source = spect_preview_source_from_app(app)

    assert source.administered_activity_mbq == pytest.approx(750.0)
    assert source.patients_per_week == pytest.approx(24.0)
    assert source.imaging_duration_h == pytest.approx(0.75)


def test_step8_source_adapter_updates_session_state_before_calculation():
    app = _app_with_vars("810", "26", "0.9")
    source = spect_preview_source_from_app(app)
    state = get_spect_preview_session_state(app)

    assert state.administered_activity_mbq == "810"
    assert state.patients_per_week == "26"
    assert state.imaging_duration_h == "0.9"
    assert source.administered_activity_mbq == pytest.approx(810.0)


def test_step8_invalid_retained_value_remains_visible_but_still_blocks_calculation():
    app = SimpleNamespace(
        _spect_preview_session_state=SpectPreviewSessionState("bad", "20", "0.5")
    )
    with pytest.raises(SpectPreviewError, match="Invalid SPECT preview source input"):
        spect_preview_source_from_app(app)
    assert app._spect_preview_session_state.administered_activity_mbq == "bad"


def test_step8_state_is_not_referenced_by_project_save_results_reports_or_serialization():
    forbidden_paths = [ROOT / "app.py", ROOT / "services" / "project_serializer.py"]
    forbidden_paths += list((ROOT / "reports").glob("*.py"))
    forbidden_paths += list((ROOT / "serialization").glob("*.py"))

    tokens = (
        "_spect_preview_session_state",
        "SpectPreviewSessionState",
        "SPECT_UI_SESSION_PREVIEW_BASELINE",
    )
    for path in forbidden_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text


def test_step8_panel_declares_session_only_retention_and_no_project_persistence():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    assert "Step 8 (editable, non-production, not saved; session-only)" in panel
    assert "persist only for this running" in panel
    assert "including room/tab switching" in panel
    assert "normal project save" in panel
