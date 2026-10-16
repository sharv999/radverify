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
from services.pet_combined_report_payload_harness import build_non_issueable_pet_combined_report_payload_envelope
from services.pet_report_payload_harness import build_non_issueable_pet_report_payload
from services.pet_report_section_view_model import (
    PET_BARRIER_TABLE_FIELDS,
    PET_EXPOSURE_TABLE_FIELDS,
    PET_PROVENANCE_DISPLAY_FIELDS,
    PET_REPORT_SECTION_HEADINGS,
    PET_REPORT_SECTION_VIEW_MODEL_BASELINE,
    PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    PET_REPORT_SECTION_WARNINGS,
    PET_SOURCE_DISPLAY_FIELDS,
    PetReportSectionViewModelError,
    build_non_issueable_pet_report_section_view_model,
)
from services.pet_results_model import build_room_results_model
from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.source_readiness import validate_project_source_readiness


def _project_and_envelope():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 0.8),
        ),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.5, 1.0)),
    )
    project = Project(project_name="PET", rooms=[room])
    rows = build_room_results_model(project, room, fallback_results=[])
    envelope = build_non_issueable_pet_combined_report_payload_envelope(
        source_payload=build_non_issueable_pet_source_summary(room),
        barrier_payload=build_non_issueable_pet_report_payload(rows),
    )
    return project, envelope


def test_view_model_freezes_headings_warnings_field_order_units_and_tables():
    _project, envelope = _project_and_envelope()
    view = build_non_issueable_pet_report_section_view_model(envelope)

    assert view["view_model_contract_version"] == PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION
    assert view["view_model_baseline"] == PET_REPORT_SECTION_VIEW_MODEL_BASELINE
    assert view["non_issueable"] is True
    assert view["report_integration_open"] is False
    assert view["replay_verified"] is True
    assert view["headings"] == dict(PET_REPORT_SECTION_HEADINGS)
    assert view["warnings"] == list(PET_REPORT_SECTION_WARNINGS)
    assert view["source_summary"]["field_order"] == list(PET_SOURCE_DISPLAY_FIELDS)
    assert view["exposure_period_table"]["field_order"] == list(PET_EXPOSURE_TABLE_FIELDS)
    assert view["barrier_table"]["field_order"] == list(PET_BARRIER_TABLE_FIELDS)
    assert view["provenance"]["field_order"] == list(PET_PROVENANCE_DISPLAY_FIELDS)
    assert [column["unit"] for column in view["barrier_table"]["columns"]] == [
        "", "", "m", "", "µSv/week", "µSv/week", "µSv/week", "", "TVL",
        "mm", "mm", "mm", "µSv/week", "", "",
    ]
    assert len(view["exposure_period_table"]["rows"]) == 2
    assert len(view["barrier_table"]["rows"]) == envelope["barrier_payload"]["barrier_count"]


def test_view_model_formats_values_deterministically_and_uses_only_envelope_data():
    _project, envelope = _project_and_envelope()
    view = build_non_issueable_pet_report_section_view_model(envelope)

    source_by_field = {row["field"]: row for row in view["source_summary"]["rows"]}
    assert source_by_field["administered_activity_mbq_per_patient"] == {
        "field": "administered_activity_mbq_per_patient",
        "label": "Administered activity per patient",
        "value": "250.000",
        "unit": "MBq/patient",
    }
    assert view["exposure_period_table"]["rows"][1] == {
        "name": "Imaging",
        "start_after_administration_h": "1.000",
        "duration_h": "0.500",
        "activity_retention_factor": "0.800",
    }
    assert view["barrier_table"]["rows"][0]["barrier_transmission_factor_B"].count(".") == 1
    assert len(view["barrier_table"]["rows"][0]["barrier_transmission_factor_B"].split(".")[1]) == 6
    assert view["provenance"]["rows"][-1]["value"] == "Yes"
    assert "source_summary_payload" not in view
    assert "barrier_payload" not in view


def test_view_model_fails_closed_for_open_unverified_or_drifted_envelopes():
    _project, envelope = _project_and_envelope()

    opened = deepcopy(envelope)
    opened["report_integration_open"] = True
    with pytest.raises(PetReportSectionViewModelError, match="not closed and non-issueable"):
        build_non_issueable_pet_report_section_view_model(opened)

    unverified = deepcopy(envelope)
    unverified["shared_provenance"]["replay_verified"] = False
    with pytest.raises(PetReportSectionViewModelError, match="replay is not verified"):
        build_non_issueable_pet_report_section_view_model(unverified)

    drifted = deepcopy(envelope)
    drifted["barrier_payload"]["barriers"][0]["unexpected"] = "field"
    with pytest.raises(PetReportSectionViewModelError, match="31-field contract"):
        build_non_issueable_pet_report_section_view_model(drifted)


def test_view_model_is_disconnected_and_issueable_outputs_remain_blocked():
    project, envelope = _project_and_envelope()
    view = build_non_issueable_pet_report_section_view_model(envelope)
    assert view["non_issueable"] is True

    forbidden_token = "pet_report_section_view_model"
    for path in Path("reports").glob("*.py"):
        assert forbidden_token not in path.read_text(encoding="utf-8")
    for path in (
        Path("services/export_eligibility.py"),
        Path("services/report_certification.py"),
        Path("reports/output_pipeline.py"),
        Path("reports/results_exporter.py"),
    ):
        assert forbidden_token not in path.read_text(encoding="utf-8")

    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_view_model_module_has_no_file_or_document_rendering_dependencies():
    text = Path("services/pet_report_section_view_model.py").read_text(encoding="utf-8")
    for forbidden in (
        "reportlab",
        "openpyxl",
        "csv.",
        "json.dump",
        "Path(",
        "open(",
        "reports.",
    ):
        assert forbidden not in text
