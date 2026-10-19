"""V0.4 Step 3: integrity-gated portable field-record restoration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from radverify.models import EvidenceItem, RadVerifyProject
from radverify.packaging import (
    FieldPackageError,
    build_field_package,
    default_restore_folder,
    project_json_for_save,
    resolve_evidence_paths,
    restore_field_package,
    verify_field_package,
)
from radverify.radtwin import project_from_radtwin


def _package(tmp_path: Path) -> tuple[Path, bytes]:
    project = RadVerifyProject()
    project.details.project_id = "SITE-27"
    project.details.site_name = "Field Clinic"
    project.details.inspector = "Physicist X"
    barrier = project.barriers[0]
    barrier.expected_pb_mm = 2.0
    barrier.observed_pb_mm = 1.5
    barrier.status = "Review"
    evidence_file = tmp_path / "proof alpha.txt"
    payload = b"approved test image stand-in\n"
    evidence_file.write_bytes(payload)
    item = EvidenceItem(evidence_id="EV-101", reference="PHOTO-101", file_path=str(evidence_file))
    item.refresh_hash()
    barrier.evidence_items = [item, EvidenceItem(evidence_id="REF-101", reference="Document 1")]
    package = build_field_package(project, tmp_path / "field_package.zip")
    return package, payload


def _rebundle(source: Path, destination: Path, edit):
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    edit(files)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return destination


def _reseal(files: dict[str, bytes]) -> None:
    """Reseal *unsigned* manifest to exercise path and schema validation."""
    manifest = json.loads(files["manifest.json"])
    for row in manifest["files"]:
        data = files[row["path"]]
        row["size"] = len(data)
        row["sha256"] = hashlib.sha256(data).hexdigest()
    files["manifest.json"] = json.dumps(manifest).encode()


def test_restore_portable_package_preserves_native_twin_pdf_and_evidence(tmp_path, monkeypatch):
    source, expected = _package(tmp_path)
    destination = tmp_path / "recipient-PC" / "survey"
    destination.parent.mkdir()
    monkeypatch.chdir(destination.parent)
    restored_project = restore_field_package(source, destination)
    assert restored_project == destination / "project/room.radverify.json"
    assert restored_project.is_file()
    assert (destination / "report/verification_DRAFT.pdf").read_bytes().startswith(b"%PDF")
    assert (destination / "manifest.json").is_file()
    with zipfile.ZipFile(source) as z:
        evidence_name = next(name for name in z.namelist() if name.startswith("evidence/"))
    assert (destination / evidence_name).read_bytes() == expected
    data = json.loads(restored_project.read_text())
    original_relative = data["barrier_inspection"][0]["evidence_items"][0]["file_path"]
    assert original_relative == "../" + evidence_name
    assert "proof_alpha.txt" in evidence_name
    project = RadVerifyProject.from_dict(data)
    resolve_evidence_paths(project, restored_project.parent)
    item = project.barriers[0].evidence_items[0]
    assert item.integrity_status() == "Verified"
    # Editing/saving an extracted project must not reintroduce machine-specific
    # absolute paths for managed evidence, including the derived payload copy.
    saved = project_json_for_save(project, restored_project)
    assert saved["barrier_inspection"][0]["evidence_items"][0]["file_path"] == original_relative
    assert (saved["radstatus_payload"]["barriers"][0]["evidence"][0]
            ["file_path"] == original_relative)
    assert project.barriers[0].expected_pb_mm == 2.0
    assert project.barriers[0].observed_pb_mm == 1.5
    assert project.barriers[0].status == "Review"
    assert project.barriers[0].evidence_items[1].integrity_status() == "Reference only"
    twin = project_from_radtwin(json.loads((destination / "twin/room.radtwin.json").read_text()))
    resolve_evidence_paths(twin, destination / "twin")
    assert twin.barriers[0].evidence_items[0].integrity_status() == "Verified"
    assert verify_field_package(source)["valid"]


def test_restore_refuses_preexisting_destination_and_cannot_modify_it(tmp_path):
    source, _ = _package(tmp_path)
    destination = tmp_path / "client"
    destination.mkdir()
    marker = destination / "old-file.txt"
    marker.write_text("KEEP THIS")
    with pytest.raises(FieldPackageError, match="already exists"):
        restore_field_package(source, destination)
    assert marker.read_text() == "KEEP THIS"


def test_restore_rejects_tampering_without_extracting_anything(tmp_path):
    source, _ = _package(tmp_path)
    tampered = _rebundle(source, tmp_path / "tampered.zip", lambda files:
        files.__setitem__("project/room.radverify.json", files["project/room.radverify.json"] + b"changed"))
    destination = tmp_path / "restored"
    with pytest.raises(FieldPackageError, match="size mismatch"):
        restore_field_package(tampered, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".radverify-restore-*"))


def test_restore_rejects_zip_slip_even_if_manifest_is_resealed(tmp_path):
    source, _ = _package(tmp_path)
    def edit(files):
        files["../outside.txt"] = b"evil"
        manifest = json.loads(files["manifest.json"])
        manifest["files"].append({"path": "../outside.txt", "size": 4, "sha256": hashlib.sha256(b"evil").hexdigest()})
        files["manifest.json"] = json.dumps(manifest).encode()
    forged = _rebundle(source, tmp_path / "slip.zip", edit)
    with pytest.raises(FieldPackageError, match="Unsafe"):
        restore_field_package(forged, tmp_path / "out")
    assert not (tmp_path / "outside.txt").exists()


def test_restore_rejects_resealed_external_evidence_file_link(tmp_path):
    source, _ = _package(tmp_path)
    def edit(files):
        name = "project/room.radverify.json"
        doc = json.loads(files[name])
        doc["barrier_inspection"][0]["evidence_items"][0]["file_path"] = "../../../../target_secret.txt"
        files[name] = json.dumps(doc).encode()
        _reseal(files)
    forged = _rebundle(source, tmp_path / "link.zip", edit)
    assert verify_field_package(forged)["valid"]  # Checksums alone cannot detect a resealed archive.
    with pytest.raises(FieldPackageError, match="Unsafe evidence link"):
        restore_field_package(forged, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_restore_rejects_resealed_unlisted_evidence_file_link(tmp_path):
    source, _ = _package(tmp_path)
    def edit(files):
        name = "twin/room.radtwin.json"
        doc = json.loads(files[name])
        doc["barriers"][0]["verification"]["evidence"][0]["file_path"] = "../evidence/nonexistent.jpg"
        files[name] = json.dumps(doc).encode()
        _reseal(files)
    forged = _rebundle(source, tmp_path / "fake-link.zip", edit)
    with pytest.raises(FieldPackageError, match="Unlisted"):
        restore_field_package(forged, tmp_path / "out")


def test_restore_rejects_case_insensitive_member_collision(tmp_path):
    source, _ = _package(tmp_path)
    def edit(files):
        files["README.TXT"] = files["README.txt"]
        manifest = json.loads(files["manifest.json"])
        manifest["files"].append({"path": "README.TXT", "size": len(files["README.TXT"]),
                                  "sha256": hashlib.sha256(files["README.TXT"]).hexdigest()})
        files["manifest.json"] = json.dumps(manifest).encode()
    forged = _rebundle(source, tmp_path / "collision.zip", edit)
    with pytest.raises(FieldPackageError, match="Case-insensitive"):
        restore_field_package(forged, tmp_path / "out")


def test_default_folder_never_overwrites_and_cli_restores(tmp_path):
    source, _ = _package(tmp_path)
    first = default_restore_folder(source, tmp_path)
    assert first.name == "field_package_restored"
    first.mkdir()
    second = default_restore_folder(source, tmp_path)
    assert second.name == "field_package_restored_2"
    result = subprocess.run([sys.executable, "-m", "radverify.packaging", str(source),
                             "--restore-to", str(second)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "RESTORED:" in result.stdout
    assert (second / "project/room.radverify.json").is_file()
