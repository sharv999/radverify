from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.spect_kat_helpers import extract_spect_kat_payload


FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_PATH = FIXTURES / "KAT_SPECT_all_green_room_project.json"
EXPECTED_PATH = FIXTURES / "KAT_SPECT_all_green_room_expected.json"


def _load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def _assert_close(actual: float, expected: float) -> None:
    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_spect_kat_001_matches_frozen_source_and_room_contract():
    actual = extract_spect_kat_payload(PROJECT_PATH)
    expected = _load_expected()

    assert actual["kat_id"] == expected["kat_id"] == "SPECT-KAT-001"
    assert actual["room"]["name"] == expected["room"]["name"]
    for field in (
        "length_m",
        "width_m",
        "height_m",
        "source_from_west_m",
        "source_from_south_m",
    ):
        _assert_close(actual["room"][field], expected["room"][field])

    assert actual["source"]["radionuclide"] == expected["source"]["radionuclide"]
    assert actual["source"]["radiation_type"] == expected["source"]["radiation_type"]
    for field in (
        "dose_rate_constant_uSv_h_per_MBq_at_1m",
        "administered_activity_MBq",
        "patients_per_week",
        "imaging_duration_h",
        "decay_integrated_hours",
        "weekly_dose_uSv_at_1m",
    ):
        _assert_close(actual["source"][field], expected["source"][field])


def test_spect_kat_001_matches_frozen_barrier_results():
    actual = extract_spect_kat_payload(PROJECT_PATH)
    expected = _load_expected()

    assert set(actual["barriers"]) == set(expected["barriers"]) == {
        "N wall",
        "E wall",
        "S wall",
        "W wall",
        "Floor",
        "Ceiling",
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
        assert actual_row["status"] == expected_row["status"] == "PASS"
        for field in numeric_fields:
            if expected_row[field] is None:
                assert actual_row[field] is None
            else:
                _assert_close(actual_row[field], expected_row[field])


def test_spect_kat_001_canvas_native_reference_values_remain_frozen():
    actual = extract_spect_kat_payload(PROJECT_PATH)

    # These are the values displayed by the Sources/Geometry/Barriers workflow.
    _assert_close(actual["source"]["weekly_dose_uSv_at_1m"], 296.2512893955822)
    _assert_close(actual["barriers"]["N wall"]["unshielded_uSv_per_week"], 32.91680993284247)
    _assert_close(actual["barriers"]["E wall"]["unshielded_uSv_per_week"], 47.40020630329315)
    _assert_close(actual["barriers"]["N wall"]["required_transmission_B"], 0.6075922922301522)
    _assert_close(actual["barriers"]["E wall"]["required_transmission_B"], 0.42193909182649464)
    _assert_close(actual["barriers"]["W wall"]["occupancy_factor"], 0.05)
    _assert_close(actual["barriers"]["Floor"]["annual_design_dose_uSv_per_year"], 1040.0)
    _assert_close(actual["barriers"]["Ceiling"]["distance_m"], 3.0)
