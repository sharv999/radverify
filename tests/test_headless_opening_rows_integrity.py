from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures"

BASE_PROJECT_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_project.json"


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Missing JSON fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _first_room(payload: dict[str, Any]) -> dict[str, Any]:
    rooms = payload.get("rooms") or []
    assert rooms, "Payload contains no rooms"
    assert isinstance(rooms[0], dict), "First room is not a dictionary"
    return rooms[0]


def _barriers_for_first_room(payload: dict[str, Any]) -> list[dict[str, Any]]:
    room = _first_room(payload)
    barriers = room.get("barriers") or []
    assert isinstance(barriers, list), "Room barriers is not a list"
    return barriers


def _opening_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    barriers = _barriers_for_first_room(payload)

    rows = []
    for row in barriers:
        element_type = str(row.get("barrier_element_type", "") or "").strip().lower()
        element_type = element_type.replace(" ", "_")

        if element_type in {"door", "viewing_panel"}:
            rows.append(row)

    return rows


def test_headless_report_payload_includes_all_geometry_openings():
    """
    Geometry openings must appear in the canonical report payload.

    This protects against the regression where the headless path exported only
    the six main barriers and silently omitted doors/viewing panels.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(BASE_PROJECT_PATH)
    report_payload = build_results_payload_from_project_dict(project_payload)

    project_room = _first_room(project_payload)
    report_room = _first_room(report_payload)

    geometry = project_room.get("geometry") or {}
    expected_openings = geometry.get("openings") or []

    assert len(expected_openings) == 3

    opening_rows = _opening_rows(report_payload)

    assert len(opening_rows) == len(expected_openings)
    assert report_room.get("opening_count_expected") == len(expected_openings)
    assert report_room.get("opening_count_exported") == len(expected_openings)

    assert report_payload.get("calculation_integrity", {}).get("opening_count_expected") == len(expected_openings)
    assert report_payload.get("calculation_integrity", {}).get("opening_count_exported") == len(expected_openings)


def test_headless_opening_rows_have_expected_names_types_and_parents():
    """
    Opening/sub-barrier rows should be named, typed, and linked to string parent
    barriers in the report payload.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(BASE_PROJECT_PATH)
    report_payload = build_results_payload_from_project_dict(project_payload)

    opening_rows = _opening_rows(report_payload)

    by_name = {str(row.get("name", "") or ""): row for row in opening_rows}

    assert set(by_name) == {"D1", "VP2", "VP3"}

    def _element_type(row: dict) -> str:
        return (
            str(row.get("barrier_element_type", "") or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )

    assert _element_type(by_name["D1"]) == "door"
    assert _element_type(by_name["VP2"]) == "viewing_panel"
    assert _element_type(by_name["VP3"]) == "viewing_panel"

    assert by_name["D1"]["parent_barrier"] == "S wall"
    assert by_name["VP2"]["parent_barrier"] == "E wall"
    assert by_name["VP3"]["parent_barrier"] == "W wall"

    for row in opening_rows:
        assert isinstance(row.get("parent_barrier"), str)
        assert row.get("status") in {"PASS", "REVIEW", "FAIL"}
        role = (
            str(row.get("barrier_role", "") or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        assert role in {"door", "viewing_panel"}
        assert by_name["D1"]["provided_thickness_mm"] == 0.88
        assert by_name["VP2"]["provided_thickness_mm"] == 0.88
        assert by_name["VP3"]["provided_thickness_mm"] == 1.76


def test_headless_opening_rows_do_not_block_payload_integrity():
    """
    The standard CT fixture should not be blocked by missing opening rows.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(BASE_PROJECT_PATH)
    report_payload = build_results_payload_from_project_dict(project_payload)

    integrity = report_payload.get("calculation_integrity", {})
    room_issues = integrity.get("room_issues") or []
    blocking_reasons = integrity.get("blocking_reasons") or []

    assert not any(
        str(issue.get("issue", "")) == "opening_export_omission"
        for issue in room_issues
        if isinstance(issue, dict)
    )

    assert not any(
        "opening" in str(reason).lower() and "missing" in str(reason).lower()
        for reason in blocking_reasons
    )