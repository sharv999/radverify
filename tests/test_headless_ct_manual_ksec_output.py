from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures"

BASE_PROJECT_PATH = FIXTURES_DIR / "KAT_ct_NCRP_147_p96_project.json"

MANUAL_KSEC_VALUE = 0.015


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Missing JSON fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _make_manual_ksec_project(project_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Convert the standard CT fixture into a manual-ksec override case.

    The standard fixture may not contain explicit sources, so this test
    deliberately injects one CT Secondary Scatter source into the first room.
    """
    payload = copy.deepcopy(project_payload)

    rooms = payload.get("rooms") or []
    assert rooms, "No rooms found in fixture"

    room = rooms[0]
    sources = room.setdefault("sources", [])

    sources.clear()
    sources.append(
        {
            "name": "CT Secondary Scatter",
            "label": "CT Secondary Scatter",
            "source_type": "ct_scatter",
            "type": "ct_scatter",
            "radiation_type": "secondary",
            "params": {
                "source_type": "ct_scatter",
                "type": "ct_scatter",
                "scanner_vendor": "Philips",
                "scanner_model": "Brilliance 64",
                "scanner_name": "Philips Brilliance 64",
                "database_ksec_mGy_per_100mAs_at_1m": None,
                "scanner_database_ksec_mGy_per_100mAs_at_1m": None,
                "ksec": MANUAL_KSEC_VALUE,
                "ksec_mgy_per_100mas_at_1m": MANUAL_KSEC_VALUE,
                "ksec_mGy_per_100mAs_at_1m": MANUAL_KSEC_VALUE,
                "manual_ksec": MANUAL_KSEC_VALUE,
                "manual_ksec_mGy_per_100mAs_at_1m": MANUAL_KSEC_VALUE,
                "manual_ksec_override": True,
                "manual_override": True,
                "manual_ksec_override_enabled": True,
                "basis": "manual_override",
                "ksec_basis": "manual_override",
                "ksec_status": "manual_override",
                "ksec_override_reason": "Headless regression test manual ksec.",
            },
        }
    )

    return payload


def _flatten_strings(value: Any) -> list[str]:
    strings: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_flatten_strings(child))
    elif isinstance(value, list):
        for item in value:
            strings.extend(_flatten_strings(item))
    elif isinstance(value, str):
        strings.append(value)

    return strings


def _source_ksec_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("source_ksec_rows") or []
    assert isinstance(rows, list)
    return [row for row in rows if isinstance(row, dict)]


def test_headless_manual_ksec_is_reported_as_manual_override_not_database():
    """
    Manual ksec must remain visibly manual/review-basis in the headless
    report/export payload.

    It must not be silently converted into a database ksec.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    base_project = _load_json(BASE_PROJECT_PATH)
    manual_project = _make_manual_ksec_project(base_project)

    payload = build_results_payload_from_project_dict(manual_project)

    rows = _source_ksec_rows(payload)
    assert rows, "Expected at least one CT ksec row in report payload"

    all_text = "\n".join(_flatten_strings(payload)).lower()

    assert "manual" in all_text
    assert "database" not in {
        str(row.get("basis", "") or "").lower()
        for row in rows
        if row.get("basis")
    }

    assert any(
        str(row.get("basis", "") or "").lower() == "manual_override"
        for row in rows
    )

    assert any(
        abs(float(row.get("value") or row.get("ksec") or row.get("ksec_mGy_per_100mAs_at_1m") or 0.0) - MANUAL_KSEC_VALUE) < 1e-9
        for row in rows
    )


def test_headless_manual_ksec_allows_calculation_but_not_silent_final_certification():
    """
    Manual override should allow the calculation pathway to proceed, while
    preserving review/audit wording in certification/export state.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    base_project = _load_json(BASE_PROJECT_PATH)
    manual_project = _make_manual_ksec_project(base_project)

    payload = build_results_payload_from_project_dict(manual_project)

    summary = payload.get("summary", {})
    certification = payload.get("certification", {})
    export_eligibility = payload.get("export_eligibility", {})

    assert summary.get("barrier_count", 0) >= 6
    assert summary.get("source_ksec_manual_override_count", 0) >= 1
    assert summary.get("source_ksec_database_count", 0) == 0

    all_text = "\n".join(_flatten_strings(payload)).lower()

    assert "manual" in all_text
    assert "override" in all_text or "review" in all_text

    # Manual override should not be treated as clean database-certified data.
    assert certification.get("certification_allowed") is not True
    assert export_eligibility.get("can_certify") is not True