from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import subprocess
import sys

FIXTURES_DIR = Path(__file__).parent / "fixtures"

BASE_PROJECT_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_project.json"


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Missing JSON fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_project_into_app(
    app: Any,
    project_payload: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_path = tmp_path / "KAT_ct_amber_red_room_project.json"
    project_path.write_text(json.dumps(project_payload, indent=2), encoding="utf-8")

    import tkinter.filedialog as filedialog

    monkeypatch.setattr(
        filedialog,
        "askopenfilename",
        lambda *args, **kwargs: str(project_path),
    )

    app.open_project()


def _assert_json_safe(value: Any, path: str = "$") -> None:
    if isinstance(value, (str, int, float, bool, type(None))):
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json_safe(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, child in value.items():
            assert isinstance(key, str), f"Non-string key at {path}: {key!r}"
            _assert_json_safe(child, f"{path}.{key}")
        return

    raise AssertionError(
        f"Non-JSON-safe value at {path}: "
        f"{value!r} ({type(value).__module__}.{type(value).__name__})"
    )


def _first_room(payload: dict[str, Any]) -> dict[str, Any]:
    rooms = payload.get("rooms") or []
    assert rooms, "Payload contains no rooms"
    assert isinstance(rooms[0], dict), "First room is not a dictionary"
    return rooms[0]


@pytest.mark.integration
def test_app_prepared_project_can_be_replayed_headlessly(tmp_path, monkeypatch):
    """
    A project prepared by the GUI save path must be clean JSON and must be
    sufficient for the headless report payload builder.

    This protects the boundary:

        app.open_project()
            -> app.prepare_project_for_save()
            -> JSON round trip
            -> build_results_payload_from_project_dict()

    Tk startup is isolated in a subprocess because Tcl/Tk can be fragile in a
    long pytest process on Windows/Python 3.14.
    """
    prepared_path = tmp_path / "prepared_project.json"
    stdout_path = tmp_path / "prepared_project_stdout.txt"
    stderr_path = tmp_path / "prepared_project_stderr.txt"

    code = rf'''
import json
from pathlib import Path

from app import ShieldingDesktopApp
from services.project_io import load_project_from_file
from reports.results_payload_builder import build_results_payload_from_project_dict

base_project_path = Path(r"{BASE_PROJECT_PATH}")
prepared_path = Path(r"{prepared_path}")

app = None
try:
    app = ShieldingDesktopApp()
    app.withdraw()

    app.project = load_project_from_file(base_project_path)

    if hasattr(app, "prepare_project_for_save"):
        prepared = app.prepare_project_for_save()
    elif hasattr(app, "_prepare_project_for_save"):
        prepared = app._prepare_project_for_save()
    else:
        prepared = app.project

    if hasattr(prepared, "to_dict"):
        prepared_payload = prepared.to_dict()
    elif isinstance(prepared, dict):
        prepared_payload = prepared
    else:
        raise AssertionError(f"Unsupported prepared project type: {{type(prepared)!r}}")

    prepared_path.write_text(
        json.dumps(prepared_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    round_trip_payload = json.loads(prepared_path.read_text(encoding="utf-8"))
    report_payload = build_results_payload_from_project_dict(round_trip_payload)

    assert isinstance(report_payload, dict)
    assert report_payload.get("rooms") or report_payload.get("room_results") or report_payload.get("barriers")
finally:
    if app is not None:
        app.destroy()
'''

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
        "Prepared project subprocess failed"
        f"\nSTDOUT:\n{stdout_text}"
        f"\nSTDERR:\n{stderr_text}"
    )

    assert prepared_path.exists()


@pytest.mark.integration
def test_app_prepared_project_roundtrip_preserves_opening_rows(tmp_path, monkeypatch):
    """
    Door/viewing-panel geometry must survive the app save-preparation pathway
    and remain available to the headless report builder.
    """
    from app import ShieldingDesktopApp
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(BASE_PROJECT_PATH)

    app = ShieldingDesktopApp()
    try:
        app.withdraw()
        _load_project_into_app(app, project_payload, tmp_path, monkeypatch)
        app.update_idletasks()

        prepared_project = app.prepare_project_for_save()
    finally:
        try:
            app.destroy()
        except Exception:
            pass

    round_tripped_project = json.loads(json.dumps(prepared_project, sort_keys=True))
    payload = build_results_payload_from_project_dict(round_tripped_project)

    room = _first_room(payload)
    barriers = room.get("barriers") or []

    opening_rows = [
        row
        for row in barriers
        if str(row.get("barrier_element_type", "") or "")
        .strip()
        .lower()
        .replace(" ", "_")
        in {"door", "viewing_panel"}
    ]

    assert len(opening_rows) == 3

    names = {str(row.get("name", "") or "") for row in opening_rows}
    assert names == {
        "D1",
        "VP2",
        "VP3",
    }

    for row in opening_rows:
        assert isinstance(row.get("parent_barrier"), str)
    role = (
        str(row.get("barrier_role", "") or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )
    assert role in {"door", "viewing_panel"}