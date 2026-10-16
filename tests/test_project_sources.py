from __future__ import annotations

"""
Regression tests for project source ownership.

These tests protect the source-of-truth rule that fixed several ksec regressions:

    project.sources is authoritative
    room.sources is a compatibility mirror/cache only

They deliberately avoid Tkinter. The goal is to test the source list behaviour
with simple model objects.

Run from project root:

    python -m pytest tests/test_project_sources.py
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from services.ksec_status import resolve_ksec_status


@dataclass
class DummySource:
    name: str
    source_type: str
    room_name: str = ""
    radiation_type: str = "xray_120kvp"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class DummyRoom:
    name: str
    modality: str = "CT"
    sources: list[DummySource] = field(default_factory=list)


@dataclass
class DummyProject:
    rooms: list[DummyRoom] = field(default_factory=list)
    sources: list[DummySource] = field(default_factory=list)


class ProjectSourceStore:
    """
    Tiny test double for the app source-store behaviour.

    This mirrors the intended app rule without importing the Tkinter app:

        - get_sources_for_room() reads project.sources only
        - migrate_room_sources_to_project() migrates legacy room.sources only
          when project.sources has no sources for that room
        - sync_room_sources_from_project() mirrors project.sources into room.sources
    """

    def __init__(self, project: DummyProject):
        self.project = project

    def get_sources_for_room(self, room_name: str) -> list[DummySource]:
        room_name = str(room_name or "").strip()
        return [
            src for src in getattr(self.project, "sources", []) or []
            if str(getattr(src, "room_name", "") or "").strip() == room_name
        ]

    def migrate_room_sources_to_project(self, room: DummyRoom | None) -> list[DummySource]:
        if room is None:
            return []

        current = self.get_sources_for_room(room.name)
        if current:
            room.sources = list(current)
            return current

        migrated: list[DummySource] = []
        for src in list(getattr(room, "sources", []) or []):
            src.room_name = room.name
            self.project.sources.append(src)
            migrated.append(src)

        room.sources = list(migrated)
        return migrated

    def sync_room_sources_from_project(self, room: DummyRoom | None) -> list[DummySource]:
        if room is None:
            return []

        sources = self.get_sources_for_room(room.name)
        if not sources and getattr(room, "sources", None):
            sources = self.migrate_room_sources_to_project(room)

        room.sources = list(sources)
        return sources


def _philips_null_source(room_name: str = "CT Room 1") -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        room_name=room_name,
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "NULL ksec — manual override required",
        },
    )


def _philips_manual_override_source(room_name: str = "CT Room 1") -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        room_name=room_name,
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "0.015",
            "manual_ksec_override": "1",
            "manual_ksec_entered_by": "Test Physicist",
            "manual_ksec_reason": "Manual override test",
            "manual_ksec_source_reference": "Vendor source page 12",
            "manual_ksec_last_updated": "2026-05-21 10:30",
        },
    )


def _ge_database_source(room_name: str = "CT Room 1") -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        room_name=room_name,
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "ksec_mGy_per_100mAs_at_1m": "0.0457",
            "manual_ksec_override": "0",
            "scanner_source": "JSON worst-case Ksec lookup (GE_REVOLUTION_APEX_FAMILY)",
        },
    )


def test_project_sources_win_over_stale_room_sources_cache():
    room = DummyRoom(name="CT Room 1")
    project_source = _philips_manual_override_source(room.name)
    stale_room_source = _philips_null_source(room.name)

    project = DummyProject(
        rooms=[room],
        sources=[project_source],
    )
    room.sources = [stale_room_source]

    store = ProjectSourceStore(project)
    synced = store.sync_room_sources_from_project(room)

    assert synced == [project_source]
    assert room.sources == [project_source]

    status = resolve_ksec_status(room.sources[0])
    assert status["basis"] == "manual_override"
    assert status["status"] == "REVIEW"
    assert status["ksec"] == pytest.approx(0.015)


def test_legacy_room_sources_migrate_when_project_sources_empty():
    room = DummyRoom(name="CT Room 1")
    legacy_source = _ge_database_source(room.name)
    room.sources = [legacy_source]

    project = DummyProject(
        rooms=[room],
        sources=[],
    )

    store = ProjectSourceStore(project)
    migrated = store.sync_room_sources_from_project(room)

    assert migrated == [legacy_source]
    assert project.sources == [legacy_source]
    assert room.sources == [legacy_source]
    assert legacy_source.room_name == room.name

    status = resolve_ksec_status(project.sources[0])
    assert status["basis"] == "database"
    assert status["status"] == "PASS"


def test_legacy_room_sources_do_not_migrate_twice():
    room = DummyRoom(name="CT Room 1")
    legacy_source = _ge_database_source(room.name)
    room.sources = [legacy_source]

    project = DummyProject(
        rooms=[room],
        sources=[],
    )

    store = ProjectSourceStore(project)

    first = store.sync_room_sources_from_project(room)
    second = store.sync_room_sources_from_project(room)

    assert first == [legacy_source]
    assert second == [legacy_source]
    assert project.sources == [legacy_source]
    assert len(project.sources) == 1


def test_sync_room_sources_replaces_stale_cache_after_project_source_changes():
    room = DummyRoom(name="CT Room 1")
    initial_source = _philips_null_source(room.name)
    updated_source = _philips_manual_override_source(room.name)

    project = DummyProject(
        rooms=[room],
        sources=[initial_source],
    )
    store = ProjectSourceStore(project)

    store.sync_room_sources_from_project(room)
    assert room.sources == [initial_source]
    assert resolve_ksec_status(room.sources[0])["status"] == "FAIL"

    # Simulate the Sources tab writing the corrected source into project.sources.
    project.sources = [updated_source]

    store.sync_room_sources_from_project(room)

    assert room.sources == [updated_source]
    status = resolve_ksec_status(room.sources[0])
    assert status["basis"] == "manual_override"
    assert status["status"] == "REVIEW"


def test_get_sources_for_room_filters_by_exact_room_name():
    room_a = DummyRoom(name="CT Room A")
    room_b = DummyRoom(name="CT Room B")

    src_a = _ge_database_source(room_a.name)
    src_b = _philips_manual_override_source(room_b.name)
    orphan = _philips_null_source("Other Room")

    project = DummyProject(
        rooms=[room_a, room_b],
        sources=[src_a, src_b, orphan],
    )

    store = ProjectSourceStore(project)

    assert store.get_sources_for_room("CT Room A") == [src_a]
    assert store.get_sources_for_room("CT Room B") == [src_b]
    assert store.get_sources_for_room("Missing Room") == []


def test_manual_override_audit_survives_room_mirror_sync():
    room = DummyRoom(name="CT Room 1")
    src = _philips_manual_override_source(room.name)

    project = DummyProject(
        rooms=[room],
        sources=[src],
    )

    store = ProjectSourceStore(project)
    store.sync_room_sources_from_project(room)

    mirrored = room.sources[0]

    assert mirrored.params["manual_ksec_override"] == "1"
    assert mirrored.params["manual_ksec_entered_by"] == "Test Physicist"
    assert mirrored.params["manual_ksec_reason"] == "Manual override test"
    assert mirrored.params["manual_ksec_source_reference"] == "Vendor source page 12"
    assert mirrored.params["manual_ksec_last_updated"] == "2026-05-21 10:30"

    status = resolve_ksec_status(mirrored)
    assert status["audit_complete"] is True


def test_null_ksec_project_source_remains_fail_after_room_sync():
    room = DummyRoom(name="CT Room 1")
    src = _philips_null_source(room.name)

    project = DummyProject(
        rooms=[room],
        sources=[src],
    )

    store = ProjectSourceStore(project)
    store.sync_room_sources_from_project(room)

    status = resolve_ksec_status(room.sources[0])

    assert status["basis"] == "manual_override_required"
    assert status["status"] == "FAIL"
    assert status["ksec"] is None
