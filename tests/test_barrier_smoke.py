from __future__ import annotations

"""
Smoke tests for barrier calculation pathways.

These tests are deliberately broad and lightweight. They are not physics
benchmark/known-answer tests. Their job is to catch obvious regressions such as:

    - example project no longer calculates
    - barrier table returns no rows
    - expected result keys disappear
    - CT ksec/manual override source state breaks barrier calculation
    - NULL CT ksec blocks calculation with a clear safety error

Run from project root:

    python -m pytest tests/test_barrier_smoke.py
"""

from copy import deepcopy
from typing import Any

import pytest

from engine.shielding_engine import (
    SOLVER_MODE_AUTO,
    build_example_project,
    calc_barrier_result,
    compute_room_barrier_table,
)
from models.shielding_models import Barrier, Room, Source


def _first_room(project) -> Room:
    assert getattr(project, "rooms", None), "example project has no rooms"
    return project.rooms[0]


def _first_barrier(room: Room) -> Barrier:
    assert getattr(room, "barriers", None), "room has no barriers"
    return room.barriers[0]


def _result_status(result: dict[str, Any]) -> str:
    return str(result.get("compliance_status", "") or "").strip().upper()


def _is_blank_result_value(value: Any) -> bool:
    """
    Barrier outputs may use ''/None/'-' for not-applicable numeric fields
    such as recommended commercial Pb thickness for concrete/floor barriers.
    """
    return value in ("", None, "-")


def _assert_smoke_result_shape(result: dict[str, Any]) -> None:
    assert isinstance(result, dict)

    # These keys are used widely by Results, Barriers, QA, and reports.
    for key in (
        "compliance_status",
        "required_lead_mm",
        "recommended_commercial_lead_mm",
        "barrier_transmission_factor_B",
        "solver_used",
    ):
        assert key in result

    assert _result_status(result) in {
        "PASS",
        "REVIEW",
        "FAIL",
        "ERROR",
        "WARN",
        "WARNING",
        "NON-COMPLIANT",
    }

    # Values may be blank/not applicable in floor/concrete/error/review cases,
    # but present numeric values should be convertible.
    for key in (
        "required_lead_mm",
        "recommended_commercial_lead_mm",
        "barrier_transmission_factor_B",
        "unshielded_weekly_dose_uSv",
        "transmitted_dose_uSv_per_week",
    ):
        value = result.get(key, "")
        if not _is_blank_result_value(value):
            float(value)


def test_example_project_room_barrier_table_smoke():
    project = build_example_project()
    room = _first_room(project)

    results = compute_room_barrier_table(
        project,
        room.name,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    assert isinstance(results, list)
    assert len(results) == len(room.barriers)

    for result in results:
        _assert_smoke_result_shape(result)


def test_single_barrier_result_smoke():
    project = build_example_project()
    room = _first_room(project)
    barrier = _first_barrier(room)

    result = calc_barrier_result(
        room,
        barrier,
        project,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    _assert_smoke_result_shape(result)


def test_ct_database_ksec_source_smoke_calculates_barriers():
    project = build_example_project()
    room = _first_room(project)

    source = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "manual_ksec_override": "0",
            "scanner_source": "JSON worst-case Ksec lookup (GE_REVOLUTION_APEX_FAMILY)",
        },
    )
    source.room_name = room.name
    project.sources = [source]
    room.sources = [source]

    results = compute_room_barrier_table(
        project,
        room.name,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    assert results
    assert len(results) == len(room.barriers)
    for result in results:
        _assert_smoke_result_shape(result)


def test_ct_manual_override_ksec_source_smoke_calculates_barriers():
    project = build_example_project()
    room = _first_room(project)

    source = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "manual_ksec_override": "1",
            "manual_ksec_entered_by": "Test Physicist",
            "manual_ksec_reason": "Vendor manual extract",
            "manual_ksec_source_reference": "Philips document XYZ page 12",
            "manual_ksec_last_updated": "2026-05-21 10:30",
            "scanner_source": "Manual override entered in Sources tab",
        },
    )
    source.room_name = room.name
    project.sources = [source]
    room.sources = [source]

    results = compute_room_barrier_table(
        project,
        room.name,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    assert results
    assert len(results) == len(room.barriers)
    for result in results:
        _assert_smoke_result_shape(result)


def test_ct_null_ksec_source_blocks_barrier_table_with_clear_error():
    """
    NULL ksec is safety-critical. The lower-level physics pathway should raise
    a clear error rather than silently calculating with 0, blank, or default ksec.
    The UI/report preflight handles this before final output generation.
    """
    project = build_example_project()
    room = _first_room(project)

    source = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "NULL ksec — manual override required",
        },
    )
    source.room_name = room.name
    project.sources = [source]
    room.sources = [source]

    with pytest.raises(ValueError, match="CT scanner ksec is NULL/missing"):
        compute_room_barrier_table(
            project,
            room.name,
            "120 kVp",
            solver_mode=SOLVER_MODE_AUTO,
        )


def test_barrier_result_changes_when_ksec_changes():
    """
    This is a sanity smoke test, not a physics benchmark.

    For the same room/barrier/workload, increasing ksec should not reduce the
    unshielded weekly dose.
    """
    project_low = build_example_project()
    project_high = deepcopy(project_low)

    room_low = _first_room(project_low)
    room_high = _first_room(project_high)

    src_low = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.010,
            "manual_ksec_override": "1",
            "manual_ksec_reason": "Test low ksec",
        },
    )
    src_low.room_name = room_low.name

    src_high = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.050,
            "manual_ksec_override": "1",
            "manual_ksec_reason": "Test high ksec",
        },
    )
    src_high.room_name = room_high.name

    project_low.sources = [src_low]
    project_high.sources = [src_high]
    room_low.sources = [src_low]
    room_high.sources = [src_high]

    barrier_low = _first_barrier(room_low)
    barrier_high = _first_barrier(room_high)

    result_low = calc_barrier_result(
        room_low,
        barrier_low,
        project_low,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )
    result_high = calc_barrier_result(
        room_high,
        barrier_high,
        project_high,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    low_dose = float(result_low.get("unshielded_weekly_dose_uSv") or 0)
    high_dose = float(result_high.get("unshielded_weekly_dose_uSv") or 0)

    assert high_dose >= low_dose


def test_barrier_result_has_source_contribution_text_or_graceful_blank():
    project = build_example_project()
    room = _first_room(project)

    results = compute_room_barrier_table(
        project,
        room.name,
        "120 kVp",
        solver_mode=SOLVER_MODE_AUTO,
    )

    assert results
    for result in results:
        assert "source_contributions" in result
        assert isinstance(result.get("source_contributions", ""), str)
