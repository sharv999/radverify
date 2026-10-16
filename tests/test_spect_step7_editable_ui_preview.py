"""Tests for SPECT Step 7 editable, non-persistent UI preview source inputs."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.shielding_models import Barrier, Room
from tabs.spect_preview_panel import (
    SPECT_UI_EDITABLE_PREVIEW_BASELINE,
    SPECT_UI_EDITABLE_PREVIEW_CONTRACT_VERSION,
    SPECT_UI_PREVIEW_SOURCE,
    SpectPreviewError,
    build_spect_preview_source,
    calculate_spect_room_preview,
    spect_preview_source_from_app,
)


ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


def _room() -> Room:
    return Room(
        name="SPECT Room 1",
        modality="SPECT",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy="Pb 0.88 mm (10 kg/m2)",
                thickness_mm=1.1,
                distance_m=2.0,
                occupancy_factor=0.5,
                design_goal_uSv_per_week=1.0,
            ),
            Barrier(
                name="East wall",
                material="Concrete",
                material_legacy="Concrete 150 mm",
                thickness_mm=150.0,
                distance_m=3.0,
                occupancy_factor=0.25,
                design_goal_uSv_per_week=1.0,
            ),
        ],
    )


def test_step7_contract_is_editable_preview_but_still_nonpersistent():
    assert SPECT_UI_EDITABLE_PREVIEW_CONTRACT_VERSION == 2
    assert (
        SPECT_UI_EDITABLE_PREVIEW_BASELINE
        == "spect-ui-preview-v2-editable-source-nonpersistent"
    )
    # Step 6 fixed values remain the Step 7 default/reset baseline.
    assert SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq == pytest.approx(600.0)
    assert SPECT_UI_PREVIEW_SOURCE.patients_per_week == pytest.approx(20.0)
    assert SPECT_UI_PREVIEW_SOURCE.imaging_duration_h == pytest.approx(0.5)


def test_step7_builds_validated_transient_source_from_editable_values():
    source = build_spect_preview_source("750", "24", "0.75")
    assert source.radionuclide == "Tc99m"
    assert source.administered_activity_mbq == pytest.approx(750.0)
    assert source.patients_per_week == pytest.approx(24.0)
    assert source.imaging_duration_h == pytest.approx(0.75)


@pytest.mark.parametrize(
    "activity,patients,duration",
    [
        ("", "20", "0.5"),
        ("abc", "20", "0.5"),
        ("0", "20", "0.5"),
        ("-1", "20", "0.5"),
        ("600", "0", "0.5"),
        ("600", "20", "0"),
    ],
)
def test_step7_invalid_editable_values_fail_at_source_domain_boundary(
    activity, patients, duration
):
    with pytest.raises(SpectPreviewError, match="Invalid SPECT preview source input"):
        build_spect_preview_source(activity, patients, duration)


def test_step7_app_adapter_reads_transient_vars_and_preserves_step6_fallback():
    fallback = spect_preview_source_from_app(SimpleNamespace())
    assert fallback is SPECT_UI_PREVIEW_SOURCE

    app = SimpleNamespace(
        spect_preview_activity_var=_Var("700"),
        spect_preview_patients_var=_Var("22"),
        spect_preview_duration_var=_Var("0.6"),
    )
    source = spect_preview_source_from_app(app)
    assert source.administered_activity_mbq == pytest.approx(700.0)
    assert source.patients_per_week == pytest.approx(22.0)
    assert source.imaging_duration_h == pytest.approx(0.6)


def test_step7_editing_source_changes_schedule_without_changing_room_state():
    room = _room()
    before = deepcopy(room)

    baseline = calculate_spect_room_preview(room)
    edited_source = build_spect_preview_source("900", "30", "1.0")
    edited = calculate_spect_room_preview(room, source=edited_source)

    assert edited.source_physics.weekly_dose_uSv_at_1m > baseline.source_physics.weekly_dose_uSv_at_1m
    assert edited.rows[0].required_thickness_mm > baseline.rows[0].required_thickness_mm
    assert room == before


def test_step7_preview_values_are_not_wired_into_project_save_results_or_reports():
    forbidden_paths = [
        ROOT / "app.py",
        ROOT / "services" / "project_serializer.py",
    ]
    forbidden_paths += list((ROOT / "reports").glob("*.py"))
    forbidden_paths += list((ROOT / "serialization").glob("*.py"))

    preview_state_tokens = (
        "spect_preview_activity_var",
        "spect_preview_patients_var",
        "spect_preview_duration_var",
        "SPECT_UI_EDITABLE_PREVIEW_BASELINE",
    )
    for path in forbidden_paths:
        text = path.read_text(encoding="utf-8")
        for token in preview_state_tokens:
            assert token not in text


def test_step7_tk_panel_labels_inputs_as_nonproduction_and_not_saved():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    assert "editable, non-production, not saved" in panel
    assert "Preview-only Tc-99m source inputs" in panel
    # Step 23 later permits validated source/workload inputs to enter a
    # non-production Room.modality_state working contract. Step 7 preview
    # geometry and production output boundaries remain unchanged.
    assert "persist as non-production working-project" in panel
    assert "Nothing enters Results, reports, export" in panel


def test_step7_still_contains_no_shielding_equations_or_coefficients_in_tk_module():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    forbidden_physics_tokens = (
        "alpha_mm_inv",
        "beta_mm_inv",
        "gamma",
        "archer_required_thickness",
        "archer_transmission",
        "exp(",
        "log(",
        "dose_rate_constant_uSv_h_per_MBq_at_1m",
    )
    for token in forbidden_physics_tokens:
        assert token not in panel
