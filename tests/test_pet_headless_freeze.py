from pathlib import Path

from serialization.pet_headless_freeze import (
    FROZEN_PET_HEADLESS_VERSIONS,
    PET_HEADLESS_FREEZE_BASELINE,
    PET_HEADLESS_PATH_FROZEN,
    PET_VALIDATION_GATE_COMMANDS,
    assert_pet_headless_freeze_intact,
    current_pet_headless_versions,
)

ROOT = Path(__file__).resolve().parents[1]


def test_pet_headless_contract_versions_are_frozen():
    assert PET_HEADLESS_PATH_FROZEN is True
    assert PET_HEADLESS_FREEZE_BASELINE == "pet-headless-v2-activity-retention"
    assert current_pet_headless_versions() == FROZEN_PET_HEADLESS_VERSIONS
    assert_pet_headless_freeze_intact()


def test_pet_freeze_records_the_two_command_validation_gate():
    assert PET_VALIDATION_GATE_COMMANDS == (
        "python -m pytest -q",
        "python -m tools.pet_cli_regression .\\tests\\fixtures\\pet_requests\\pet_cli_regression_manifest.json",
    )


def test_pet_headless_path_remains_disconnected_from_ui_and_production_outputs():
    forbidden_targets = (
        ROOT / "app.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    )
    forbidden_import_fragments = (
        "services.pet_calculation_service",
        "serialization.pet_calculation_request_contract",
        "serialization.pet_project_contract",
        "serialization.pet_headless_replay",
        "serialization.pet_headless_freeze",
        "tools.pet_calculation_request_cli",
        "tools.pet_cli_regression",
    )

    report_targets = tuple((ROOT / "reports").glob("*.py"))
    for path in (*forbidden_targets, *report_targets):
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_import_fragments:
            assert fragment not in text, f"{path.relative_to(ROOT)} imports frozen PET path: {fragment}"


def test_pet_frozen_physics_remains_valid_after_controlled_host_promotion():
    from modalities.registry import get_modality_plugin, production_modalities

    pet = get_modality_plugin("PET")
    assert pet.spec.production_enabled is True
    assert pet.spec.expected_sources[0].dose_model == "pet_patient_production_dispatch"
    assert "PET" in {spec.modality_id for spec in production_modalities()}
