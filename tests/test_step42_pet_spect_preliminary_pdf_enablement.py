from __future__ import annotations

from pathlib import Path

import pytest

from reports.output_pipeline import generate_outputs_from_app
from reports.results_payload_builder import build_results_payload
from services.project_io import load_project_from_file
from services.pet_spect_preliminary_pdf_issuance import (
    PetSpectPreliminaryPdfIssuanceError,
    authorize_issueable_preliminary_pet_spect_pdf,
    assess_step42_preliminary_pdf_enablement,
)
from tests.test_step40_pet_spect_normal_report_integration import _App, _pet_project, _spect_project

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("factory", [_pet_project, _spect_project])
def test_step42_authorizes_only_preliminary_pdf_and_keeps_all_other_output_closed(factory):
    project, _ = factory()
    payload = build_results_payload(_App(project), report_status="Draft")
    assert payload["export_eligibility"]["can_export_pdf"] is False

    authorize_issueable_preliminary_pet_spect_pdf(payload)

    gate = payload["preliminary_pdf_issuance"]
    assert gate["issueable"] is True
    assert gate["preliminary_pdf_enabled"] is True
    assert gate["machine_export_enabled"] is False
    assert gate["certification_enabled"] is False
    assert gate["signature_enabled"] is False
    assert payload["export_eligibility"]["can_export_pdf"] is True
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["export_eligibility"]["can_certify"] is False
    assert payload["certification"]["certification_allowed"] is False
    assert payload["certification"]["signature_allowed"] is False
    assert payload["meta"]["report_status"] == "Preliminary"
    assert payload["meta"]["report_status_effective"] == "Preliminary — Issueable"
    assert "Preliminary" in payload["meta"]["report_title"]


@pytest.mark.parametrize("factory", [_pet_project, _spect_project])
def test_step42_normal_output_pipeline_generates_issueable_preliminary_pdf_without_machine_exports(tmp_path, factory):
    project, _ = factory()
    app = _App(project)
    app.apply_project_form = lambda: None
    app.refresh_results_tab = lambda: None
    app._safe_refresh_barrier_schedule = lambda: None

    path = tmp_path / "preliminary.pdf"
    result = generate_outputs_from_app(app=app, output_path=path, report_status="Draft")

    assert result.generated is True
    assert path.exists() and path.read_bytes().startswith(b"%PDF-")
    assert set(result.export_paths) == {"barrier_results_json"}
    assert result.export_paths["barrier_results_json"].exists()
    assert result.export_eligibility["can_export_pdf"] is True
    assert result.export_eligibility["can_export_csv"] is False
    assert result.export_eligibility["can_certify"] is False
    assert result.payload["certification"]["certification_allowed"] is False
    assert result.payload["certification"]["signature_allowed"] is False
    assert result.payload["meta"]["report_status"] == "Preliminary"

    if PdfReader is not None:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        assert "Preliminary" in text
        assert "North wall" in text
        assert "certificate of shielding compliance" in text.lower()


def test_step42_pipeline_generates_preliminary_pdf_for_saved_spect_fail_case(tmp_path):
    project = load_project_from_file(ROOT / "tests" / "fixtures" / "KAT_SPECT_red_room_project.json")
    app = _App(project)
    app.apply_project_form = lambda: None
    app.refresh_results_tab = lambda: None
    app._safe_refresh_barrier_schedule = lambda: None

    path = tmp_path / "spect_fail_preliminary.pdf"
    result = generate_outputs_from_app(app=app, output_path=path, report_status="Draft")

    assert result.generated is True
    assert path.exists() and path.read_bytes().startswith(b"%PDF-")
    assert result.payload["summary"]["fail_count"] >= 1
    assert result.payload["preliminary_pdf_issuance"]["assessment_status"] == "FAIL"
    assert result.payload["preliminary_pdf_issuance"]["issueable"] is True
    assert result.payload["export_eligibility"]["can_export_pdf"] is True
    assert result.payload["certification"]["certification_allowed"] is False

    if PdfReader is not None:
        reader = PdfReader(str(path))
        assert len(reader.pages) == 6
        page3_text = reader.pages[2].extract_text() or ""
        assert "4. Barrier plan" in page3_text
        assert "Project note:" not in page3_text


