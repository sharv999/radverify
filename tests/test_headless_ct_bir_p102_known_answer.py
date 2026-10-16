from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "fixtures"

PROJECT_PATH = FIXTURES_DIR / "KAT_ct_BIR_p102_project.json"
EXPECTED_PATH = FIXTURES_DIR / "KAT_ct_BIR_p102_expected_output.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_payload_rows(report_payload: dict) -> list[dict]:
    rows: list[dict] = []

    for room in report_payload.get("rooms", []) or []:
        room_name = room.get("name", "")
        room_modality = room.get("modality", "")
        room_classification = room.get("classification", "")

        for barrier in room.get("barriers", []) or []:
            row = dict(barrier)
            row["room_name"] = room_name
            row["room_modality"] = room_modality
            row["room_classification"] = room_classification
            row["barrier"] = row.pop("name", "")
            rows.append(row)

    return rows


def _normalised_output(report_payload: dict) -> dict:
    project = report_payload.get("project", {})
    summary = report_payload.get("summary", {})

    return {
        "export_version": 1,
        "project_name": project.get("project_name", ""),
        "global_energy": project.get("global_energy", ""),
        "solver_mode": project.get("solver_mode", ""),
        "summary": {
            "room_count": summary.get("room_count"),
            "barrier_count": summary.get("barrier_count"),
            "pass_count": summary.get("pass_count"),
            "review_count": summary.get("review_count"),
            "fail_count": summary.get("fail_count"),
            "source_ksec_database_count": summary.get("source_ksec_database_count"),
            "source_ksec_manual_override_count": summary.get("source_ksec_manual_override_count"),
            "source_ksec_incomplete_count": summary.get("source_ksec_incomplete_count"),
        },
        "rows": _flatten_payload_rows(report_payload),
    }


def _round_floats(value):
    if isinstance(value, float):
        return round(value, 3)

    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_round_floats(item) for item in value]

    return value


def test_headless_ct_bir_p102_matches_expected_output():
    """
    Known-answer BIR p102 CT secondary scatter fixture.

    This fixture protects a manual-ksec CT scatter case based on the BIR p102
    reference configuration. Expected result: 4 REVIEW barriers and 2 FAIL
    barriers, with no openings.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)
    expected = _load_json(EXPECTED_PATH)

    actual_payload = build_results_payload_from_project_dict(project_payload)
    actual = _normalised_output(actual_payload)

    expected = dict(expected)
    expected.pop("generated_on", None)

    assert _round_floats(actual["summary"]) == _round_floats(expected["summary"])

    actual_rows = sorted(actual["rows"], key=lambda r: r["barrier"])
    expected_rows = sorted(expected["rows"], key=lambda r: r["barrier"])

    stable_keys = [
        "room_name",
        "room_modality",
        "room_classification",
        "barrier",
        "barrier_element_type",
        "parent_barrier",
        "adjacent_area",
        "barrier_role",
        "material",
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
        "status",
        "status_text",
        "risk_visual_state",
        "dominant_source",
        "solver_used",
        "source_contributions",
        "compliance_statement",
        "governing_requirement_text",
    ]

    actual_compact = [
        {key: row.get(key) for key in stable_keys}
        for row in actual_rows
    ]
    expected_compact = [
        {key: row.get(key) for key in stable_keys}
        for row in expected_rows
    ]

    assert _round_floats(actual_compact) == _round_floats(expected_compact)


def test_headless_ct_bir_p102_contract_summary():
    """
    Explicit contract check for the BIR p102 known-answer case.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)
    payload = build_results_payload_from_project_dict(project_payload)

    summary = payload.get("summary", {})
    rows = _flatten_payload_rows(payload)

    assert summary["room_count"] == 1
    assert summary["barrier_count"] == 6
    assert summary["pass_count"] == 0
    assert summary["review_count"] == 4
    assert summary["fail_count"] == 2

    assert summary["source_ksec_database_count"] == 0
    assert summary["source_ksec_manual_override_count"] == 1
    assert summary["source_ksec_incomplete_count"] == 0

    assert {row["barrier"] for row in rows} == {
        "N wall",
        "E wall",
        "S wall",
        "W wall",
        "Floor",
        "Ceiling",
    }

    by_barrier = {row["barrier"]: row for row in rows}

    assert by_barrier["N wall"]["status"] == "REVIEW"
    assert by_barrier["E wall"]["status"] == "REVIEW"
    assert by_barrier["S wall"]["status"] == "REVIEW"
    assert by_barrier["W wall"]["status"] == "REVIEW"
    assert by_barrier["Floor"]["status"] == "FAIL"
    assert by_barrier["Ceiling"]["status"] == "FAIL"

    for name in ("N wall", "E wall", "S wall", "W wall"):
        assert float(by_barrier[name]["margin_mm"]) > 0
        assert float(by_barrier[name]["margin_mm"]) < 0.5
        assert by_barrier[name]["risk_visual_state"] == "REVIEW"

    for name in ("Floor", "Ceiling"):
        assert float(by_barrier[name]["margin_mm"]) < 0
        assert by_barrier[name]["risk_visual_state"] == "FAIL"