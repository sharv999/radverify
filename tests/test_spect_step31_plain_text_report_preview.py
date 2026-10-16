from copy import deepcopy
from pathlib import Path

import pytest

from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state, set_room_spect_working_state
from services.spect_report_payload_harness import build_non_issueable_spect_report_payload
from services.spect_report_plain_text_preview import (
    SPECT_PLAIN_TEXT_PREVIEW_BASELINE,
    SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION,
    SPECT_PLAIN_TEXT_PREVIEW_FOOTER,
    SPECT_PLAIN_TEXT_PREVIEW_HEADER,
    SpectPlainTextPreviewError,
    render_non_issueable_spect_plain_text_preview,
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
    rows = build_room_results_model(Project(project_name="SPECT", rooms=[room]), room, fallback_results=[])
    source = build_non_issueable_spect_source_summary(room)
    barriers = build_non_issueable_spect_report_payload(rows)
    return build_non_issueable_spect_report_section_view_model(source_payload=source, barrier_payload=barriers)


def test_step31_renders_deterministic_non_issueable_plain_text_preview():
    view = _view_model()
    text = render_non_issueable_spect_plain_text_preview(view)
    assert text == render_non_issueable_spect_plain_text_preview(view)
    assert text.startswith(SPECT_PLAIN_TEXT_PREVIEW_HEADER + "\n")
    assert text.endswith(SPECT_PLAIN_TEXT_PREVIEW_FOOTER + "\n")
    assert "NON-ISSUEABLE PREVIEW" in text
    assert "Tc-99m source summary" in text
    assert "Barrier 1: North wall" in text
    assert "Assessment status:" in text
    assert "Calculation provenance" in text
    assert f"Preview contract: v{SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION} — {SPECT_PLAIN_TEXT_PREVIEW_BASELINE}" in text


def test_step31_preserves_step30_nonreportable_dose_wording():
    text = render_non_issueable_spect_plain_text_preview(_view_model(3.0))
    assert "Transmitted weekly dose: Not reported µSv/week" in text


def test_step31_fails_closed_for_open_or_drifted_view_model():
    view = _view_model()
    opened = deepcopy(view)
    opened["report_integration_open"] = True
    with pytest.raises(SpectPlainTextPreviewError, match="closed and non-issueable"):
        render_non_issueable_spect_plain_text_preview(opened)

    drifted = deepcopy(view)
    drifted["barrier_table"]["rows"][0]["unexpected"] = "x"
    with pytest.raises(SpectPlainTextPreviewError, match="field order drifted"):
        render_non_issueable_spect_plain_text_preview(drifted)

    wrong_baseline = deepcopy(view)
    wrong_baseline["view_model_baseline"] = "future"
    with pytest.raises(SpectPlainTextPreviewError, match="baseline"):
        render_non_issueable_spect_plain_text_preview(wrong_baseline)


def test_step31_rejects_multiline_content_even_after_view_model_construction():
    view = _view_model()
    view["source_summary"]["rows"][0]["value"] = "Tc-99m\nunsafe"
    with pytest.raises(SpectPlainTextPreviewError, match="single-line"):
        render_non_issueable_spect_plain_text_preview(view)


def test_step31_module_remains_pure_and_disconnected_from_issueable_outputs():
    module_path = Path("services/spect_report_plain_text_preview.py")
    text = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "reportlab", "openpyxl", "json.dump", "Path(", "open(", "reports.",
        "output_pipeline", "export_eligibility", "report_certification", "results_exporter",
    ):
        assert forbidden not in text

    token = "spect_report_plain_text_preview"
    for path in list(Path("reports").glob("*.py")) + [
        Path("services/export_eligibility.py"),
        Path("services/report_certification.py"),
        Path("reports/output_pipeline.py"),
        Path("reports/results_exporter.py"),
    ]:
        assert token not in path.read_text(encoding="utf-8-sig")


def test_step31_renderer_does_not_mutate_frozen_step30_view_model():
    view = _view_model()
    before = deepcopy(view)
    render_non_issueable_spect_plain_text_preview(view)
    assert view == before