def test_step42_rejects_final_certified_or_issued_status():
    project, _ = _pet_project()
    payload = build_results_payload(_App(project), report_status="Final")
    with pytest.raises(PetSpectPreliminaryPdfIssuanceError, match="Preliminary"):
        authorize_issueable_preliminary_pet_spect_pdf(payload)


@pytest.mark.parametrize(
    ("status", "review_count", "fail_count"),
    [("REVIEW", 1, 0), ("FAIL", 0, 1)],
)
def test_step42_allows_review_or_fail_room_for_preliminary_design_report(status, review_count, fail_count):
    project, _ = _spect_project()
    payload = build_results_payload(_App(project))
    payload["rooms"][0]["overall_status"] = status
    payload["rooms"][0]["review_count"] = review_count
    payload["rooms"][0]["fail_count"] = fail_count
    payload["summary"]["review_count"] = review_count
    payload["summary"]["fail_count"] = fail_count

    authorize_issueable_preliminary_pet_spect_pdf(payload)

    assert payload["export_eligibility"]["can_export_pdf"] is True
    assert payload["preliminary_pdf_issuance"]["issueable"] is True
    assert payload["preliminary_pdf_issuance"]["assessment_status"] == status
    assert payload["preliminary_pdf_issuance"]["contains_nonpassing_barriers"] is True
    assert payload["certification"]["assessment_status"] == status
    assert payload["certification"]["certification_allowed"] is False
    assert payload["export_eligibility"]["warnings"]


def test_step42_rejects_non_pet_spect_payload():
    payload = {
        "meta": {"report_status": "Draft"},
        "rooms": [{"modality": "CT", "overall_status": "PASS", "review_count": 0, "fail_count": 0}],
        "summary": {"review_count": 0, "fail_count": 0},
        "calculation_integrity": {"blocking": False},
        "source_readiness": {"errors": []},
    }
    with pytest.raises(PetSpectPreliminaryPdfIssuanceError, match="PET/SPECT-only"):
        authorize_issueable_preliminary_pet_spect_pdf(payload)


def test_step42_gate_records_only_preliminary_pdf_enablement():
    result = assess_step42_preliminary_pdf_enablement()
    assert result["step41_qualification_complete"] is True
    assert result["preliminary_pdf_enabled"] is True
    assert result["final_or_certified_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["barrier_results_json_enabled"] is True
    assert result["certification_enabled"] is False
    assert result["signature_enabled"] is False


def test_step42_cli_reports_preliminary_only_enablement(capsys):
    from tools import pet_spect_preliminary_pdf_enablement

    assert pet_spect_preliminary_pdf_enablement.main() == 0
    out = capsys.readouterr().out
    assert "PET/SPECT STEP 42 PRELIMINARY PDF ENABLEMENT" in out
    assert "Preliminary PDF enabled: YES" in out
    assert "Final/certified PDF enabled: NO" in out
    assert "Machine export enabled: NO" in out
    assert "Certification enabled: NO" in out


def test_step42_output_pipeline_uses_dedicated_authorization_without_enabling_export_or_certification():
    text = (ROOT / "reports" / "output_pipeline.py").read_text(encoding="utf-8-sig")
    assert "authorize_issueable_preliminary_pet_spect_pdf" in text
    assert "is_pet_spect_preliminary_pdf_candidate" in text
    service = (ROOT / "services" / "pet_spect_preliminary_pdf_issuance.py").read_text(encoding="utf-8")
    assert "STEP42_PRELIMINARY_PDF_ENABLED = True" in service
    assert "STEP42_MACHINE_EXPORT_ENABLED = False" in service
    assert "STEP42_BARRIER_RESULTS_JSON_ENABLED = True" in service
    assert "STEP42_CERTIFICATION_ENABLED = False" in service
    assert "STEP42_SIGNATURE_ENABLED = False" in service


def test_step42_document_records_preliminary_go_but_certification_no_go():
    text = (ROOT / "docs" / "architecture" / "PET_SPECT_Preliminary_PDF_Enablement_Step_42.md").read_text(encoding="utf-8")
    assert "GO for issueable Preliminary Shielding Assessment PDF" in text
    assert "Final/certified PDF: **DISABLED**" in text
    assert "Certification: **DISABLED**" in text
