from types import SimpleNamespace

from tabs.project_tab_actions import (
    _default_room_name_for_modality,
    _rename_single_room,
)


def _app(room, project_sources=None):
    return SimpleNamespace(
        project=SimpleNamespace(
            rooms=[room],
            sources=list(project_sources or []),
        )
    )


def test_registry_default_room_name_follows_single_room_modality():
    assert _default_room_name_for_modality("CT") == "CT Room 1"
    assert _default_room_name_for_modality("SPECT") == "SPECT Room 1"
    assert _default_room_name_for_modality("PET") == "PET Room 1"


def test_single_room_rename_keeps_room_name_references_aligned():
    geometry = SimpleNamespace(room_name="CT Room 1")
    room_source = SimpleNamespace(room_name="CT Room 1")
    project_source = SimpleNamespace(room_name="CT Room 1")
    room = SimpleNamespace(
        name="CT Room 1",
        modality="CT",
        geometry=geometry,
        sources=[room_source],
    )
    app = _app(room, project_sources=[project_source])

    new_name = _rename_single_room(app, room, "SPECT Room 1")

    assert new_name == "SPECT Room 1"
    assert room.name == "SPECT Room 1"
    assert room.geometry.room_name == "SPECT Room 1"
    assert room_source.room_name == "SPECT Room 1"
    assert project_source.room_name == "SPECT Room 1"


def test_single_room_contract_uses_fixed_room_one_names():
    current = SimpleNamespace(
        name="CT Room 1",
        modality="CT",
        geometry=SimpleNamespace(room_name="CT Room 1"),
        sources=[],
    )
    app = _app(current)

    assert _default_room_name_for_modality("PET") == "PET Room 1"
    assert len(app.project.rooms) == 1
