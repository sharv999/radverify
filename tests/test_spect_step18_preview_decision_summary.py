"""Tests for SPECT Step 18 preview calculation summary / decision panel."""
from pathlib import Path

from engine.spect_barrier_schedule import SpectBarrierScheduleResult, SpectBarrierScheduleRow
from tabs.spect_preview_panel import (
    SPECT_UI_DECISION_SUMMARY_BASELINE,
    SPECT_UI_DECISION_SUMMARY_CONTRACT_VERSION,
    build_spect_preview_decision_summary,
    spect_preview_decision_summary_lines,
)

ROOT = Path(__file__).resolve().parents[1]


def _row(
    index,
    name,
    status,
    required_mm,
    transmitted=None,
    *,
    scatter=False,
    extrapolation=False,
):
    return SpectBarrierScheduleRow(
        schedule_index=index,
        barrier_id=f"b{index}",
        barrier_name=name,
        material_key="lead",
        distance_m=2.0,
        occupancy_factor=1.0,
        design_goal_uSv_per_week=10.0,
        unshielded_weekly_dose_uSv_at_barrier=100.0,
        occupied_unshielded_weekly_dose_uSv=100.0,
        required_transmission=0.1,
        required_thickness_mm=required_mm,
        provided_thickness_mm=required_mm if transmitted is not None else None,
        provided_transmission=0.05 if transmitted is not None else None,
        transmitted_weekly_dose_uSv=transmitted,
        compliance_status=status,
        required_room_scatter_caution=scatter,
        provided_room_scatter_caution=scatter if transmitted is not None else None,
        required_source_model_extrapolation=extrapolation,
        practical_record_id="tc99m-lead",
        practical_provenance="test provenance",
        required_scope_note="test",
        provided_scope_note="test" if transmitted is not None else None,
    )


def _result(rows):
    rows = tuple(rows)
    return SpectBarrierScheduleResult(
        contract_version=1,
        status="development_nonproduction",
        production_eligible=False,
        ordering_basis="caller_request_order",
        source_physics=None,
        rows=rows,
        pass_count=sum(r.compliance_status == "PASS" for r in rows),
        fail_count=sum(r.compliance_status == "FAIL" for r in rows),
        not_assessed_count=sum(r.compliance_status == "NOT_ASSESSED" for r in rows),
        requires_room_scatter_review=any(
            r.required_room_scatter_caution or r.provided_room_scatter_caution is True
            for r in rows
        ),
        contains_source_model_extrapolation=any(
            r.required_source_model_extrapolation for r in rows
        ),
    )


def test_step18_contract_is_explicitly_nonproduction_presentation_only():
    assert SPECT_UI_DECISION_SUMMARY_CONTRACT_VERSION == 12
    assert SPECT_UI_DECISION_SUMMARY_BASELINE == "spect-ui-preview-v12-decision-summary"


def test_step18_fail_has_priority_in_overall_status():
    result = _result([
        _row(0, "North", "PASS", 1.0, 4.0),
        _row(1, "South", "FAIL", 2.0, 12.0),
        _row(2, "East", "NOT_ASSESSED", 0.5),
    ])
    summary = build_spect_preview_decision_summary(result)
    assert summary.overall_status == "ONE OR MORE BARRIERS FAIL"
    assert (summary.pass_count, summary.fail_count, summary.not_assessed_count) == (1, 1, 1)


def test_step18_not_assessed_is_incomplete_when_there_are_no_fails():
    summary = build_spect_preview_decision_summary(
        _result([_row(0, "North", "PASS", 1.0, 4.0), _row(1, "East", "NOT_ASSESSED", 0.5)])
    )
    assert summary.overall_status == "INCOMPLETE ASSESSMENT"


def test_step18_all_assessed_barriers_pass_status():
    summary = build_spect_preview_decision_summary(
        _result([_row(0, "North", "PASS", 1.0, 4.0), _row(1, "West", "PASS", 1.5, 3.0)])
    )
    assert summary.overall_status == "ALL ASSESSED BARRIERS PASS"


def test_step18_empty_schedule_is_not_presented_as_a_pass():
    summary = build_spect_preview_decision_summary(_result([]))
    assert summary.overall_status == "NO BARRIERS TO ASSESS"
    assert summary.critical_barrier_name is None
    assert summary.highest_transmitted_barrier_name is None


def test_step18_critical_barrier_is_maximum_existing_required_thickness():
    result = _result([
        _row(0, "North", "PASS", 1.0, 4.0),
        _row(1, "South", "PASS", 3.25, 2.0),
        _row(2, "West", "PASS", 2.0, 1.0),
    ])
    summary = build_spect_preview_decision_summary(result)
    assert summary.critical_barrier_name == "South"
    assert summary.maximum_required_thickness_mm == 3.25


def test_step18_critical_barrier_tie_preserves_schedule_order():
    result = _result([
        _row(0, "North", "PASS", 2.0, 1.0),
        _row(1, "South", "PASS", 2.0, 1.0),
    ])
    assert build_spect_preview_decision_summary(result).critical_barrier_name == "North"


def test_step18_highest_transmitted_dose_ignores_not_assessed_rows():
    result = _result([
        _row(0, "North", "NOT_ASSESSED", 2.0),
        _row(1, "South", "PASS", 2.0, 8.5),
        _row(2, "West", "PASS", 1.0, 2.0),
    ])
    summary = build_spect_preview_decision_summary(result)
    assert summary.highest_transmitted_barrier_name == "South"
    assert summary.highest_transmitted_weekly_dose_uSv == 8.5


def test_step18_counts_scatter_and_extrapolation_rows_not_boolean_schedule_flags():
    result = _result([
        _row(0, "North", "PASS", 1.0, 2.0, scatter=True),
        _row(1, "South", "PASS", 1.0, 2.0, scatter=True, extrapolation=True),
        _row(2, "West", "PASS", 1.0, 2.0, extrapolation=True),
    ])
    summary = build_spect_preview_decision_summary(result)
    assert summary.room_scatter_caution_count == 2
    assert summary.source_model_extrapolation_count == 2


def test_step18_summary_lines_are_explicitly_preview_decision_language():
    summary = build_spect_preview_decision_summary(
        _result([_row(0, "North", "FAIL", 2.5, 14.0, scatter=True)])
    )
    text = "\n".join(spect_preview_decision_summary_lines(summary))
    assert "Overall: ONE OR MORE BARRIERS FAIL" in text
    assert "Critical barrier: North (2.5 mm required)" in text
    assert "Highest transmitted dose: North (14 µSv/week)" in text
    assert "scatter review 1" in text


def test_step18_panel_contains_nonproduction_summary_and_no_compliance_claim_language():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    assert "Preview calculation summary — non-production" in panel
    assert "SPECT_UI_DECISION_SUMMARY_BASELINE" in panel
    assert "certified" not in panel.lower()
    assert "compliance certificate" not in panel.lower()


def test_step18_summary_contract_stays_out_of_project_results_reports_and_production():
    forbidden = [
        ROOT / "models" / "shielding_models.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "app.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "SPECT_UI_DECISION_SUMMARY_BASELINE" not in text
        assert "SpectPreviewDecisionSummary" not in text
