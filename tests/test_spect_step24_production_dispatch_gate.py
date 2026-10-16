from __future__ import annotations

from pathlib import Path

import pytest

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest
from engine.spect_production_dispatch_gate import (
    SPECT_DISPATCH_DISABLED_REASON,
    SPECT_LOW_TRANSMISSION_BLOCK_REASON,
    SPECT_PRODUCTION_DISPATCH_ENABLED,
    SpectProductionDispatchBlockedError,
    assess_spect_production_dispatch_readiness,
    require_spect_production_dispatch_enabled,
)
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state


ROOT = Path(__file__).resolve().parents[1]


def _state():
    return new_spect_working_project_state(
        SpectSourceDomain(
            radionuclide="Tc99m",
            administered_activity_mbq=720.0,
            patients_per_week=25.0,
            imaging_duration_h=0.65,
        )
    )


def _barriers():
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
    )


def test_step24_foundations_now_support_step26_isolated_dispatch():
    result = assess_spect_production_dispatch_readiness()
    assert result.validated_foundations is True
    assert result.production_ready is True
    assert result.dispatch_enabled is True
    assert SPECT_LOW_TRANSMISSION_BLOCK_REASON not in result.blocking_reasons
    assert SPECT_DISPATCH_DISABLED_REASON not in result.blocking_reasons


def test_step24_audit_explicitly_verifies_steps_20_to_23():
    result = assess_spect_production_dispatch_readiness(
        state=_state(),
        barrier_requests=_barriers(),
    )
    checks = {check.name: check for check in result.checks}
    assert checks["Step 20 physics freeze"].status == "PASS"
    assert checks["Step 21 deterministic replay"].status == "PASS"
    assert checks["Step 22 source/output blocker"].status == "PASS"
    assert checks["Step 23 working-project boundary"].status == "PASS"


def test_step24_low_transmission_policy_is_now_resolved_by_step25():
    result = assess_spect_production_dispatch_readiness()
    check = next(c for c in result.checks if c.name == "Low-transmission production policy")
    assert check.status == "PASS"
    assert "required transmission" in check.detail.lower()


def test_step24_explicit_dispatch_switch_is_now_open_for_step26():
    assert SPECT_PRODUCTION_DISPATCH_ENABLED is True
    result = assess_spect_production_dispatch_readiness()
    check = next(c for c in result.checks if c.name == "Explicit production dispatch switch")
    assert check.status == "PASS"
    assert result.dispatch_enabled is True


def test_step24_gate_allows_valid_step23_state_and_request_for_step26_only():
    readiness = require_spect_production_dispatch_enabled(_state(), _barriers())
    assert readiness.dispatch_enabled is True
    assert readiness.production_ready is True


def test_step24_partial_dispatch_context_fails_closed():
    with pytest.raises(SpectProductionDispatchBlockedError, match="both SPECT working state and barrier requests"):
        assess_spect_production_dispatch_readiness(state=_state())


def test_step24_registry_and_step22_calculation_blocker_remain_closed():
    assert "SPECT" in production_modality_names()
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON


def test_step24_gate_does_not_leak_into_existing_production_dispatch_results_or_reports():
    forbidden = (
        "spect_production_dispatch_gate",
        "require_spect_production_dispatch_enabled",
        "SPECT_PRODUCTION_DISPATCH_ENABLED",
    )
    paths = [
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "tabs" / "results_tab_rendering.py",
        ROOT / "reports" / "results_payload_builder.py",
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "services" / "export_eligibility.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined
