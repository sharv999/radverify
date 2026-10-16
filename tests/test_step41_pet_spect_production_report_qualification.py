from __future__ import annotations

import json
from pathlib import Path

import pytest

from reports.report_generator import render_pdf_from_payload
from reports.results_payload_builder import build_results_payload
from services.project_io import load_project_from_file, write_project_payload
from services.project_serializer import project_to_working_dict
from services.pet_results_model import build_room_results_model as build_pet_results_model
from services.spect_results_model import build_room_results_model as build_spect_results_model
from services.pet_spect_production_report_qualification import (
    require_step41_production_report_qualification,
)
from tests.test_step40_pet_spect_normal_report_integration import _App, _pet_project, _spect_project

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

ROOT = Path(__file__).resolve().parents[1]

KNOWN = {
    "PET": {
        "unshielded_weekly_dose_uSv": 11.965508612353315,
        "transmitted_dose_uSv_per_week": 1.4567035290771286,
        "provided_transmission": 0.4869675251658631,
        "required_thickness_mm": 0.0,
        "status": "PASS",
    },
    "SPECT": {
        "unshielded_weekly_dose_uSv": 13.344652675476675,
        "transmitted_dose_uSv_per_week": 0.23936053869242221,
        "provided_transmission": 0.07174725173096262,
        "required_thickness_mm": 0.0,
        "status": "PASS",
    },
}


def _reopen(project, tmp_path: Path):
    path = tmp_path / "working_project.json"
    write_project_payload(path, project_to_working_dict(project))
    return load_project_from_file(path)


def _stable_room_payload(payload):
    room = payload["rooms"][0]
    return {
        "modality": room["modality"],
        "barriers": room["barriers"],
        "route": room["pet_spect_report_route"],
        "overall_status": room["overall_status"],
        "wall_result_count": room["wall_result_count"],
    }


@pytest.mark.parametrize("modality,factory,builder", [
    ("PET", _pet_project, build_pet_results_model),
    ("SPECT", _spect_project, build_spect_results_model),
])
def test_step41_save_reopen_replays_results_and_report_payload_deterministically(tmp_path, modality, factory, builder):
    project, room = factory()
    first_results = builder(project, room, fallback_results=[])
    first_payload = build_results_payload(_App(project))

    restored = _reopen(project, tmp_path)
    restored_room = restored.rooms[0]
    second_results = builder(restored, restored_room, fallback_results=[])
    second_payload = build_results_payload(_App(restored))

    assert second_results == first_results
    assert _stable_room_payload(second_payload) == _stable_room_payload(first_payload)
    assert second_payload["export_eligibility"]["can_export_pdf"] is False
    assert second_payload["export_eligibility"]["can_export_csv"] is False
    assert second_payload["export_eligibility"]["can_certify"] is False


@pytest.mark.parametrize("modality,factory,builder", [
    ("PET", _pet_project, build_pet_results_model),
    ("SPECT", _spect_project, build_spect_results_model),
])
def test_step41_report_route_is_equivalent_to_post_reopen_canonical_results(tmp_path, modality, factory, builder):
    project, _ = factory()
    restored = _reopen(project, tmp_path)
    room = restored.rooms[0]
    results = builder(restored, room, fallback_results=[])
    payload = build_results_payload(_App(restored))
    adapted = payload["rooms"][0]["pet_spect_report_route"]["payload"]["barriers"]
    assert len(adapted) == len(results) == 1
    report_row = adapted[0]["result_payload"]
    for key, value in report_row.items():
        assert key in results[0]
        assert value == results[0][key]


@pytest.mark.parametrize("modality,factory,builder", [
    ("PET", _pet_project, build_pet_results_model),
    ("SPECT", _spect_project, build_spect_results_model),
])
def test_step41_representative_known_answer_case_is_pinned(modality, factory, builder):
    project, room = factory()
    row = builder(project, room, fallback_results=[])[0]
    expected = KNOWN[modality]
    assert row["unshielded_weekly_dose_uSv"] == pytest.approx(expected["unshielded_weekly_dose_uSv"], rel=1e-12)
    assert row["transmitted_dose_uSv_per_week"] == pytest.approx(expected["transmitted_dose_uSv_per_week"], rel=1e-12)
    assert row["provided_transmission"] == pytest.approx(expected["provided_transmission"], rel=1e-12)
    assert row["required_thickness_mm"] == pytest.approx(expected["required_thickness_mm"], abs=1e-12)
    assert row["compliance_status"] == expected["status"]


@pytest.mark.parametrize("modality,factory", [("PET", _pet_project), ("SPECT", _spect_project)])
def test_step41_visual_report_qualification_renders_preliminary_payload_without_opening_output(tmp_path, modality, factory):
    project, _ = factory()
    payload = build_results_payload(_App(project), report_status="QUALIFICATION — NON-ISSUEABLE")
    pdf_path = tmp_path / f"{modality.lower()}_qualification.pdf"
    render_pdf_from_payload(payload, pdf_path)
    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 5000
    assert payload["export_eligibility"]["can_export_pdf"] is False
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["export_eligibility"]["can_certify"] is False
    if PdfReader is not None:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
        assert modality in text
        assert "Barrier schedule" in text
        assert "North wall" in text


def test_step41_gate_records_qualification_complete_but_all_issued_outputs_closed():
    result = require_step41_production_report_qualification()
    assert result["production_report_qualification_complete"] is True
    assert result["save_reopen_replay_qualified"] is True
    assert result["results_report_equivalence_qualified"] is True
    assert result["known_answer_cases_qualified"] is True
    assert result["visual_report_validation_qualified"] is True
    assert result["issued_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["certification_enabled"] is False
    assert result["signature_enabled"] is False


def test_step41_cli_reports_qualified_but_closed(capsys):
    from tools import pet_spect_production_report_qualification
    assert pet_spect_production_report_qualification.main() == 0
    out = capsys.readouterr().out
    assert "PET/SPECT STEP 41 PRODUCTION REPORT QUALIFICATION" in out
    assert "Production report qualification complete: YES" in out
    assert "Issued PDF enabled: NO" in out
    assert "Machine export enabled: NO" in out
    assert "Certification enabled: NO" in out


def test_step41_qualification_module_has_no_output_enablement_side_effects():
    text = (ROOT / "services" / "pet_spect_production_report_qualification.py").read_text(encoding="utf-8")
    assert "STEP41_ISSUED_PDF_ENABLED = False" in text
    assert "STEP41_MACHINE_EXPORT_ENABLED = False" in text
    assert "STEP41_CERTIFICATION_ENABLED = False" in text
    assert "reports.output_pipeline" not in text
    assert "report_certification" not in text
