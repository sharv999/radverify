from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "fixtures"

PROJECT_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_project.json"
EXPECTED_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_expected_output.json"


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
        return {k: _round_floats(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_round_floats(v) for v in value]

    return value


def test_headless_ct_amber_red_room_matches_expected_status_contract():
    """
    Known mixed-status CT fixture.

    Expected:
      PASS   = N wall, E wall, Floor, Ceiling
      REVIEW = S wall, W wall, D1, VP3
      FAIL   = VP2

    This protects the opening display/status rule:
      positive margin < 0.5 mm -> REVIEW
      negative margin -> FAIL
      adequate margin -> PASS
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)
    expected = _load_json(EXPECTED_PATH)

    actual_payload = build_results_payload_from_project_dict(project_payload)
    actual = _normalised_output(actual_payload)

    expected_summary = expected["summary"]

    assert actual["summary"]["room_count"] == expected_summary["room_count"]
    assert actual["summary"]["barrier_count"] == expected_summary["barrier_count"]
    assert actual["summary"]["pass_count"] == expected_summary["pass_count"]
    assert actual["summary"]["review_count"] == expected_summary["review_count"]
    assert actual["summary"]["fail_count"] == expected_summary["fail_count"]
    assert actual["summary"]["source_ksec_database_count"] == expected_summary["source_ksec_database_count"]
    assert actual["summary"]["source_ksec_manual_override_count"] == expected_summary["source_ksec_manual_override_count"]
    assert actual["summary"]["source_ksec_incomplete_count"] == expected_summary["source_ksec_incomplete_count"]

    actual_rows = {
        row["barrier"]: row
        for row in actual["rows"]
    }
    expected_rows = {
        row["barrier"]: row
        for row in expected["rows"]
    }

    assert set(actual_rows) == set(expected_rows) == {
        "N wall",
        "E wall",
        "S wall",
        "W wall",
        "Floor",
        "Ceiling",
        "D1",
        "VP2",
        "VP3",
    }

    expected_status = {
        "N wall": "PASS",
        "E wall": "PASS",
        "Floor": "PASS",
        "Ceiling": "PASS",
        "S wall": "REVIEW",
        "W wall": "REVIEW",
        "D1": "REVIEW",
        "VP3": "REVIEW",
        "VP2": "FAIL",
    }

    for barrier_name, status in expected_status.items():
        row = actual_rows[barrier_name]
        assert row["status"] == status
        assert row["risk_visual_state"] == status

    # Specific opening checks that caused the UI mismatch.
    d1 = actual_rows["D1"]
    vp2 = actual_rows["VP2"]
    vp3 = actual_rows["VP3"]

    assert d1["barrier_element_type"].lower() == "door"
    assert d1["status"] == "REVIEW"
    assert round(float(d1["margin_mm"]), 3) == 0.345

    assert vp2["barrier_element_type"].lower().replace(" ", "_") == "viewing_panel"
    assert vp2["status"] == "FAIL"
    assert round(float(vp2["margin_mm"]), 3) == -0.620

    assert vp3["barrier_element_type"].lower().replace(" ", "_") == "viewing_panel"
    assert vp3["status"] == "REVIEW"
    assert round(float(vp3["margin_mm"]), 3) == 0.260


def test_headless_ct_amber_red_room_core_rows_match_expected_values():
    """
    Compare the main stable row fields against the known expected output.
    This is intentionally narrower than a full JSON snapshot.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)
    expected = _load_json(EXPECTED_PATH)

    actual_payload = build_results_payload_from_project_dict(project_payload)
    actual = _normalised_output(actual_payload)

    actual_rows = sorted(actual["rows"], key=lambda r: r["barrier"])
    expected_rows = sorted(expected["rows"], key=lambda r: r["barrier"])

    stable_keys = [
        "barrier",
        "barrier_element_type",
        "parent_barrier",
        "barrier_role",
        "material",
        "provided_thickness_mm",
        "required_thickness_mm",
        "margin_mm",
        "transmitted_dose_uSv_per_week",
        "distance_m",
        "occupancy_factor",
        "design_goal_uSv_per_week",
        "status",
        "status_text",
        "risk_visual_state",
        "solver_used",
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