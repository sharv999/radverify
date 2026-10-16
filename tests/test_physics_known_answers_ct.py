from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.shielding_engine import calc_barrier_result
from models.shielding_models import Barrier, Room, Source, Project
from services.source_readiness import validate_project_source_readiness


ROOM_NAME = "CT Room 1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_obj(cls, **kwargs):
    """Instantiate dataclass/model classes defensively across refactors."""
    try:
        return cls(**kwargs)
    except TypeError:
        obj = cls()
        for key, value in kwargs.items():
            setattr(obj, key, value)
        return obj


def _ct_source(
    *,
    ksec: float | str | None,
    scanner_model: str = "Known-answer CT",
    scanner_family: str = "KNOWN_ANSWER_CT",
    manual_override: str = "0",
    scans_per_week: float = 60.0,
    workload_mas_per_scan: float = 630.0,
):
    params = {
        "preset": "ct_low_dose",
        "use_scanner_db": "1",
        "manual_ksec_override": manual_override,
        "scanner_vendor": "Known",
        "scanner_model": scanner_model,
        "scanner_family": scanner_family,
        "scanner_phantom": "body",
        "scanner_kvp": 140,
        "ksec_energy_kvp": 140,
        "ksec_mGy_per_100mAs_at_1m": ksec,
        "scans_per_week": scans_per_week,
        "workload_mAs_per_scan": workload_mas_per_scan,
        "scanner_ksec_status": "manual_override" if manual_override == "1" else "database",
        "scanner_source": "Known-answer test fixture",
        "ksec_definition": "scatter air kerma per 100 mAs at 1 m",
        "ksec_reference_distance_m": 1.0,
    }

    return _make_obj(
        Source,
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_140kvp",
        params=params,
        room_name=ROOM_NAME,
    )


def _barrier(
    *,
    name: str = "N wall",
    distance_m: float = 2.0,
    thickness_mm: float = 0.88,
    occupancy_factor: float = 0.2,
    design_goal_uSv_per_week: float = 10.0,
):
    return _make_obj(
        Barrier,
        name=name,
        material="Pb",
        thickness_mm=thickness_mm,
        barrier_role="secondary_wall",
        distance_m=distance_m,
        occupancy_factor=occupancy_factor,
        design_goal_uSv_per_week=design_goal_uSv_per_week,
        adjacent_area="Known-answer adjacent area",
    )


def _room_with(barrier: Barrier, source: Source):
    return _make_obj(
        Room,
        name=ROOM_NAME,
        modality="CT",
        barriers=[barrier],
        sources=[source],
    )


def _project_with(room: Room, source: Source):
    try:
        return _make_obj(
            Project,
            project_name="Known-answer CT physics test",
            rooms=[room],
            sources=[source],
        )
    except Exception:
        return SimpleNamespace(
            project_name="Known-answer CT physics test",
            rooms=[room],
            sources=[source],
        )


def _result_for(
    *,
    ksec: float | str | None = 0.005,
    distance_m: float = 2.0,
    thickness_mm: float = 0.88,
    occupancy_factor: float = 0.2,
    design_goal_uSv_per_week: float = 10.0,
    manual_override: str = "0",
):
    source = _ct_source(ksec=ksec, manual_override=manual_override)
    barrier = _barrier(
        distance_m=distance_m,
        thickness_mm=thickness_mm,
        occupancy_factor=occupancy_factor,
        design_goal_uSv_per_week=design_goal_uSv_per_week,
    )
    room = _room_with(barrier, source)
    project = _project_with(room, source)

    return calc_barrier_result(room, barrier, project, "140 kVp")


def _float(result: dict, key: str) -> float:
    value = result.get(key)
    assert value not in (None, ""), f"Missing result key/value: {key}"
    return float(value)


# ---------------------------------------------------------------------------
# Known-answer CT scatter tests
# ---------------------------------------------------------------------------

def test_kat_ct_01_database_ksec_inverse_square_at_2m():
    """
    Known answer:

    ksec = 0.005 mGy / 100 mAs @ 1 m
    workload = 630 mAs/scan
    scans = 60/week

    Weekly scatter at 1 m:
        0.005 * (630 / 100) * 60 * 1000 = 1890 uSv/week

    At 2 m:
        1890 / 2^2 = 472.5 uSv/week

    Engine convention:
        reported unshielded_weekly_dose_uSv is the physical unshielded dose
        at the barrier distance and does not include occupancy T.
    """
    result = _result_for(
        ksec=0.005,
        distance_m=2.0,
        thickness_mm=0.88,
        occupancy_factor=0.2,
    )

    assert _float(result, "unshielded_weekly_dose_uSv") == pytest.approx(472.5, rel=1e-6)


