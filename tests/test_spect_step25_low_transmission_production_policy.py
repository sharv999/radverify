from __future__ import annotations

from dataclasses import replace

from engine.spect_barrier_schedule import (
    SpectBarrierScheduleRequest,
    calculate_spect_tc99m_barrier_schedule,
)
from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
    SPECT_LOW_TRANSMISSION_POLICY_STATUS,
    SPECT_LOW_TRANSMISSION_POLICY_VERSION,
    SPECT_LOW_TRANSMISSION_REVIEW_STATUS,
    SPECT_LOW_TRANSMISSION_THRESHOLD,
    assess_spect_low_transmission_policy,
    assess_spect_production_barrier_policy,
)
from engine.spect_production_dispatch_gate import (
    SPECT_DISPATCH_DISABLED_REASON,
    assess_spect_production_dispatch_readiness,
)
from modalities.spect import SpectSourceDomain


def _source():
    return SpectSourceDomain(
        radionuclide="Tc99m",
        administered_activity_mbq=600.0,
        patients_per_week=20.0,
        imaging_duration_h=0.5,
    )


def _row_for_goal(goal: float, *, provided: float | None = None):
    schedule = calculate_spect_tc99m_barrier_schedule(
        _source(),
        (
            SpectBarrierScheduleRequest(
                barrier_id="north",
                barrier_name="North wall",
                material_key="lead",
                distance_m=1.0,
                occupancy_factor=1.0,
                design_goal_uSv_per_week=goal,
                provided_thickness_mm=provided,
                source_name="SPECT patient",
            ),
        ),
    )
    return schedule.rows[0]


def test_step25_policy_is_explicit_approved_and_pinned_to_one_percent():
    assert SPECT_LOW_TRANSMISSION_POLICY_APPROVED is True
    assert SPECT_LOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
    assert SPECT_LOW_TRANSMISSION_POLICY_VERSION == 1
    assert SPECT_LOW_TRANSMISSION_THRESHOLD == 0.01


def test_step25_required_transmission_at_or_below_one_percent_requires_review():
    # occupied unshielded is ~120.1 uSv/week here; 1.0 uSv/week therefore requires <1%.
    row = _row_for_goal(1.0, provided=2.0)
    assert row.required_transmission <= 0.01
    decision = assess_spect_production_barrier_policy(row)
    assert decision.status == SPECT_LOW_TRANSMISSION_REVIEW_STATUS
    assert decision.automatic_assessment_allowed is False
    assert decision.production_transmitted_dose_reportable is False


def test_step25_exact_threshold_is_fail_closed():
    row = _row_for_goal(2.0)
    row = replace(
        row,
        required_transmission=0.01,
        required_room_scatter_caution=True,
        required_source_model_extrapolation=False,
    )
    decision = assess_spect_production_barrier_policy(row)
    assert decision.status == SPECT_LOW_TRANSMISSION_REVIEW_STATUS
    assert decision.automatic_assessment_allowed is False


def test_step25_above_threshold_uses_thickness_comparison_for_pass_fail():
    base = _row_for_goal(20.0)
    assert base.required_transmission > 0.01
    passing = replace(
        base,
        provided_thickness_mm=base.required_thickness_mm + 0.1,
        provided_transmission=0.005,
        provided_room_scatter_caution=True,
        transmitted_weekly_dose_uSv=0.000001,  # deliberately irrelevant to policy decision
        compliance_status="PASS",
    )
    failing = replace(
        base,
        provided_thickness_mm=max(0.0, base.required_thickness_mm - 0.1),
        provided_transmission=0.5,
        provided_room_scatter_caution=False,
        transmitted_weekly_dose_uSv=999999.0,  # deliberately irrelevant to policy decision
        compliance_status="FAIL",
    )
    pass_decision = assess_spect_production_barrier_policy(passing)
    fail_decision = assess_spect_production_barrier_policy(failing)
    assert pass_decision.status == "PASS"
    assert fail_decision.status == "FAIL"


def test_step25_ultralow_provided_transmission_is_not_reportable_as_production_dose():
    base = _row_for_goal(20.0)
    row = replace(
        base,
        provided_thickness_mm=base.required_thickness_mm + 5.0,
        provided_transmission=0.001,
        provided_room_scatter_caution=True,
        compliance_status="PASS",
    )
    decision = assess_spect_production_barrier_policy(row)
    assert decision.status == "PASS"
    assert decision.automatic_assessment_allowed is True
    assert decision.production_transmitted_dose_reportable is False
    assert "thickness" in decision.decision_basis.lower()


def test_step25_missing_provided_thickness_remains_not_assessed_above_threshold():
    row = _row_for_goal(20.0)
    decision = assess_spect_production_barrier_policy(row)
    assert decision.status == "NOT_ASSESSED"
    assert decision.automatic_assessment_allowed is True
    assert decision.production_transmitted_dose_reportable is False


def test_step25_schedule_aggregates_review_required_rows():
    schedule = calculate_spect_tc99m_barrier_schedule(
        _source(),
        (
            SpectBarrierScheduleRequest("north", "North", "lead", 1.0, 1.0, 1.0, 2.0),
            SpectBarrierScheduleRequest("south", "South", "lead", 2.0, 1.0, 20.0, 1.0),
        ),
    )
    assessment = assess_spect_low_transmission_policy(schedule)
    assert assessment.approved is True
    assert assessment.review_required_count == 1
    assert assessment.automatic_production_assessment_allowed is False


def test_step25_policy_remains_resolved_after_step26_dispatch_enablement():
    readiness = assess_spect_production_dispatch_readiness()
    checks = {c.name: c for c in readiness.checks}
    assert checks["Low-transmission production policy"].status == "PASS"
    assert "required transmission" in checks["Low-transmission production policy"].detail.lower()
    assert readiness.dispatch_enabled is True
    assert readiness.production_ready is True
    assert SPECT_DISPATCH_DISABLED_REASON not in readiness.blocking_reasons


def test_step25_does_not_promote_spect_registry_or_remove_step22_blocker():
    from modalities.registry import production_modality_names, source_calculation_blocked_reason
    from modalities.spect import SPECT_CALCULATION_BLOCK_REASON

    assert "SPECT" in production_modality_names()
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON
