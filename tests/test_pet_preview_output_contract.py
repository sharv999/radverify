from pathlib import Path

from tabs.pet_preview_output_contract import (
    PET_DISPLAYED_ASSUMPTIONS,
    PET_OUTPUT_SCHEDULE_COLUMNS,
    PET_PREVIEW_OUTPUT_BASELINE,
    PET_PREVIEW_OUTPUT_CONTRACT_VERSION,
    PET_RADIONUCLIDE_DATA_PROVENANCE,
    build_barrier_reasoning,
)
from tabs.pet_preview_panel import calculate_pet_barrier_schedule_preview

ROOT = Path(__file__).resolve().parents[1]


def _source():
    return {
        "radionuclide": "F18",
        "injected_activity_mbq": "250",
        "patients_per_week": "30",
        "residual_activity_factor": "1",
        "phase_1_name": "Uptake",
        "phase_1_start_h": "0",
        "phase_1_duration_h": "1",
        "phase_1_activity_retention_factor": "1",
        "phase_2_name": "Imaging",
        "phase_2_start_h": "1",
        "phase_2_duration_h": "0.5",
        "phase_2_activity_retention_factor": "1",
    }


def _barriers():
    return ({
        "source_name": "N wall",
        "material_key": "lead",
        "distance_m": "2",
        "occupancy_factor": "0.5",
        "design_goal_uSv_per_week": "10",
        "provided_thickness_mm": "12",
    },)


def test_pet_output_contract_identity_and_schedule_headings_are_frozen():
    assert PET_PREVIEW_OUTPUT_CONTRACT_VERSION == 4
    assert PET_PREVIEW_OUTPUT_BASELINE == "pet-single-source-output-v4-activity-retention"
    assert tuple((key, label) for key, label, _ in PET_OUTPUT_SCHEDULE_COLUMNS)[-2:] == (
        ("status", "Status"),
        ("reasoning", "Calculation reasoning"),
    )


def test_pet_output_contract_freezes_assumptions_and_honest_radionuclide_provenance():
    assert PET_DISPLAYED_ASSUMPTIONS[0] == "One PET patient/source position is modelled per selected room."
    assert "inverse square" in " ".join(PET_DISPLAYED_ASSUMPTIONS)
    assert "per-field source references" in PET_RADIONUCLIDE_DATA_PROVENANCE


def test_pet_schedule_exposes_summary_provenance_and_reasoning():
    payload = calculate_pet_barrier_schedule_preview(_source(), _barriers())
    assert payload["output_contract_version"] == 4
    assert payload["output_baseline"] == "pet-single-source-output-v4-activity-retention"
    assert payload["calculation_basis"] == "decay_integrated_point_source_at_1m"
    assert payload["radionuclide_data"]["display_name"] == "F-18"
    assert payload["radionuclide_data"]["half_life_h"] == 1.8295
    assert payload["radionuclide_data"]["dataset_id"] == "pet-radionuclide-physics-source-model"
    assert payload["radionuclide_data"]["dataset_approval_status"] == "production_approved"
    assert payload["radionuclide_data"]["dataset_approved_by"] == "YOUR NAME"
    assert "IAEA" in payload["radionuclide_data"]["half_life_provenance"]["source_title"]
    assert "AAPM" in payload["radionuclide_data"]["dose_rate_provenance"]["source_title"]
    assert payload["attenuation_datasets"] == ({
        "dataset_id": "pet-511kev-aapm-tg108-review-fixture",
        "dataset_revision": "2026-07-19-review-1",
        "approved_by": "Steve H",
        "approved_date": "2026-07-19",
    },)
    row = payload["rows"][0]
    assert "inverse square" in row["calculation_reasoning"]
    assert "occupancy T=0.5" in row["calculation_reasoning"]
    assert row["attenuation_record_id"] == "tg108-511kev-lead-provisional"
    assert "AAPM Task Group 108" in row["attenuation_provenance"]


def test_pet_reasoning_is_deterministic_and_complete():
    payload = calculate_pet_barrier_schedule_preview(_source(), _barriers())
    row = payload["rows"][0]
    assert build_barrier_reasoning(row) == row["calculation_reasoning"]
    for phrase in ("1 m workload", "goal", "TVLs", "Provided", row["compliance_status"]):
        assert phrase in row["calculation_reasoning"]


def test_pet_output_freeze_remains_outside_production_paths():
    output_module = "pet_preview_output_contract"
    for path in (
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "tabs" / "results_tab_layout.py",
    ):
        assert output_module not in path.read_text(encoding="utf-8")
    report_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "reports").glob("*.py"))
    assert output_module not in report_text
