from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.shielding_models import Project, project_from_dict
from serialization.schema_migration import migrate_project_schema
from serialization.pet_preview_state import PET_PREVIEW_STATE_SCHEMA
from serialization.spect_preview_state import SPECT_PREVIEW_STATE_SCHEMA


def read_project_payload(path: str | Path) -> dict[str, Any]:
    """Read and migrate a Radshield working-project JSON payload."""
    project_path = Path(path)
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Project file must contain a JSON object.")

    # PET preview snapshots are a deliberately separate non-production file
    # format.  Do not pass them through working-project schema migration: their
    # schema_version currently differs from the working-project version and,
    # more importantly, they do not contain a Project payload at all.
    if payload.get("schema") == PET_PREVIEW_STATE_SCHEMA:
        raise ValueError(
            "This file is a PET development preview snapshot, not a Radshield "
            "working project. Load it from Sources > Load PET Preview... instead."
        )
    if payload.get("schema") == SPECT_PREVIEW_STATE_SCHEMA:
        raise ValueError(
            "This file is a SPECT development preview snapshot, not a Radshield "
            "working project. Load it from the SPECT Preview panel instead."
        )

    return migrate_project_schema(payload)


def load_project_from_file(path: str | Path) -> Project:
    """Load a Radshield project model from disk and validate modality working state."""
    project = project_from_dict(read_project_payload(path))
    from serialization.spect_working_project_state import validate_project_spect_working_states

    validate_project_spect_working_states(project)
    return project


def write_project_payload(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write a Radshield working-project JSON payload to disk."""
    project_path = Path(path)
    project_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return project_path


def save_project_to_file(app: Any, path: str | Path) -> Path:
    """Synchronise the app state and save the editable project JSON to disk."""
    payload = getattr(app, "prepare_project" + "_for_save")()
    return write_project_payload(path, payload)
