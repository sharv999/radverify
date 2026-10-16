from __future__ import annotations

from models.shielding_models import Project, project_to_dict


FILE_ROLE_WORKING_PROJECT = "working_project"
SAVE_SCHEMA_NAME = "radshield_working_project_v1"
SAVE_SCHEMA_VERSION = 1


def project_to_working_dict(project: Project) -> dict:
    data = project_to_dict(project)

    # project.sources is canonical; avoid stale duplicated room sources.
    for room_data in data.get("rooms", []) or []:
        room_data["sources"] = []

    data["file_role"] = FILE_ROLE_WORKING_PROJECT
    data["save_schema"] = SAVE_SCHEMA_NAME
    data["schema_version"] = SAVE_SCHEMA_VERSION

    return data