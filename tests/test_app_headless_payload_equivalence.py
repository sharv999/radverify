from __future__ import annotations

import json
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "fixtures"

PROJECT_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_project.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalise_payload(payload: dict) -> dict:
    """
    Keep only the stable fields needed to prove that the app-loaded path and
    headless path produce the same calculation/output contract.

    Deliberately ignores timestamps, report metadata and other presentation
    fields that are not calculation-path evidence.
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


def _round_floats(value):
    if isinstance(value, float):
        return round(value, 3)

    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_round_floats(item) for item in value]

    return value


def _load_project_into_app(app, project_payload: dict, tmp_path: Path, monkeypatch):
    """
    Load a project through the real app import/open path when available.

    Falls back to direct project assignment only if the app does not expose the
    expected loader. This keeps the test focused on payload equivalence rather
    than file-dialog mechanics.
    """
    project_path = tmp_path / "app_headless_equivalence_project.json"
    project_path.write_text(json.dumps(project_payload, indent=2), encoding="utf-8")

    if hasattr(app, "load_project_from_path"):
        app.load_project_from_path(project_path)
        return

    if hasattr(app, "_load_project_from_path"):
        app._load_project_from_path(project_path)
        return

    if hasattr(app, "open_project_file"):
        app.open_project_file(project_path)
        return

    # Last-resort fallback for current app implementations that use project IO
    # helpers internally but do not expose a public loader.
    import services.project_io as project_io

    loader = None
    for name in (
        "load_project_from_file",
        "load_project",
        "load_project_file",
        "load_project_from_path",
        "read_project",
        "read_project_file",
    ):
        candidate = getattr(project_io, name, None)
        if callable(candidate):
            loader = candidate
            break

    if loader is None:
        raise AssertionError(
            "No project loader found in services.project_io. "
            "Add the actual loader name to this test helper."
        )

    app.project = loader(project_path)

    if hasattr(app, "refresh_all"):
        app.refresh_all()
    elif hasattr(app, "_refresh_all"):
        app._refresh_all()
    elif hasattr(app, "_refresh_from_project"):
        app._refresh_from_project()


@pytest.mark.integration
def test_app_loaded_project_and_headless_project_build_same_payload(tmp_path, monkeypatch):
    """
    Given the same saved project JSON, the app-loaded path and the headless
    project-dict path must produce the same calculation/output payload.

    This protects against the critical MVP failure mode where the UI tabs agree
    but JSON/PDF/CSV export uses a different source/opening/calculation path.
    """
    from app import ShieldingDesktopApp
    from reports.results_payload_builder import (
        build_results_payload,
        build_results_payload_from_project_dict,
    )

    project_payload = _load_json(PROJECT_PATH)

    app = ShieldingDesktopApp()
    try:
        app.withdraw()
        _load_project_into_app(app, project_payload, tmp_path, monkeypatch)
        app.update_idletasks()

        app_payload = build_results_payload(app)
    finally:
        try:
            app.destroy()
        except Exception:
            pass

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