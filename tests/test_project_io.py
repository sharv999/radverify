from __future__ import annotations

import json
from types import SimpleNamespace

from services.project_io import (
    read_project_payload,
    save_project_to_file,
    write_project_payload,
)


class DummyApp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def prepare_project_for_save(self):
        self.calls.append("prepare_project_for_save")
        return self.payload


def test_write_and_read_project_payload_round_trip(tmp_path):
    path = tmp_path / "project.json"
    payload = {"schema_version": 1, "project_name": "Example"}

    written = write_project_payload(path, payload)

    assert written == path
    assert json.loads(path.read_text(encoding="utf-8"))["project_name"] == "Example"
    assert read_project_payload(path)["project_name"] == "Example"


def test_save_project_to_file_uses_app_save_boundary(tmp_path):
    path = tmp_path / "saved.json"
    app = DummyApp({"schema_version": 1, "project_name": "Saved"})

    written = save_project_to_file(app, path)

    assert written == path
    assert app.calls == ["prepare_project_for_save"]
    assert json.loads(path.read_text(encoding="utf-8"))["project_name"] == "Saved"


def test_project_open_rejects_pet_preview_snapshot_with_specific_guidance(tmp_path):
    path = tmp_path / "pet_case.petpreview.json"
    path.write_text(
        json.dumps(
            {
                "schema": "radshield_pet_ui_preview_state_v2",
                "schema_version": 2,
                "production_eligible": False,
            }
        ),
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(ValueError) as exc_info:
        read_project_payload(path)

    message = str(exc_info.value)
    assert "PET development preview snapshot" in message
    assert "Sources > Load PET Preview" in message
    assert "Unsupported project schema version" not in message


def test_working_project_io_round_trip_preserves_persisted_pet_room_state(tmp_path):
    from geometry.pet_preview_position import PetPreviewPosition
    from models.shielding_models import Project, Room
    from modalities.pet import PetExposurePhase, PetSourceDomain
    from serialization.pet_working_project_state import (
        PetWorkingProjectState,
        get_room_pet_working_state,
        set_room_pet_working_state,
    )
    from services.project_io import load_project_from_file
    from services.project_serializer import project_to_working_dict

    state = PetWorkingProjectState(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            residual_activity_factor=1.0,
            exposure_phases=(
                PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
                PetExposurePhase("Imaging", 1.0, 0.5, 1.0),
            ),
        ),
        position=PetPreviewPosition(3.5, 0.5, 1.0),
    )
    room = Room(name="CT Room 1", modality="CT")
    set_room_pet_working_state(room, state)
    project = Project(project_name="PET working project", rooms=[room], sources=[])

    payload = project_to_working_dict(project)
    assert payload["schema_version"] == 1
    assert payload["file_role"] == "working_project"

    path = tmp_path / "pet_working_project.json"
    write_project_payload(path, payload)
    restored = load_project_from_file(path)

    assert restored.sources == []
    assert get_room_pet_working_state(restored.rooms[0]) == state


def test_project_type_save_reopen_round_trip_preserves_new_build(tmp_path):
    from models.shielding_models import Project
    from services.project_io import load_project_from_file
    from services.project_serializer import project_to_working_dict

    project = Project(project_name="New build case", project_type="new_build")
    path = tmp_path / "new_build.json"
    write_project_payload(path, project_to_working_dict(project))

    restored = load_project_from_file(path)

    assert restored.project_type == "new_build"
    assert json.loads(path.read_text(encoding="utf-8"))["project_type"] == "new_build"


def test_project_type_save_reopen_round_trip_preserves_refurbishment(tmp_path):
    from models.shielding_models import Project
    from services.project_io import load_project_from_file
    from services.project_serializer import project_to_working_dict

    project = Project(project_name="Refurbishment case", project_type="refurbishment")
    path = tmp_path / "refurbishment.json"
    write_project_payload(path, project_to_working_dict(project))

    restored = load_project_from_file(path)

    assert restored.project_type == "refurbishment"
    assert json.loads(path.read_text(encoding="utf-8"))["project_type"] == "refurbishment"


def test_legacy_project_without_project_type_defaults_to_new_build(tmp_path):
    from services.project_io import load_project_from_file
    from services.project_serializer import project_to_working_dict

    path = tmp_path / "legacy.json"
    legacy_payload = {
        "schema_version": 1,
        "project_name": "Legacy case",
        "rooms": [],
        "sources": [],
    }
    write_project_payload(path, legacy_payload)

    restored = load_project_from_file(path)

    assert restored.project_type == "new_build"
    assert "project_type" not in json.loads(path.read_text(encoding="utf-8"))

    resaved = tmp_path / "legacy_resaved.json"
    write_project_payload(resaved, project_to_working_dict(restored))
    assert json.loads(resaved.read_text(encoding="utf-8"))["project_type"] == "new_build"
