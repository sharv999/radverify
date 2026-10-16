from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.spect_kat_helpers import extract_spect_kat_payload


FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_PATH = FIXTURES / "KAT_SPECT_red_room_project.json"
EXPECTED_PATH = FIXTURES / "KAT_SPECT_red_room_expected.json"


def _load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def _actual() -> dict[str, Any]:
    return extract_spect_kat_payload(PROJECT_PATH, kat_id="SPECT-KAT-002")


def _assert_close(actual: float, expected: float) -> None:
    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_spect_kat_002_matches_frozen_source_and_room_contract():
    actual = _actual()
    expected = _load_expected()

    assert actual["kat_id"] == expected["kat_id"] == "SPECT-KAT-002"
    assert actual["room"]["name"] == expected["room"]["name"] == "SPECT Room 1"
    for field in (
        "length_m",
        "width_m",
        "height_m",
        "source_from_west_m",
        "source_from_south_m",
    ):
        _assert_close(actual["room"][field], expected["room"][field])

    assert actual["source"]["radionuclide"] == expected["source"]["radionuclide"] == "Tc99m"
    assert actual["source"]["radiation_type"] == expected["source"]["radiation_type"] == "tc99m_140kev"
    for field in (
        "dose_rate_constant_uSv_h_per_MBq_at_1m",
        "administered_activity_MBq",
        "patients_per_week",
        "imaging_duration_h",
        "decay_integrated_hours",
        "weekly_dose_uSv_at_1m",
    ):
        _assert_close(actual["source"][field], expected["source"][field])


def test_spect_kat_002_matches_frozen_barrier_results_and_fail_pattern():
    actual = _actual()
    expected = _load_expected()

    assert set(actual["barriers"]) == set(expected["barriers"]) == {
        "N wall", "E wall", "S wall", "W wall", "Floor", "Ceiling"
    }

    numeric_fields = (
        "distance_m",
        "occupancy_factor",
        "design_goal_uSv_per_week",
        "annual_design_dose_uSv_per_year",
        "unshielded_uSv_per_week",
        "occupied_unshielded_uSv_per_week",
        "required_transmission_B",
        "required_thickness_mm",
        "provided_thickness_mm",
        "provided_transmission",
        "transmitted_uSv_per_week",
    )

    for barrier_name, expected_row in expected["barriers"].items():
        actual_row = actual["barriers"][barrier_name]
        assert actual_row["status"] == expected_row["status"]
        for field in numeric_fields:
            if expected_row[field] is None:
                assert actual_row[field] is None
            else:
                _assert_close(actual_row[field], expected_row[field])

    assert {name for name, row in actual["barriers"].items() if row["status"] == "FAIL"} == {"E wall"}
    assert {name for name, row in actual["barriers"].items() if row["status"] == "PASS"} == {
        "N wall", "S wall", "W wall", "Floor", "Ceiling"
    }


def test_spect_kat_002_east_wall_failure_reference_values_remain_frozen():
    actual = _actual()
    e_wall = actual["barriers"]["E wall"]

    _assert_close(actual["source"]["weekly_dose_uSv_at_1m"], 2089.7726089796474)
    _assert_close(e_wall["distance_m"], 2.5)
    _assert_close(e_wall["unshielded_uSv_per_week"], 334.3636174367436)
    _assert_close(e_wall["required_transmission_B"], 0.059815120297242536)
    _assert_close(e_wall["required_thickness_mm"], 1.0711065450420907)
    _assert_close(e_wall["provided_thickness_mm"], 0.88)
    _assert_close(e_wall["provided_transmission"], 0.09752534270020069)
    _assert_close(e_wall["transmitted_uSv_per_week"], 32.60892637699722)
    assert e_wall["status"] == "FAIL"
