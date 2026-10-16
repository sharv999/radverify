from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures"

BASE_PROJECT_PATH = FIXTURES_DIR / "KAT_ct_all_green_room_project.json"


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


def _force_ct_scatter_ksec_missing(project_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Convert the standard CT project into a missing-ksec CT case.

    This deliberately avoids Tkinter/UI state. It modifies source params only.
    """
    payload = copy.deepcopy(project_payload)

    for item in _walk_dicts(payload):
        source_type = str(item.get("source_type", "") or "").lower()
        params = item.get("params")

        if "ct" in source_type and "scatter" in source_type and isinstance(params, dict):
            params["scanner_vendor"] = "Philips"
            params["scanner_model"] = "Brilliance 64"
            params["scanner_name"] = "Philips Brilliance 64"
            params["ksec_mGy_per_100mAs_at_1m"] = None
            params["manual_ksec_mGy_per_100mAs_at_1m"] = None
            params["manual_ksec_override"] = False
            params["ksec_basis"] = "manual_override_required"
            params["ksec_status"] = "missing"
            params["ksec_override_reason"] = ""

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


def test_headless_missing_ct_ksec_blocks_certification_and_machine_exports():
    """
    A CT project with missing/null scanner ksec must be blocked in the
    headless report/output path.

    This protects the legal/compliance gating pathway without relying on
    warning dialogs, Results tab state, or Tkinter.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    base_project = _load_json(BASE_PROJECT_PATH)
    missing_ksec_project = _force_ct_scatter_ksec_missing(base_project)

    payload = build_results_payload_from_project_dict(missing_ksec_project)

    certification = payload.get("certification", {})
    export_eligibility = payload.get("export_eligibility", {})
    source_readiness = payload.get("source_readiness", {})

    assert certification.get("certification_allowed") is False
    assert certification.get("signature_allowed") is False

    assert export_eligibility.get("allowed") is False
    assert export_eligibility.get("blocking") is True
    assert export_eligibility.get("can_certify") is False

    assert source_readiness.get("blocking") is True
    assert str(source_readiness.get("overall_status", "")).upper() in {
        "FAIL",
        "BLOCKED",
        "INCOMPLETE",
        "UNKNOWN",
    }

    all_text = "\n".join(_flatten_strings(payload)).lower()

    assert "ksec" in all_text
    assert (
        "manual" in all_text
        or "override" in all_text
        or "missing" in all_text
        or "null" in all_text
    )

    # Draft PDF may still be allowed depending on current MVP rules, but
    # certification and machine-readable final export must not be allowed.
    assert payload.get("meta", {}).get("report_status_effective") != "Final"