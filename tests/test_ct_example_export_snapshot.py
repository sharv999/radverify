from __future__ import annotations

"""
Snapshot/known-answer test for Generate Outputs barrier_results.json.

Workflow:
    1. Open tests/fixtures/CT_example.json in the app.
    2. Select Generate Outputs.
    3. Copy the generated *_barrier_results.json to:

           tests/fixtures/CT_example_barrier_results.json

       Or point to it with:

           $env:CT_EXAMPLE_BARRIER_RESULTS_JSON="C:\\path\\to\\Example_Shielding_Assessment_barrier_results.json"

    4. Run:

           python -m pytest tests/test_ct_example_export_snapshot.py

This test compares the generated machine-readable results table against the
known expected results table. It deliberately includes openings/sub-barriers
(D1/D2/D3/VP4-8), because those are part of the app-visible Results table.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest


ACTUAL_FIXTURE = Path("tests/fixtures/CT_example_barrier_results.json")
EXPECTED_FIXTURE = Path("tests/fixtures/CT_example_expected_barrier_results.json")


NUMERIC_FIELDS = {
    "provided_thickness_mm",
    "required_lead_mm",
    "required_concrete_mm",
    "required_thickness_mm",
    "recommended_commercial_lead_mm",
    "margin_mm",
    "unshielded_weekly_dose_uSv",
    "barrier_transmission_factor_B",
    "transmitted_dose_uSv_per_week",
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
}

TEXT_FIELDS = {
    "room_name",
    "room_modality",
    "barrier",
    "barrier_element_type",
    "parent_barrier",
    "barrier_role",
    "material",
    "status",
    "solver_used",
    "ct_solver_used",
}


DEFAULT_TOLERANCE = {
    "provided_thickness_mm": 0.001,
    "required_lead_mm": 0.002,
    "required_concrete_mm": 0.1,
    "required_thickness_mm": 0.002,
    "recommended_commercial_lead_mm": 0.002,
    "margin_mm": 0.002,
    "unshielded_weekly_dose_uSv": 0.01,
    "barrier_transmission_factor_B": 0.000001,
    "transmitted_dose_uSv_per_week": 0.01,
    "distance_m": 0.001,
    "occupancy_factor": 0.000001,
    "design_goal_uSv_per_week": 0.001,
}


def _actual_path() -> Path:
    env = os.environ.get("CT_EXAMPLE_BARRIER_RESULTS_JSON", "").strip()
    if env:
        return Path(env)
    return ACTUAL_FIXTURE


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"Required results fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_by_barrier(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = data.get("rows", []) or []
    return {str(row.get("barrier", "") or ""): row for row in rows}


def _assert_numeric_or_null(actual_value: Any, expected_value: Any, field: str) -> None:
    if expected_value is None:
        assert actual_value in (None, "", "-"), field
        return

    assert actual_value not in (None, "", "-"), field
    tol = DEFAULT_TOLERANCE.get(field, 1e-6)
    assert float(actual_value) == pytest.approx(float(expected_value), abs=tol), field


def test_ct_example_generated_barrier_results_match_known_expected_snapshot():
    actual = _load_json(_actual_path())
    expected = _load_json(EXPECTED_FIXTURE)

    assert actual.get("project_name") == expected.get("project_name")
    assert actual.get("global_energy") == expected.get("global_energy")
    assert actual.get("solver_mode") == expected.get("solver_mode")

    expected_summary = expected.get("summary", {}) or {}
    actual_summary = actual.get("summary", {}) or {}

    for key in ("room_count", "barrier_count", "pass_count", "review_count", "fail_count"):
        assert actual_summary.get(key) == expected_summary.get(key), key

    actual_rows = _rows_by_barrier(actual)
    expected_rows = _rows_by_barrier(expected)

    assert set(actual_rows) == set(expected_rows)

    # Explicit guard that opening/sub-barrier rows are present.
    for opening_name in ("D1", "D2", "D3", "VP4", "VP5", "VP6", "VP7", "VP8"):
        assert opening_name in actual_rows

    for barrier_name, expected_row in expected_rows.items():
        actual_row = actual_rows[barrier_name]

        for field in TEXT_FIELDS:
            if field in expected_row:
                assert str(actual_row.get(field, "") or "") == str(expected_row.get(field, "") or ""), (
                    barrier_name,
                    field,
                )

        for field in NUMERIC_FIELDS:
            if field in expected_row:
                _assert_numeric_or_null(actual_row.get(field), expected_row.get(field), field)


def test_ct_example_generated_results_have_no_duplicate_barrier_names():
    actual = _load_json(_actual_path())
    names = [str(row.get("barrier", "") or "") for row in actual.get("rows", []) or []]

    assert len(names) == len(set(names))
    assert all(names)


def test_ct_example_opening_rows_have_expected_element_types():
    actual = _load_json(_actual_path())
    rows = _rows_by_barrier(actual)

    for name in ("D1", "D2", "D3"):
        assert rows[name]["barrier_element_type"] == "door"

    for name in ("VP4", "VP5", "VP6", "VP7", "VP8"):
        assert rows[name]["barrier_element_type"] == "viewing_panel"
