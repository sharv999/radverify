from __future__ import annotations

import pytest

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest
from engine.spect_production_dispatch import (
    SPECT_PRODUCTION_DISPATCH_VERSION,
    SpectProductionPolicyReviewRequiredError,
    dispatch_spect_production_calculation,
)
from engine.spect_production_dispatch_gate import (
    SPECT_PRODUCTION_DISPATCH_ENABLED,
    assess_spect_production_dispatch_readiness,
)
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state


def _state():
    return new_spect_working_project_state(
        SpectSourceDomain(
            radionuclide="Tc99m",
            administered_activity_mbq=600.0,
            patients_per_week=20.0,
            imaging_duration_h=0.5,
        )
    )


def _supported_barriers():
    return (
        SpectBarrierScheduleRequest(
            barrier_id="north",
            barrier_name="North wall",
            material_key="lead",
            distance_m=2.0,
            occupancy_factor=1.0,
            design_goal_uSv_per_week=1.0,
            provided_thickness_mm=1.0,
            source_name="SPECT patient",
        ),
        SpectBarrierScheduleRequest(
            barrier_id="south",
            barrier_name="South wall",
            material_key="concrete_2300kg_m3",
            distance_m=3.0,
            occupancy_factor=0.25,
            design_goal_uSv_per_week=10.0,
            provided_thickness_mm=150.0,
            source_name="SPECT patient",
        ),
    )


def test_step26_explicit_headless_production_switch_is_enabled():
    assert SPECT_PRODUCTION_DISPATCH_ENABLED is True
    readiness = assess_spect_production_dispatch_readiness(
        state=_state(),
        barrier_requests=_supported_barriers(),
    )
    assert readiness.validated_foundations is True
    assert readiness.production_ready is True
    assert readiness.dispatch_enabled is True
    checks = {c.name: c for c in readiness.checks}
    assert checks["Explicit production dispatch switch"].status == "PASS"


def test_step26_supported_request_returns_production_wrapper_only():
    result = dispatch_spect_production_calculation(_state(), _supported_barriers())
    assert result.dispatch_version == SPECT_PRODUCTION_DISPATCH_VERSION
    assert result.production_eligible is True
    assert result.output_eligible is False
    assert result.results_integration_enabled is False
    assert result.report_integration_enabled is False
    # Historical Step 5 remains the frozen calculation substrate and is not
    # itself relabelled production-eligible.
    assert result.schedule.production_eligible is False
    assert result.low_transmission_policy.automatic_production_assessment_allowed is True
    assert result.readiness.dispatch_enabled is True


def test_step26_dispatch_is_deterministic_for_same_canonical_request():
    first = dispatch_spect_production_calculation(_state(), _supported_barriers())
    second = dispatch_spect_production_calculation(_state(), _supported_barriers())
    assert first.request_sha256 == second.request_sha256
    assert first.schedule == second.schedule
    assert first.low_transmission_policy == second.low_transmission_policy


def test_step26_low_transmission_case_fails_closed_to_manual_review():
    barriers = (
        SpectBarrierScheduleRequest(
            barrier_id="critical",
            barrier_name="Critical wall",
            material_key="lead",
            distance_m=1.0,
            occupancy_factor=1.0,
            design_goal_uSv_per_week=1.0,
            provided_thickness_mm=3.0,
            source_name="SPECT patient",
        ),
    )
    with pytest.raises(SpectProductionPolicyReviewRequiredError, match="critical"):
        dispatch_spect_production_calculation(_state(), barriers)


def test_step26_source_model_extrapolation_also_fails_closed():
    # Build a valid supported row first, then rely on the real Step 25 policy
    # through an extreme design target that forces the practical model outside
    # its supported automatic range.
    barriers = (
        SpectBarrierScheduleRequest(
            barrier_id="extreme",
            barrier_name="Extreme wall",
            material_key="lead",
            distance_m=1.0,
            occupancy_factor=1.0,
            design_goal_uSv_per_week=0.000001,
            provided_thickness_mm=20.0,
            source_name="SPECT patient",
        ),
    )
    with pytest.raises(SpectProductionPolicyReviewRequiredError, match="extreme"):
        dispatch_spect_production_calculation(_state(), barriers)


def test_step26_does_not_promote_desktop_registry_or_remove_step22_blocker():
    assert "SPECT" in production_modality_names()
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON


def test_step26_result_metadata_explicitly_keeps_output_surfaces_closed():
    payload = dispatch_spect_production_calculation(_state(), _supported_barriers()).as_dict()
    assert payload["production_eligible"] is True
    assert payload["output_eligible"] is False
    assert payload["results_integration_enabled"] is False
    assert payload["report_integration_enabled"] is False
    assert payload["barrier_count"] == 2


def test_step26_dispatch_is_not_imported_by_results_reports_or_export_services():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "spect_production_dispatch",
        "dispatch_spect_production_calculation",
        "SpectProductionCalculationResult",
    )
    paths = [
        root / "tabs" / "results_tab_rendering.py",
        root / "reports" / "results_payload_builder.py",
        root / "reports" / "output_pipeline.py",
        root / "services" / "export_eligibility.py",
        root / "engine" / "shielding_engine.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined
