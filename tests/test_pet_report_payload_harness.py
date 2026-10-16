from copy import deepcopy
from pathlib import Path

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from services.export_eligibility import assess_export_eligibility
from services.pet_report_payload_harness import (
    PET_REPORT_PAYLOAD_HARNESS_BASELINE,
    PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
    PetReportPayloadHarnessError,
    build_non_issueable_pet_report_payload,
)
from services.pet_report_readiness_contract import PET_REPORT_PERMITTED_RESULT_FIELDS
from services.pet_results_model import build_room_results_model
from services.source_readiness import validate_project_source_readiness


def _project_and_rows():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0, 1.0),),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.0, 1.0)),
    )
    project = Project(project_name="PET", rooms=[room])
    rows = build_room_results_model(project, room, fallback_results=[])
    return project, rows


def test_harness_copies_only_the_frozen_31_permitted_fields():
    _project, rows = _project_and_rows()
    payload = build_non_issueable_pet_report_payload(rows)

    assert payload["harness_contract_version"] == PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION
    assert payload["harness_baseline"] == PET_REPORT_PAYLOAD_HARNESS_BASELINE
    assert payload["non_issueable"] is True
    assert payload["report_integration_open"] is False
    assert payload["permitted_field_count"] == 31
    assert tuple(payload["permitted_fields"]) == PET_REPORT_PERMITTED_RESULT_FIELDS
    assert payload["barrier_count"] == len(rows)
    for original, adapted in zip(rows, payload["barriers"]):
        assert tuple(adapted.keys()) == PET_REPORT_PERMITTED_RESULT_FIELDS
        assert set(adapted) == set(PET_REPORT_PERMITTED_RESULT_FIELDS)
        assert "notes" in original
        assert "notes" not in adapted
        assert "results_presentation_baseline" not in adapted


def test_harness_fails_closed_for_missing_required_field():
    _project, rows = _project_and_rows()
    broken = deepcopy(rows)
    del broken[0]["calculation_reasoning"]
    with pytest.raises(PetReportPayloadHarnessError, match="missing required"):
        build_non_issueable_pet_report_payload(broken)


def test_harness_fails_closed_for_unverified_or_mixed_provenance():
    _project, rows = _project_and_rows()
    unverified = deepcopy(rows)
    unverified[0]["replay_verified"] = False
    with pytest.raises(PetReportPayloadHarnessError, match="not deterministic-replay verified"):
        build_non_issueable_pet_report_payload(unverified)

    mixed = deepcopy(rows)
    mixed[1]["provenance_manifest_revision"] = "tampered-revision"
    with pytest.raises(PetReportPayloadHarnessError, match="frozen room provenance"):
        build_non_issueable_pet_report_payload(mixed)


def test_harness_fails_closed_for_empty_or_duplicate_barrier_rows():
    with pytest.raises(PetReportPayloadHarnessError, match="At least one"):
        build_non_issueable_pet_report_payload([])

    _project, rows = _project_and_rows()
    duplicate = deepcopy(rows)
    duplicate[1]["barrier_name"] = duplicate[0]["barrier_name"]
    with pytest.raises(PetReportPayloadHarnessError, match="unique barrier names"):
        build_non_issueable_pet_report_payload(duplicate)


def test_harness_is_not_connected_to_reports_or_output_pipeline():
    forbidden_token = "pet_report_payload_harness"
    for path in Path("reports").glob("*.py"):
        assert forbidden_token not in path.read_text(encoding="utf-8")
    assert forbidden_token not in Path("services/export_eligibility.py").read_text(encoding="utf-8")


def test_issueable_outputs_remain_blocked_after_harness_build():
    project, rows = _project_and_rows()
    payload = build_non_issueable_pet_report_payload(rows)
    assert payload["non_issueable"] is True

    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
