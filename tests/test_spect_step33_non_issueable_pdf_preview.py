from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state, set_room_spect_working_state
from services.spect_report_payload_harness import build_non_issueable_spect_report_payload
from services.spect_report_pdf_preview import (
    SPECT_PDF_PREVIEW_BASELINE,
    SPECT_PDF_PREVIEW_CONTRACT_VERSION,
    SPECT_PDF_PREVIEW_FOOTER,
    SPECT_PDF_PREVIEW_HEADER,
    SpectPdfPreviewError,
    render_non_issueable_spect_pdf_preview,
)
from services.spect_report_section_view_model import build_non_issueable_spect_report_section_view_model
from services.spect_results_model import build_room_results_model
from services.spect_source_summary_harness import build_non_issueable_spect_source_summary


def _view_model(lead_mm: float = 1.0):
    room = Room(
        name="SPECT Room",
        modality="SPECT",
        barriers=[
            Barrier(name="North wall", material="Pb", material_legacy=f"Pb {lead_mm} mm", thickness_mm=lead_mm, distance_m=2.0, occupancy_factor=1.0, design_goal_uSv_per_week=1.0),
            Barrier(name="South wall", material="Concrete", material_legacy="Concrete 150 mm", thickness_mm=150.0, distance_m=3.0, occupancy_factor=0.25, design_goal_uSv_per_week=10.0),
        ],
    )
    set_room_spect_working_state(room, new_spect_working_project_state(SpectSourceDomain("Tc99m", 600.0, 20.0, 0.5)))
    rows = build_room_results_model(Project(project_name="SPECT Step 33", rooms=[room]), room, fallback_results=[])
    return build_non_issueable_spect_report_section_view_model(
        source_payload=build_non_issueable_spect_source_summary(room),
        barrier_payload=build_non_issueable_spect_report_payload(rows),
    )


def test_step33_renders_deterministic_non_issueable_pdf_bytes():
    view = _view_model()
    first = render_non_issueable_spect_pdf_preview(view)
    second = render_non_issueable_spect_pdf_preview(view)
    assert first.pdf_bytes == second.pdf_bytes
    assert first.pdf_bytes.startswith(b"%PDF-")
    assert first.pdf_bytes.rstrip().endswith(b"%%EOF")
    assert first.contract_version == SPECT_PDF_PREVIEW_CONTRACT_VERSION == 1
    assert first.baseline == SPECT_PDF_PREVIEW_BASELINE
    assert first.non_issueable is True
    assert first.output_eligible is False
    assert first.issued_pdf_enabled is False
    assert first.certification_enabled is False


def test_step33_pdf_contains_frozen_preview_content_and_non_issueable_markers():
    pdf = render_non_issueable_spect_pdf_preview(_view_model()).pdf_bytes
    for expected in (
        b"SPECT SHIELDING ASSESSMENT",
        b"NON-ISSUEABLE PDF",
        b"NON-ISSUEABLE PREVIEW - NOT FOR REGULATORY",
        b"Tc-99m source summary",
        b"Barrier 1: North wall",
        b"Assessment status",
        b"Calculation provenance",
    ):
        assert expected in pdf


def test_step33_preserves_step25_nonreportable_dose_wording_in_pdf():
    pdf = render_non_issueable_spect_pdf_preview(_view_model(3.0)).pdf_bytes
    assert b"Transmitted weekly dose" in pdf
    assert b"Not reported" in pdf


def test_step33_pdf_metadata_is_explicitly_non_issueable():
    pdf = render_non_issueable_spect_pdf_preview(_view_model()).pdf_bytes
    assert b"SPECT Shielding Assessment - Non-Issueable PDF Preview" in pdf
    assert SPECT_PDF_PREVIEW_BASELINE.encode("ascii") in pdf


def test_step33_fails_closed_for_drifted_or_open_view_model():
    view = _view_model()
    opened = deepcopy(view)
    opened["report_integration_open"] = True
    with pytest.raises(SpectPdfPreviewError, match="closed and non-issueable"):
        render_non_issueable_spect_pdf_preview(opened)

    drifted = deepcopy(view)
    drifted["view_model_baseline"] = "future"
    with pytest.raises(SpectPdfPreviewError, match="baseline"):
        render_non_issueable_spect_pdf_preview(drifted)


def test_step33_rejects_multiline_injection_via_frozen_step31_validator():
    view = _view_model()
    view["source_summary"]["rows"][0]["value"] = "Tc-99m\nunsafe"
    with pytest.raises(Exception, match="single-line"):
        render_non_issueable_spect_pdf_preview(view)


def test_step33_does_not_mutate_view_model():
    view = _view_model()
    before = deepcopy(view)
    render_non_issueable_spect_pdf_preview(view)
    assert view == before


def test_step33_remains_disconnected_from_issueable_output_routes():
    token = "spect_report_pdf_preview"
    for path in list(Path("reports").glob("*.py")) + [
        Path("services/export_eligibility.py"),
        Path("services/report_certification.py"),
        Path("services/report_wording_guard.py"),
    ]:
        assert token not in path.read_text(encoding="utf-8-sig")

    module_text = Path("services/spect_report_pdf_preview.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "from reports", "import reports", "output_pipeline", "results_exporter",
        "export_eligibility", "report_certification",
    ):
        assert forbidden not in module_text


def test_step33_audit_document_records_isolated_non_issueable_boundary():
    text = Path("docs/architecture/SPECT_NonIssueable_PDF_Preview_Step_33.md").read_text(encoding="utf-8-sig")
    assert "NON-ISSUEABLE" in text
    assert "in-memory PDF bytes" in text
    assert "Step 22 remains authoritative" in text
    assert "issued SPECT PDF" in text