def test_kat_ct_02_inverse_square_distance_doubling():
    """
    Same source as KAT-CT-01.

    Engine-reported unshielded dose:
        d = 2 m -> 472.5 uSv/week
        d = 4 m -> 118.125 uSv/week

    Doubling distance should reduce dose by factor 4.
    """
    result_2m = _result_for(ksec=0.005, distance_m=2.0, occupancy_factor=0.2)
    result_4m = _result_for(ksec=0.005, distance_m=4.0, occupancy_factor=0.2)

    d2 = _float(result_2m, "unshielded_weekly_dose_uSv")
    d4 = _float(result_4m, "unshielded_weekly_dose_uSv")

    assert d2 == pytest.approx(472.5, rel=1e-6)
    assert d4 == pytest.approx(118.125, rel=1e-6)
    assert d2 / d4 == pytest.approx(4.0, rel=1e-6)


def test_kat_ct_03_manual_ksec_override_scales_linearly():
    """
    Manual override known answer:

    ksec = 0.015, i.e. 3x the 0.005 database case.

    At d = 2 m:
        0.015 * (630 / 100) * 60 * 1000 / 2^2
        = 1417.5 uSv/week
    """
    database = _result_for(ksec=0.005, distance_m=2.0, occupancy_factor=0.2)
    manual = _result_for(
        ksec=0.015,
        distance_m=2.0,
        occupancy_factor=0.2,
        manual_override="1",
    )

    db_unshielded = _float(database, "unshielded_weekly_dose_uSv")
    manual_unshielded = _float(manual, "unshielded_weekly_dose_uSv")

    assert manual_unshielded == pytest.approx(1417.5, rel=1e-6)
    assert manual_unshielded / db_unshielded == pytest.approx(3.0, rel=1e-6)


def test_kat_ct_04_current_ct_pb_snapshot_borderline_review_case():
    """
    Regression snapshot from the stable MVP baseline.

    Inputs:
        ksec = 0.005
        workload = 630 mAs/scan
        scans = 60/week
        distance = 2 m
        T = 0.2
        P = 10 uSv/week
        Pb = 0.88 mm

    Expected current engine outputs:
        unshielded = 472.5 µSv/week
        transmitted ≈ 2.465 µSv/week
        required Pb ≈ 0.476 mm
        margin ≈ 0.404 mm

    Physics compliance is PASS, but user-facing status should be REVIEW
    because margin < 0.5 mm. The separate report/UI tests protect that
    presentation rule.
    """
    result = _result_for(
        ksec=0.005,
        distance_m=2.0,
        thickness_mm=0.88,
        occupancy_factor=0.2,
        design_goal_uSv_per_week=10.0,
    )

    assert _float(result, "unshielded_weekly_dose_uSv") == pytest.approx(472.5, rel=1e-6)
    assert _float(result, "transmitted_dose_uSv_per_week") == pytest.approx(2.465, rel=5e-3)
    assert _float(result, "required_lead_mm") == pytest.approx(0.476, rel=5e-3)
    assert _float(result, "margin_mm") == pytest.approx(0.404, rel=5e-3)
    assert str(result.get("compliance_status", "")).upper() == "PASS"


def test_kat_ct_05_zero_pb_forces_fail():
    result = _result_for(
        ksec=0.005,
        distance_m=2.0,
        thickness_mm=0.0,
        occupancy_factor=1.0,
        design_goal_uSv_per_week=10.0,
    )

    assert _float(result, "transmitted_dose_uSv_per_week") > 10.0
    assert _float(result, "margin_mm") < 0.0
    assert str(result.get("compliance_status", "")).upper() in {
        "FAIL",
        "ERROR",
        "NON-COMPLIANT",
    }


def test_kat_ct_06_null_ksec_without_manual_override_blocks_source_readiness():
    source = _ct_source(
        ksec="",
        scanner_model="Brilliance 64",
        scanner_family="PHILIPS_BRILLIANCE_64",
        manual_override="0",
    )
    source.params["scanner_ksec_status"] = "manual_override_required"
    source.params["scanner_source"] = "NULL ksec — manual override required"

    barrier = _barrier()
    room = _room_with(barrier, source)
    project = _project_with(room, source)

    readiness = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [source] if room_name == ROOM_NAME else [],
    )

    assert readiness.get("blocking") is True
    assert str(readiness.get("overall_status", "")).upper() in {"FAIL", "BLOCKED", "ERROR"}

    joined = " ".join(
        str(x)
        for x in (
            readiness.get("errors", [])
            + readiness.get("warnings", [])
            + readiness.get("source_results", [])
            + readiness.get("room_results", [])
        )
    ).lower()

    assert "ksec" in joined
    assert "manual" in joined or "override" in joined


def test_kat_ct_07_report_payload_contains_low_margin_review_rule():
    """
    Contract guard for the CT-14G fix.

    Borderline physics PASS rows must be promoted to user-facing REVIEW in the
    report/export payload when margin < 0.5 mm.
    """
    semantics_text = Path("reports/report_semantics.py").read_text(encoding="utf-8")
    builder_text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8")

    assert "margin" in semantics_text
    assert "0.5" in semantics_text
    assert "user_facing_status_from_live as _user_facing_status_from_live" in builder_text
    assert "REVIEW" in semantics_text