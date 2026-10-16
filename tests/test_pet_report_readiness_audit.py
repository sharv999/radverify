from pathlib import Path

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from services.export_eligibility import assess_export_eligibility
from services.pet_report_readiness_contract import (
    PET_REPORT_FORBIDDEN_RESULT_FIELDS,
    PET_REPORT_INTEGRATION_OPEN,
    PET_REPORT_PERMITTED_RESULT_FIELDS,
    PET_REPORT_REQUIRED_RESULT_FIELDS,
    PET_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER,
    audit_pet_result_row,
)
from services.pet_results_model import build_room_results_model
from services.source_readiness import validate_project_source_readiness


def _project():
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
    return Project(project_name="PET", rooms=[room]), room


def test_current_pet_results_satisfy_frozen_report_readiness_allowlist():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    assert rows
    audited = audit_pet_result_row(rows[0])
    assert audited["report_integration_open"] is False
    assert audited["ready_for_future_adapter"] is True
    assert audited["missing_required_fields"] == []
    assert tuple(audited["permitted_result_payload"].keys()) == PET_REPORT_PERMITTED_RESULT_FIELDS


def test_report_allowlist_excludes_ui_only_and_requires_separate_source_adapter():
    assert PET_REPORT_INTEGRATION_OPEN is False
    assert PET_REPORT_REQUIRED_RESULT_FIELDS == PET_REPORT_PERMITTED_RESULT_FIELDS
    assert not set(PET_REPORT_FORBIDDEN_RESULT_FIELDS) & set(PET_REPORT_PERMITTED_RESULT_FIELDS)
    assert "radionuclide" in PET_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER
    assert "exposure_periods" in PET_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER
    assert "pet_position_height_affl_m" in PET_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER


def test_pet_report_readiness_contract_is_not_imported_by_report_or_output_modules():
    forbidden_tokens = (
        "pet_results_model",
        "pet_results_presentation_contract",
        "pet_report_readiness_contract",
    )
    for path in Path("reports").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text


def test_persisted_pet_still_blocks_issueable_outputs_after_audit():
    project, _room = _project()
    readiness = validate_project_source_readiness(project)
    assert any(item.get("output_blocking") is True for item in readiness["source_results"])
    eligibility = assess_export_eligibility(
        preflight=readiness,
        requested_report_status="Final",
    )
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_audit_document_records_closed_boundary_and_exact_field_count():
    text = Path("docs/architecture/PET_Report_Readiness_Audit_Step_22.md").read_text(encoding="utf-8")
    assert "PET_REPORT_INTEGRATION_OPEN = False" in text
    assert "All 31 fields are required" in text
    assert "PDF generation" in text
    assert "CSV/JSON machine-readable export" in text
    assert "certification and signature" in text
