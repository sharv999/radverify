"""Loss-resistant persistence primitives for editable field records.

Writes a complete sibling temporary file before replacing the destination.
A failed serialization/write leaves the previous destination bytes intact.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def atomic_write_json(path: str | Path, document: Any) -> Path:
    destination = Path(path)
    # Render before creating a temp file, so invalid data cannot disturb saved work.
    payload = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination.name}.", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, destination)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return destination


def read_native_project(path: str | Path):
    """Strictly load one supported editable project without changing GUI state."""
    from radverify.models import RadVerifyProject
    from radverify.packaging import resolve_evidence_paths

    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "radverify-0.1":
        raise ValueError("Unsupported or missing RadVerify project schema_version")
    project = RadVerifyProject.from_dict(data)
    resolve_evidence_paths(project, source.parent)
    return project
