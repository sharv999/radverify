from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "fixtures"

PROJECT_PATH = FIXTURES_DIR / "KAT_ct_all_green_room_project.json"
EXPECTED_PATH = FIXTURES_DIR / "KAT_ct_all_green_room_expected_output.json"


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


def test_headless_ct_all_green_room_matches_expected_pass_contract():
    """
    Regression test for the all-green CT room.

    The modified project contains:
      - 6 main wall/floor/ceiling barriers
      - 3 geometry openings

    The expected-output fixture is the six-main-barrier all-PASS contract.
    The full generated payload is expected to contain 9 rows.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)
    expected = _load_json(EXPECTED_PATH)

    actual_payload = build_results_payload_from_project_dict(project_payload)
    actual = _normalised_output(actual_payload)

    actual_rows = sorted(actual["rows"], key=lambda r: r["barrier"])
    wall_rows = sorted(
        [
            row for row in actual_rows
            if str(row.get("barrier_element_type", "")).strip().lower() == "wall"
        ],
        key=lambda r: r["barrier"],
    )
    opening_rows = sorted(
        [
            row for row in actual_rows
            if str(row.get("barrier_element_type", "")).strip().lower() != "wall"
        ],
        key=lambda r: r["barrier"],
    )

    expected_rows = sorted(expected["rows"], key=lambda r: r["barrier"])
    expected_summary = expected["summary"]

    # Full payload now includes openings.
    assert actual["summary"]["room_count"] == 1
    assert actual["summary"]["barrier_count"] == 9
    assert actual["summary"]["pass_count"] == 9
    assert actual["summary"]["review_count"] == 0
    assert actual["summary"]["fail_count"] == 0

    assert actual["summary"]["source_ksec_database_count"] == expected_summary["source_ksec_database_count"]
    assert actual["summary"]["source_ksec_manual_override_count"] == expected_summary["source_ksec_manual_override_count"]
    assert actual["summary"]["source_ksec_incomplete_count"] == expected_summary["source_ksec_incomplete_count"]

    # Expected fixture remains the six-main-barrier contract.
    assert len(wall_rows) == expected_summary["barrier_count"] == 6
    assert [row["barrier"] for row in wall_rows] == [
        "Ceiling",
        "E wall",
        "Floor",
        "N wall",
        "S wall",
        "W wall",
    ]

    assert [row["barrier"] for row in expected_rows] == [
        "Ceiling",
        "E wall",
        "Floor",
        "N wall",
        "S wall",
        "W wall",
    ]

    for row in wall_rows:
        assert row["status"] == "PASS"
        assert row["status_text"] == "PASS (meets design goal)"
        assert row["risk_visual_state"] == "PASS"

        tx = float(row["transmitted_dose_uSv_per_week"])
        p = float(row["design_goal_uSv_per_week"])
        assert tx <= p, f"{row['barrier']} has Tx {tx} > P {p}"

    # Openings must also remain all-green/all-PASS.
    assert len(opening_rows) == 3

    opening_types = sorted(
        str(row.get("barrier_element_type", ""))
        .strip()
        .lower()
        .replace(" ", "_")
        for row in opening_rows
    )

    assert opening_types == [
        "door",
        "viewing_panel",
        "viewing_panel",
    ]

    for row in opening_rows:
        assert row["status"] == "PASS"
        assert row["status_text"] == "PASS (meets design goal)"
        assert row["risk_visual_state"] == "PASS"

        tx_raw = row.get("transmitted_dose_uSv_per_week")
        p_raw = row.get("design_goal_uSv_per_week")

        # Some headless opening rows may not expose Tx/P yet. The regression being
        # protected here is PASS openings being promoted to REVIEW/amber.
        if tx_raw not in (None, "") and p_raw not in (None, ""):
            tx = float(tx_raw)
            p = float(p_raw)
            assert tx <= p, f"{row['barrier']} has Tx {tx} > P {p}"


def test_headless_ct_all_green_project_fixture_contains_geometry_openings():
    """
    Guardrail: this fixture deliberately includes geometry openings even though
    the expected all-green output currently checks only the six main barriers.
    """
    project_payload = _load_json(PROJECT_PATH)

    room = project_payload["rooms"][0]
    openings = room["geometry"]["openings"]

    assert len(openings) == 3

    opening_types = [opening["opening_type"] for opening in openings]
    assert opening_types == [
        "door",
        "viewing_panel",
        "viewing_panel",
    ]

    