from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "fixtures"

PROJECT_PATH = FIXTURES_DIR / "KAT_ct_all_green_room_project.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _round_floats(value):
    if isinstance(value, float):
        return round(value, 3)

    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_round_floats(item) for item in value]

    return value


def _normalise_payload(payload: dict) -> dict:
    """
    Keep only stable calculation/output fields.

    This deliberately ignores generated timestamps, report metadata, logos,
    and other presentation fields. The purpose is to prove that app-loaded
    output and headless output use the same calculation/result contract.
    """
    summary = payload.get("summary", {}) or {}

    rows = []
    for room in payload.get("rooms", []) or []:
        room_name = room.get("name", "")
        room_modality = room.get("modality", "")
        room_classification = room.get("classification", "")

        for row in room.get("barriers", []) or []:
            rows.append(
                {
                    "room_name": room_name,
                    "room_modality": room_modality,
                    "room_classification": room_classification,
                    "name": row.get("name"),
                    "barrier_element_type": row.get("barrier_element_type"),
                    "parent_barrier": row.get("parent_barrier"),
                    "barrier_role": row.get("barrier_role"),
                    "material": row.get("material"),
                    "provided_thickness_mm": row.get("provided_thickness_mm"),
                    "required_lead_mm": row.get("required_lead_mm"),
                    "required_concrete_mm": row.get("required_concrete_mm"),
                    "required_thickness_mm": row.get("required_thickness_mm"),
                    "recommended_commercial_lead_mm": row.get("recommended_commercial_lead_mm"),
                    "margin_mm": row.get("margin_mm"),
                    "unshielded_weekly_dose_uSv": row.get("unshielded_weekly_dose_uSv"),
                    "barrier_transmission_factor_B": row.get("barrier_transmission_factor_B"),
                    "transmitted_dose_uSv_per_week": row.get("transmitted_dose_uSv_per_week"),
                    "distance_m": row.get("distance_m"),
                    "occupancy_factor": row.get("occupancy_factor"),
                    "design_goal_uSv_per_week": row.get("design_goal_uSv_per_week"),
                    "status": row.get("status"),
                    "status_text": row.get("status_text"),
                    "risk_visual_state": row.get("risk_visual_state"),
                    "dominant_source": row.get("dominant_source"),
                    "solver_used": row.get("solver_used"),
                    "ct_solver_used": row.get("ct_solver_used"),
                    "source_contributions": row.get("source_contributions"),
                    "compliance_statement": row.get("compliance_statement"),
                    "governing_requirement_text": row.get("governing_requirement_text"),
                }
            )

    rows.sort(key=lambda r: (str(r.get("room_name", "")), str(r.get("name", ""))))

    return {
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
        "rows": rows,
    }


def _load_project_into_app(app, project_payload: dict, tmp_path: Path):
    """
    Load project JSON into the real app object.

    Uses services.project_io.load_project_from_file because this is the actual
    project loader currently exposed by the app/service layer.
    """
    from services.project_io import load_project_from_file

    project_path = tmp_path / "app_headless_all_green_project.json"
    project_path.write_text(json.dumps(project_payload, indent=2), encoding="utf-8")

    app.project = load_project_from_file(project_path)

    if hasattr(app, "refresh_all"):
        app.refresh_all()
    elif hasattr(app, "_refresh_all"):
        app._refresh_all()
    elif hasattr(app, "_refresh_from_project"):
        app._refresh_from_project()

def _build_app_payload_in_subprocess(project_payload: dict, tmp_path: Path) -> dict:
    """
    Build the app-loaded payload in a fresh Python process.

    Tk can be order-dependent in a long pytest run on Windows/Python 3.14.
    This still tests the real app-loaded pathway, but isolates Tk startup from
    other integration tests.
    """
    project_path = tmp_path / "app_headless_all_green_project.json"
    output_path = tmp_path / "app_headless_all_green_payload.json"

    project_path.write_text(json.dumps(project_payload, indent=2), encoding="utf-8")

    code = rf'''
import json
from pathlib import Path

from app import ShieldingDesktopApp
from reports.results_payload_builder import build_results_payload
from services.project_io import load_project_from_file

project_path = Path(r"{project_path}")
output_path = Path(r"{output_path}")

app = None
try:
    app = ShieldingDesktopApp()
    app.withdraw()

    app.project = load_project_from_file(project_path)

    if hasattr(app, "refresh_all"):
        app.refresh_all()
    elif hasattr(app, "_refresh_all"):
        app._refresh_all()
    elif hasattr(app, "_refresh_from_project"):
        app._refresh_from_project()

    app.update_idletasks()

    payload = build_results_payload(app)
    output_path.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
finally:
    if app is not None:
        app.destroy()
'''

    stdout_path = tmp_path / "app_headless_all_green_stdout.txt"
    stderr_path = tmp_path / "app_headless_all_green_stderr.txt"

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path.cwd(),
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            timeout=30,
        )

    stdout_text = stdout_path.read_text(encoding="utf-8")
    stderr_text = stderr_path.read_text(encoding="utf-8")

    assert result.returncode == 0, (
        "App-loaded payload subprocess failed"
        f"\nSTDOUT:\n{stdout_text}"
        f"\nSTDERR:\n{stderr_text}"
)

    return _load_json(output_path)


@pytest.mark.integration
def test_app_loaded_all_green_project_and_headless_project_build_same_payload(tmp_path):
    """
    Given the same all-green CT project JSON, the app-loaded path and the
    headless project-dict path must produce the same calculation/output payload.

    This protects the clean PASS pathway and ensures all-green opening rows do
    not drift between UI/export and headless output.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(PROJECT_PATH)

    app_payload = _build_app_payload_in_subprocess(project_payload, tmp_path)

    headless_payload = build_results_payload_from_project_dict(project_payload)

    app_norm = _round_floats(_normalise_payload(app_payload))
    headless_norm = _round_floats(_normalise_payload(headless_payload))

    assert app_norm["summary"] == headless_norm["summary"]

    app_rows = app_norm["rows"]
    headless_rows = headless_norm["rows"]

    assert len(app_rows) == len(headless_rows)

    for app_row, headless_row in zip(app_rows, headless_rows):
        row_name = app_row.get("name") or headless_row.get("name") or "<unknown>"

        assert app_row.get("name") == headless_row.get("name"), (
            f"\nRow ordering/name mismatch"
            f"\n  app:      {app_row.get('name')!r}"
            f"\n  headless: {headless_row.get('name')!r}"
        )

        for key in app_row:
            assert app_row.get(key) == headless_row.get(key), (
                f"\nMismatch for row={row_name!r}, field={key!r}"
                f"\n  app:      {app_row.get(key)!r}"
                f"\n  headless: {headless_row.get(key)!r}"
            )

    assert app_norm["summary"]["fail_count"] == 0
    assert app_norm["summary"]["review_count"] == 0
    assert app_norm["summary"]["pass_count"] == app_norm["summary"]["barrier_count"]

    for row in app_rows:
        assert row["status"] == "PASS"
        assert row["risk_visual_state"] == "PASS"