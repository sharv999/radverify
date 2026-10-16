from copy import deepcopy
from pathlib import Path

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import (
    PetWorkingProjectState,
    set_room_pet_working_state,
)
from services.export_eligibility import assess_export_eligibility
from services.pet_source_summary_harness import (
    PET_SOURCE_SUMMARY_HARNESS_BASELINE,
    PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
    PetSourceSummaryHarnessError,
    build_non_issueable_pet_source_summary,
)
from services.pet_source_summary_report_contract import (
    PET_EXPOSURE_PERIOD_FIELDS,
    PET_SOURCE_SUMMARY_FIELDS,
    PET_SOURCE_SUMMARY_REPORT_BASELINE,
    PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
    PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
)
from services.source_readiness import validate_project_source_readiness


def _room():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 1.0),
        ),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.5, 1.0)),
    )
    return room


def test_source_summary_contract_is_frozen_and_complete():
    assert PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN is False
    assert PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION == 2
    assert PET_SOURCE_SUMMARY_REPORT_BASELINE == "pet-source-summary-report-v2-activity-retention-closed"
    assert PET_SOURCE_SUMMARY_FIELDS == (
        "radionuclide",
        "administered_activity_mbq_per_patient",
        "patients_per_week",
        "activity_scaling_factor",
        "exposure_periods",
        "pet_position_west_m",
        "pet_position_south_m",
        "pet_position_height_affl_m",
        "provenance_manifest_id",
        "provenance_manifest_revision",
        "radionuclide_dataset_id",
        "radionuclide_dataset_revision",
        "radionuclide_records_sha256",
        "attenuation_dataset_id",
        "attenuation_dataset_revision",
        "attenuation_records_sha256",
        "physics_contract_version",
        "solver_contract_version",
    )
    assert PET_EXPOSURE_PERIOD_FIELDS == (
        "name",
        "start_after_administration_h",
        "duration_h",
        "activity_retention_factor",
    )


def test_harness_builds_only_frozen_source_summary_fields():
    payload = build_non_issueable_pet_source_summary(_room())
    assert payload["harness_contract_version"] == PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION
    assert payload["harness_baseline"] == PET_SOURCE_SUMMARY_HARNESS_BASELINE
    assert payload["non_issueable"] is True
    assert payload["report_integration_open"] is False
    summary = payload["source_summary"]
    assert tuple(summary.keys()) == PET_SOURCE_SUMMARY_FIELDS
    assert summary["radionuclide"] == "F18"
    assert summary["administered_activity_mbq_per_patient"] == 250.0
    assert summary["patients_per_week"] == 30.0
    assert summary["pet_position_west_m"] == 2.0
    assert summary["pet_position_south_m"] == 2.5
    assert summary["pet_position_height_affl_m"] == 1.0
    assert len(summary["radionuclide_records_sha256"]) == 64
    assert len(summary["attenuation_records_sha256"]) == 64
    assert tuple(summary["exposure_periods"][0].keys()) == PET_EXPOSURE_PERIOD_FIELDS


def test_harness_requires_persisted_pet_working_state():
    room = Room(name="No PET", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    with pytest.raises(PetSourceSummaryHarnessError, match="Persisted PET working state"):
        build_non_issueable_pet_source_summary(room)


def test_source_summary_harness_is_not_connected_to_issueable_outputs():
    forbidden_tokens = (
        "pet_source_summary_harness",
        "pet_source_summary_report_contract",
    )
    for path in Path("reports").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text
    for path in (
        Path("services/export_eligibility.py"),
        Path("reports/output_pipeline.py"),
    ):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text


def test_issueable_outputs_remain_blocked_after_source_summary_build():
    room = _room()
    project = Project(project_name="PET", rooms=[room])
    payload = build_non_issueable_pet_source_summary(room)
    assert payload["non_issueable"] is True
    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
