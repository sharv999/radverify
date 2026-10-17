from __future__ import annotations

from pathlib import Path

import pytest

from app import RadVerifyApp
from radverify.models import EvidenceItem, RadVerifyProject
from radverify.radtwin import project_from_radtwin, project_to_radtwin


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset_app(app):
    project = RadVerifyProject()
    project.details.inspector = "Inspector A"
    project.details.inspection_date = "2026-10-17"
    app.project = project
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()


def test_evidence_file_hash_detects_unchanged_and_changed_file(tmp_path: Path):
    evidence_file = tmp_path / "wall_photo.txt"
    evidence_file.write_text("original evidence", encoding="utf-8")
    item = EvidenceItem(
        evidence_id="N-WALL-EV01",
        evidence_type="Photo",
        reference="Photo 1",
        file_path=str(evidence_file),
    )
    digest = item.refresh_hash()
    assert len(digest) == 64
    assert item.integrity_status() == "Verified"

    evidence_file.write_text("changed evidence", encoding="utf-8")
    assert item.integrity_status() == "File changed"


def test_native_project_and_radstatus_preserve_structured_evidence(tmp_path: Path):
    evidence_file = tmp_path / "north_wall.jpg"
    evidence_file.write_bytes(b"not-a-real-image-but-stable-test-evidence")
    project = RadVerifyProject()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    item = EvidenceItem(
        evidence_id="N-WALL-EV01",
        evidence_type="Photo",
        reference="IMG_0102",
        file_path=str(evidence_file),
        inspection_date="2026-10-17",
        inspector="Inspector A",
        description="North wall junction",
    )
    item.refresh_hash()
    north.evidence_items.append(item)
    north.evidence_ref = "IMG_0102"

    saved = project.to_dict()
    evidence_json = saved["barrier_inspection"][0]["evidence_items"][0]
    assert evidence_json["reference"] == "IMG_0102"
    assert evidence_json["sha256"] == item.sha256
    assert saved["radstatus_payload"]["barriers"][0]["evidence"][0]["inspector"] == "Inspector A"

    restored = RadVerifyProject.from_dict(saved)
    restored_north = next(b for b in restored.barriers if b.barrier_id == "N wall")
    assert restored_north.evidence_items[0].evidence_id == "N-WALL-EV01"
    assert restored_north.evidence_items[0].sha256 == item.sha256


def test_digital_twin_round_trip_preserves_structured_evidence():
    project = RadVerifyProject()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    north.evidence_ref = "Drawing A-401"
    north.evidence_items.append(
        EvidenceItem(
            evidence_id="N-WALL-EV01",
            evidence_type="Drawing",
            reference="A-401 Rev C",
            inspection_date="2026-10-17",
            inspector="Inspector A",
            description="Construction drawing reference",
        )
    )

    twin = project_to_radtwin(project)
    north_twin = next(b for b in twin["barriers"] if b["id"] == "N wall")
    assert north_twin["verification"]["evidence"][0]["reference"] == "A-401 Rev C"

    restored = project_from_radtwin(twin)
    restored_north = next(b for b in restored.barriers if b.barrier_id == "N wall")
    assert restored_north.evidence_ref == "Drawing A-401"
    assert len(restored_north.evidence_items) == 1
    assert restored_north.evidence_items[0].evidence_type == "Drawing"
    assert restored_north.evidence_items[0].description == "Construction drawing reference"


def test_barrier_workspace_adds_multiple_evidence_records_and_updates_summary(app, tmp_path: Path):
    assert app.barrier_tab.select_barrier("N wall") is True
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(b"evidence bytes")
    photo = EvidenceItem(
        evidence_id="N-WALL-EV01",
        evidence_type="Photo",
        reference="IMG_0201",
        file_path=str(file_path),
        inspection_date="2026-10-17",
        inspector="Inspector A",
        description="Wall/ceiling junction",
    )
    photo.refresh_hash()
    reference = EvidenceItem(
        evidence_id="N-WALL-EV02",
        evidence_type="Drawing",
        reference="A-401 Rev D",
        inspection_date="2026-10-17",
        inspector="Inspector A",
        description="Approved construction drawing",
    )

    assert app.barrier_tab.add_evidence_item("N wall", photo) is True
    assert app.barrier_tab.add_evidence_item("N wall", reference) is True
    north = next(b for b in app.project.barriers if b.barrier_id == "N wall")
    assert len(north.evidence_items) == 2
    assert north.evidence_ref == "IMG_0201"
    assert app.barrier_tab.evidence_summary(north) == "2 items — IMG_0201"
    assert len(app.barrier_tab.evidence_tree.get_children()) == 2
    assert app._dirty is True
