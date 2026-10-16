from pathlib import Path

from tabs.pet_preview_ui_contract import (
    PET_POSITION_UI_FIELDS,
    PET_PREVIEW_UI_BASELINE,
    PET_PREVIEW_UI_CONTRACT_VERSION,
    PET_RESULTS_COLUMNS,
    PET_SOURCE_UI_DEFAULTS,
    PET_SOURCE_UI_FIELDS,
    display_label,
)
from tabs.pet_preview_panel import build_pet_preview_source_domain, calculate_pet_preview
from tests.test_pet_ui_preview import _values

ROOT = Path(__file__).resolve().parents[1]


def test_pet_step10_freezes_source_field_order_labels_units_and_defaults():
    actual = tuple(
        (field.key, field.label, field.unit, field.default, field.widget_kind)
        for field in PET_SOURCE_UI_FIELDS
    )
    assert actual == (
        ("room_mode", "PET room mode", "", "Imaging Room", "combobox"),
        ("radionuclide", "Radionuclide", "", "F18", "combobox"),
        ("injected_activity_mbq", "Administered activity per patient", "MBq/patient", "250", "entry"),
        ("patients_per_week", "Patient workload", "patients/week", "30", "entry"),
        ("phase_1_start_h", "Uptake time", "h", "0", "entry"),
        ("phase_1_duration_h", "Imaging time", "h", "1", "entry"),
        ("phase_1_activity_retention_factor", "Voiding factor", "dimensionless (0–1)", "1.0", "entry"),
    )
    assert PET_SOURCE_UI_DEFAULTS == {field.key: field.default for field in PET_SOURCE_UI_FIELDS}



def test_pet_preview_ui_exposes_explicit_room_mode_and_single_phase_inputs():
    keys = {field.key for field in PET_SOURCE_UI_FIELDS}
    assert "room_mode" in keys
    assert "residual_activity_factor" not in keys
    assert "phase_1_name" not in keys
    assert not any(key.startswith("phase_2_") for key in keys)


def test_pet_preview_uses_unity_global_activity_scaling():
    values = dict(PET_SOURCE_UI_DEFAULTS)
    values.update({
        "phase_1_start_h": "1.0",
        "phase_1_duration_h": "0.5",
        "phase_1_activity_retention_factor": "0.85",
        # Legacy/external values must not alter the desktop preview calculation.
        "residual_activity_factor": "0.5",
    })
    source = build_pet_preview_source_domain(values)
    assert source.residual_activity_factor == 1.0


def test_pet_preview_fixed_single_phase_defaults_internally_to_imaging():
    values = dict(PET_SOURCE_UI_DEFAULTS)
    values.update({
        "phase_1_start_h": "1.0",
        "phase_1_duration_h": "0.5",
        "phase_1_activity_retention_factor": "0.85",
    })
    source = build_pet_preview_source_domain(values)
    assert len(source.exposure_phases) == 1
    assert source.exposure_phases[0].name == "Imaging"


def test_pet_preview_uptake_room_builds_uptake_only_phase():
    values = dict(PET_SOURCE_UI_DEFAULTS)
    values.update({
        "room_mode": "Uptake Room",
        "phase_1_start_h": "1.0",
        # Imaging-only values must not affect Uptake Room physics.
        "phase_1_duration_h": "9.0",
        "phase_1_activity_retention_factor": "0.2",
    })
    source = build_pet_preview_source_domain(values)
    assert len(source.exposure_phases) == 1
    phase = source.exposure_phases[0]
    assert phase.name == "Uptake"
    assert phase.start_time_h == 0.0
    assert phase.duration_h == 1.0
    assert phase.activity_retention_factor == 1.0



def test_pet_preview_shows_derived_decay_factor_as_read_only_not_source_input():
    keys = {field.key for field in PET_SOURCE_UI_FIELDS}
    assert "calculated_decay_factor" not in keys
    panel_text = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert 'text="Calculated decay factor"' in panel_text
    assert 'state="readonly"' in panel_text
    assert "calculate_pet_decay_factor_at_time" in panel_text

def test_pet_step10_freezes_position_terminology_units_and_default_rule():
    assert tuple((field.key, field.label, field.unit, field.default) for field in PET_POSITION_UI_FIELDS) == (
        ("x_from_west_m", "Distance from West wall", "m", "room centre"),
        ("y_from_south_m", "Distance from South wall", "m", "room centre"),
        ("height_above_ffl_m", "Height above finished floor level", "m AFFL", "1.0"),
    )
    assert display_label(PET_POSITION_UI_FIELDS[2]) == "Height above finished floor level (m AFFL)"


def test_pet_step10_freezes_results_schedule_headings_and_units():
    assert tuple((key, label) for key, label, _width in PET_RESULTS_COLUMNS) == (
        ("name", "Barrier"),
        ("material", "Material"),
        ("distance", "Distance (m)"),
        ("occupancy", "Occupancy T"),
        ("goal", "Design goal (µSv/week)"),
        ("tvls", "Required TVLs"),
        ("required", "Required (mm)"),
        ("provided", "Provided (mm)"),
        ("transmitted", "Transmitted dose (µSv/week)"),
        ("status", "Status"),
    )


def test_pet_step10_preview_payload_identifies_frozen_ui_contract():
    preview = calculate_pet_preview(_values())
    assert PET_PREVIEW_UI_CONTRACT_VERSION == 7
    assert PET_PREVIEW_UI_BASELINE == "pet-single-source-ui-v7-room-mode"
    assert preview["ui_contract_version"] == PET_PREVIEW_UI_CONTRACT_VERSION
    assert preview["ui_baseline"] == PET_PREVIEW_UI_BASELINE


def test_pet_step10_ui_contract_remains_outside_production_paths():
    forbidden = (
        ROOT / "app.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    )
    forbidden += tuple((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        assert "pet_preview_ui_contract" not in path.read_text(encoding="utf-8")
