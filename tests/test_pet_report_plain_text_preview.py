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
from services.pet_report_plain_text_preview import (
    PET_PLAIN_TEXT_PREVIEW_BASELINE,
    PET_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION,
    PET_PLAIN_TEXT_PREVIEW_STATUS,
    PetPlainTextPreviewError,
    render_non_issueable_pet_plain_text_preview,
)
from services.pet_report_section_view_model import build_non_issueable_pet_report_section_view_model
from services.pet_results_model import build_room_results_model
from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.source_readiness import validate_project_source_readiness


def _project_and_view_model():
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
    return project, build_non_issueable_pet_report_section_view_model(envelope)


def test_plain_text_preview_is_deterministic_complete_and_in_memory():
    _project, view = _project_and_view_model()
    lines = render_non_issueable_pet_plain_text_preview(view)

    assert isinstance(lines, list)
    assert lines == render_non_issueable_pet_plain_text_preview(view)
    assert lines[0] == "PET shielding assessment — non-issueable preview"
    assert PET_PLAIN_TEXT_PREVIEW_STATUS in lines
    assert "PET source summary" in lines
    assert "PET exposure periods" in lines
    assert "PET barrier shielding results" in lines
    assert "Calculation provenance" in lines
    assert lines[-1] == "END OF NON-ISSUEABLE PET PREVIEW"
    assert any(line == "Administered activity per patient: 250.000 MBq/patient" for line in lines)
    assert any("Exposure period | Start after administration [h]" in line for line in lines)
    assert any("Barrier | Material | Distance [m]" in line for line in lines)
    assert all("\n" not in line and "\r" not in line for line in lines)


def test_plain_text_preview_consumes_only_frozen_view_model_and_fails_closed():
    _project, view = _project_and_view_model()

    opened = deepcopy(view)
    opened["report_integration_open"] = True
    with pytest.raises(PetPlainTextPreviewError, match="not closed and non-issueable"):
        render_non_issueable_pet_plain_text_preview(opened)

    unverified = deepcopy(view)
    unverified["replay_verified"] = False
    with pytest.raises(PetPlainTextPreviewError, match="replay is not verified"):
        render_non_issueable_pet_plain_text_preview(unverified)

    drifted = deepcopy(view)
    drifted["barrier_table"]["field_order"].append("unexpected")
    with pytest.raises(PetPlainTextPreviewError, match="field ordering has drifted"):
        render_non_issueable_pet_plain_text_preview(drifted)

    multiline = deepcopy(view)
    multiline["source_summary"]["rows"][0]["value"] = "F18\nunsafe"
    with pytest.raises(PetPlainTextPreviewError, match="single line"):
        render_non_issueable_pet_plain_text_preview(multiline)


def test_plain_text_preview_contract_identity_is_frozen():
    assert PET_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION == 1
    assert PET_PLAIN_TEXT_PREVIEW_BASELINE == "pet-plain-text-preview-v1-non-issueable"


def test_plain_text_preview_is_disconnected_and_issueable_outputs_remain_blocked():
    project, view = _project_and_view_model()
    assert render_non_issueable_pet_plain_text_preview(view)

    forbidden_token = "pet_report_plain_text_preview"
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


def test_plain_text_preview_module_has_no_file_or_document_dependencies():
    text = Path("services/pet_report_plain_text_preview.py").read_text(encoding="utf-8")
    for forbidden in (
        "reportlab",
        "openpyxl",
        "csv.",
        "json.dump",
        "Path(",
        "open(",
        "write_text",
        "write_bytes",
        "reports.",
    ):
        assert forbidden not in text
