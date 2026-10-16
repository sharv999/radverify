from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures"

INPUT_PROJECT_PATH = FIXTURES_DIR / "KAT_ct_amber_red_room_project.json"


JSON_SAFE_SCALARS = (str, int, float, bool, type(None))


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Missing JSON fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_json_safe(value: Any, path: str = "$") -> None:
    """
    Recursively assert that a payload contains only JSON-safe values.

    Allowed:
      - dict with string keys
      - list
      - str
      - int
      - float
      - bool
      - None

    Disallowed:
      - Room/Barrier/source objects
      - Path
      - datetime
      - Tkinter variables
      - _HeadlessObject
      - arbitrary classes
    """
    if isinstance(value, JSON_SAFE_SCALARS):
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json_safe(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, child in value.items():
            assert isinstance(key, str), (
                f"Non-string dictionary key at {path}: "
                f"{key!r} ({type(key).__name__})"
            )
            _assert_json_safe(child, f"{path}.{key}")
        return

    raise AssertionError(
        f"Non-JSON-safe value at {path}: "
        f"{value!r} ({type(value).__module__}.{type(value).__name__})"
    )


def test_headless_report_payload_is_json_serialisable():
    """
    The canonical report payload must be clean JSON data.

    This protects JSON/CSV/PDF export paths from leaking live model objects,
    Tkinter variables, Path/datetime objects, or headless adapter objects.
    """
    from reports.results_payload_builder import build_results_payload_from_project_dict

    project_payload = _load_json(INPUT_PROJECT_PATH)

    report_payload = build_results_payload_from_project_dict(project_payload)

    _assert_json_safe(report_payload)

    # Also prove the standard library JSON encoder can serialise it.
    json.dumps(report_payload, sort_keys=True)