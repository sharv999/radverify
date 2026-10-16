from __future__ import annotations

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
from services.pet_pdf_integration_readiness_gate import (
    PET_PDF_GATE_BLOCK_REASON,
    PET_PDF_INTEGRATION_READINESS_BASELINE,
    PET_PDF_INTEGRATION_READINESS_CONTRACT_VERSION,
    PET_PDF_INTEGRATION_SWITCH_ENABLED,
    PetPdfIntegrationNotEnabledError,
    assess_pet_pdf_integration_readiness,
    require_pet_pdf_integration_enabled,
)
from services.pet_report_payload_harness import build_non_issueable_pet_report_payload
from services.pet_report_pdf_preview import (
    PET_PDF_PREVIEW_BASELINE,
    PET_PDF_PREVIEW_CONTRACT_VERSION,
    PetPdfPreviewError,
    render_non_issueable_pet_pdf_preview,
)
from services.pet_report_section_view_model import build_non_issueable_pet_report_section_view_model
from services.pet_results_model import build_room_results_model
from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.source_readiness import validate_project_source_readiness


def _project_and_view_model():
    room = Room(name="PET Room", modality="PET", barriers=default_barriers(), geometry=RoomGeometry())
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
    project = Project(project_name="PET Step 28", rooms=[room])
    rows = build_room_results_model(project, room, fallback_results=[])
    envelope = build_non_issueable_pet_combined_report_payload_envelope(
        source_payload=build_non_issueable_pet_source_summary(room),
        barrier_payload=build_non_issueable_pet_report_payload(rows),
    )
    return project, build_non_issueable_pet_report_section_view_model(envelope)


def test_step28_pdf_foundations_pass_but_integration_gate_remains_closed():
    state = assess_pet_pdf_integration_readiness()
    assert state["contract_version"] == PET_PDF_INTEGRATION_READINESS_CONTRACT_VERSION == 1
    assert state["baseline"] == PET_PDF_INTEGRATION_READINESS_BASELINE
    assert state["validated_foundations"] is True
    assert state["pdf_integration_switch_enabled"] is False
    assert state["pdf_integration_ready"] is False
    assert state["issued_pdf_enabled"] is False
    assert state["machine_export_enabled"] is False
    assert state["certification_enabled"] is False
    assert len(state["checks"]) == 4
    assert all(check["passed"] for check in state["checks"])
    assert state["blocking_reasons"] == [PET_PDF_GATE_BLOCK_REASON]


def test_step28_explicit_pdf_integration_gate_fails_closed():
    assert PET_PDF_INTEGRATION_SWITCH_ENABLED is False
    with pytest.raises(PetPdfIntegrationNotEnabledError, match="not enabled"):
        require_pet_pdf_integration_enabled()


def test_step28_normal_output_gate_still_blocks_pet_issued_outputs():
    project, _view = _project_and_view_model()
    readiness = validate_project_source_readiness(project)
    assert any(row.get("output_blocking") is True for row in readiness["source_results"])
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_step28_renders_deterministic_non_issueable_pdf_bytes():
    _project, view = _project_and_view_model()
    first = render_non_issueable_pet_pdf_preview(view)
    second = render_non_issueable_pet_pdf_preview(view)
    assert first.pdf_bytes == second.pdf_bytes
    assert first.pdf_bytes.startswith(b"%PDF-")
    assert first.pdf_bytes.rstrip().endswith(b"%%EOF")
    assert first.contract_version == PET_PDF_PREVIEW_CONTRACT_VERSION == 1
    assert first.baseline == PET_PDF_PREVIEW_BASELINE
    assert first.non_issueable is True
    assert first.output_eligible is False
    assert first.issued_pdf_enabled is False
    assert first.certification_enabled is False


def test_step28_pdf_contains_pet_source_exposure_barrier_and_provenance_content():
    _project, view = _project_and_view_model()
    pdf = render_non_issueable_pet_pdf_preview(view).pdf_bytes
    for expected in (
        b"PET SHIELDING ASSESSMENT",
        b"NON-ISSUEABLE PDF",
        b"PET source summary",
        b"PET exposure periods",
        b"Uptake",
        b"Imaging",
        b"Barrier 1:",
        b"Calculation provenance",
        b"NON-ISSUEABLE PREVIEW - NOT FOR REGULATORY",
    ):
        assert expected in pdf


def test_step28_pdf_metadata_is_explicitly_non_issueable():
    _project, view = _project_and_view_model()
    pdf = render_non_issueable_pet_pdf_preview(view).pdf_bytes
    assert b"PET Shielding Assessment - Non-Issueable PDF Preview" in pdf
    assert PET_PDF_PREVIEW_BASELINE.encode("ascii") in pdf


def test_step28_pdf_preview_fails_closed_for_open_drifted_or_multiline_view_model():
    _project, view = _project_and_view_model()
    opened = deepcopy(view)
    opened["report_integration_open"] = True
    with pytest.raises(PetPdfPreviewError, match="closed and non-issueable"):
        render_non_issueable_pet_pdf_preview(opened)

    drifted = deepcopy(view)
    drifted["view_model_baseline"] = "future"
    with pytest.raises(PetPdfPreviewError, match="baseline"):
        render_non_issueable_pet_pdf_preview(drifted)

    multiline = deepcopy(view)
    multiline["source_summary"]["rows"][0]["value"] = "F18\nunsafe"
    with pytest.raises(Exception, match="single line"):
        render_non_issueable_pet_pdf_preview(multiline)


def test_step28_pdf_preview_does_not_mutate_view_model():
    _project, view = _project_and_view_model()
    before = deepcopy(view)
    render_non_issueable_pet_pdf_preview(view)
    assert view == before


def test_step28_pdf_gate_and_preview_remain_disconnected_from_issueable_output_routes():
    forbidden_tokens = ("pet_pdf_integration_readiness_gate", "pet_report_pdf_preview")
    paths = list(Path("reports").glob("*.py")) + [
        Path("services/export_eligibility.py"),
        Path("services/report_certification.py"),
        Path("services/report_wording_guard.py"),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden_tokens:
            assert token not in text

    module_text = Path("services/pet_report_pdf_preview.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "from reports", "import reports", "output_pipeline", "results_exporter",
        "export_eligibility", "report_certification", "write_bytes", "open(", "path(",
    ):
        assert forbidden not in module_text


def test_step28_cli_reports_validated_foundations_but_closed_integration(capsys):
    from tools import pet_pdf_integration_readiness

    result = pet_pdf_integration_readiness.main()
    captured = capsys.readouterr()
    assert result in (None, 0)
    assert "PET STEP 28 PDF INTEGRATION READINESS" in captured.out
    assert "Validated foundations: YES" in captured.out
    assert "PDF integration switch enabled: NO" in captured.out
    assert "PDF integration ready: NO" in captured.out
    assert "Issued PET PDF enabled: NO" in captured.out
    assert "Machine export enabled: NO" in captured.out
    assert "Certification enabled: NO" in captured.out


def test_step28_audit_document_records_closed_issued_output_and_isolated_preview():
    text = Path("docs/architecture/PET_PDF_Readiness_and_NonIssueable_Preview_Step_28.md").read_text(encoding="utf-8-sig")
    assert "Validated report foundations: **YES**" in text
    assert "PDF integration switch enabled: **NO**" in text
    assert "**NO-GO for issued PET PDF integration.**" in text
    assert "isolated non-issueable PDF preview" in text
    assert "Issued PDF, machine export, certification and signatures remain closed" in text
