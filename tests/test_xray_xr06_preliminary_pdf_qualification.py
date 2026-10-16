from pathlib import Path

import pytest

from reports.report_generator import render_pdf_from_payload
from reports.results_payload_builder import build_results_payload
from services.xray_results_model import build_xray_results_model, XRAY_RESULTS_MODEL_VERSION
from tests.test_xray_xr05_persistence_results import _project

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


class _Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value


class _App:
    def __init__(self, project):
        self.project = project
        self.project_vars = {}
        self.global_energy_var = _Var("xray_120kvp")
        self.solver_mode_var = _Var("auto")

    def get_sources_for_room(self, room_name):
        return [s for s in self.project.sources if s.room_name == room_name]

    def _row_confidence_from_live(self, *_args):
        return 1.0


def _payload():
    project = _project()
    return project, build_results_payload(_App(project), report_status="QUALIFICATION - NON-ISSUEABLE")


def test_xr06_report_payload_uses_xr05_canonical_results_exactly():
    project, payload = _payload()
    canonical = build_xray_results_model(project, project.rooms[0])
    room = payload["rooms"][0]
    assert room["xray_report_qualification"] == {
        "qualification_version": "xr06-preliminary-pdf-v1",
        "results_model_version": XRAY_RESULTS_MODEL_VERSION,
        "issued_output_enabled": False,
        "report_payload_qualified": True,
        "barrier_count": 3,
    }
    assert len(room["barriers"]) == len(canonical) == 3
    for report_row, result_row in zip(room["barriers"], canonical):
        for key in ("unshielded_weekly_dose_uSv", "transmitted_dose_uSv_per_week", "required_thickness_mm", "solver_used"):
            assert report_row[key] == result_row[key]


def test_xr06_source_design_basis_is_present_and_xr08_requalification_is_fail_closed():
    _project_obj, payload = _payload()
    source = payload["rooms"][0]["sources"][0]
    assert source["params"]["xray_method"] == "ncrp_simplified"
    assert source["params"]["exam_room_type"] == "general_radiography"
    assert source["params"]["exams_per_week"] == 125
    assert source["params"]["tube_potential_kvp"] == 120
    # XR-08 deliberately re-closes issued output while the complete NCRP 147
    # Section 5.3 / Figure 5.2 representative-room model is requalified.
    assert payload["export_eligibility"]["can_export_pdf"] is False
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["export_eligibility"]["can_certify"] is False


def test_xr06_renders_nonissueable_preliminary_pdf_with_xray_design_basis(tmp_path):
    _project_obj, payload = _payload()
    path = tmp_path / "xray_xr06_qualification.pdf"
    render_pdf_from_payload(payload, path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 5000
    if PdfReader is not None:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        assert "X-ray" in text or "X-RAY" in text
        assert "NCRP 147 simplified general radiography" in text
        assert "125 exams/week" in text
        assert "120 kVp" in text
        assert "Barrier schedule" in text
        assert "primary_bucky_wall" in text or "Primary" in text
        assert "QUALIFICATION - NON-ISSUEABLE" in text


def test_xr06_known_answer_barrier_thicknesses_are_preserved_in_report_payload():
    _project_obj, payload = _payload()
    rows = payload["rooms"][0]["barriers"]
    assert rows[0]["solver_used"] == "ncrp147_archer_primary_bucky_wall"
    assert rows[1]["solver_used"] == "ncrp147_archer_primary_floor"
    assert rows[2]["solver_used"] == "ncrp147_archer_secondary_wall"
    assert all(float(row["required_thickness_mm"]) >= 0.0 for row in rows)
