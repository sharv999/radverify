"""V0.4 Step 2: portable ZIP, evidence integrity, cross-computer paths."""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path
import zipfile

import pytest

from radverify.models import EvidenceItem, MeasurementPoint, MeasurementRecord, RadVerifyProject
from radverify.packaging import (
    FieldPackageError,
    build_field_package,
    resolve_evidence_paths,
    verify_field_package,
)
from radverify.radtwin import project_from_radtwin


def _survey(tmp_path: Path) -> tuple[RadVerifyProject, Path]:
    p = RadVerifyProject()
    p.details.project_id = "FIELD-009"
    p.details.site_name = "Example Hospital"
    p.geometry.length_m = 4.6
    p.geometry.width_m = 7.2
    b = next(b for b in p.barriers if b.barrier_id == "N wall")
    b.status = "Review"
    b.expected_pb_mm = 2.0
    b.observed_pb_mm = 1.5
    file = tmp_path / "photo & drawing.txt"
    file.write_bytes(b"test original evidence\n")
    e = EvidenceItem(evidence_id="EV-001", file_path=str(file), reference="PIC-01")
    e.refresh_hash()
    b.evidence_items.append(e)
    b.evidence_items.append(EvidenceItem(evidence_id="REF-002", reference="Site verbal record"))
    p.measurements = [MeasurementPoint(point_id="MP01", x_m=1.2, y_m=3.4)]
    p.measurements[0].add_measurement_record(
        MeasurementRecord(record_id="MP01-M01", reading_uSv_h=0.8,
                          background_uSv_h=0.1, instrument="Meter 1", status="Review")
    )
    return p, file


def test_archive_round_trip_contains_pdf_twin_native_and_relative_evidence(tmp_path, monkeypatch):
    p, original = _survey(tmp_path)
    expected_original_path = p.barriers[0].evidence_items[0].file_path
    target = tmp_path / "field_package.zip"
    build_field_package(p, target)
    assert verify_field_package(target)["valid"] is True
    assert p.barriers[0].evidence_items[0].file_path == expected_original_path
    with zipfile.ZipFile(target) as package:
        names = package.namelist()
        assert "manifest.json" in names
        assert "report/verification_DRAFT.pdf" in names
        assert package.read("report/verification_DRAFT.pdf").startswith(b"%PDF")
        members = [x for x in names if x.startswith("evidence/")]
        assert len(members) == 1
        assert package.read(members[0]) == original.read_bytes()
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["evidence_index"][1]["status"] == "Reference only"
        native = json.loads(package.read("project/room.radverify.json"))
        twin = json.loads(package.read("twin/room.radtwin.json"))
        ref1 = native["barrier_inspection"][0]["evidence_items"][0]["file_path"]
        ref2 = twin["barriers"][0]["verification"]["evidence"][0]["file_path"]
        assert ref1 == ref2 == "../" + members[0]
        assert str(tmp_path) not in json.dumps(native)
        assert str(tmp_path) not in json.dumps(twin)
        assert twin["verification_summary"]["barriers"]["evidence_integrity_issues"] == 0
        assert native["radstatus_payload"]["verification_summary"]["barriers"]["evidence_integrity_issues"] == 0
        assert twin["geometry"]["dimensions_m"]["west_east"] == 7.2
        assert native["measurement_points"][0]["measurement_history"][0]["corrected_uSv_h"] == pytest.approx(0.7)

    destination = tmp_path / "on-another-PC"
    with zipfile.ZipFile(target) as package:
        package.extractall(destination)
    # Move current working directory; both formats must resolve evidence links
    # relative to the loaded JSON and not the process cwd.
    monkeypatch.chdir(tmp_path)
    native_project = RadVerifyProject.from_dict(json.loads((destination / "project/room.radverify.json").read_text()))
    resolve_evidence_paths(native_project, destination / "project")
    assert native_project.barriers[0].evidence_items[0].integrity_status() == "Verified"
    twin_project = project_from_radtwin(json.loads((destination / "twin/room.radtwin.json").read_text()))
    resolve_evidence_paths(twin_project, destination / "twin")
    assert twin_project.barriers[0].evidence_items[0].integrity_status() == "Verified"


@pytest.mark.parametrize("failure", ["missing", "changed", "no-hash"])
def test_missing_changed_or_unhashed_evidence_blocks_export_and_preserves_old_zip(tmp_path, failure):
    p, file = _survey(tmp_path)
    target = tmp_path / "existing.zip"
    target.write_bytes(b"previous archive remains intact")
    if failure == "missing":
        file.unlink()
    elif failure == "changed":
        file.write_bytes(b"mutated evidence")
    else:
        p.barriers[0].evidence_items[0].sha256 = ""
    with pytest.raises(FieldPackageError):
        build_field_package(p, target)
    assert target.read_bytes() == b"previous archive remains intact"
    assert not list(tmp_path.glob(".radverify-package-*"))


def test_export_does_not_replace_existing_file_if_pdf_generation_fails(tmp_path, monkeypatch):
    p, _ = _survey(tmp_path)
    target = tmp_path / "existing.zip"
    target.write_bytes(b"prior")
    from radverify import packaging
    monkeypatch.setattr(packaging, "build_verification_pdf", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("PDF failed")))
    with pytest.raises(RuntimeError, match="PDF failed"):
        build_field_package(p, target)
    assert target.read_bytes() == b"prior"


def test_verifier_rejects_tampered_or_unlisted_member(tmp_path):
    p, _ = _survey(tmp_path)
    target = build_field_package(p, tmp_path / "source.zip")
    with zipfile.ZipFile(target) as z:
        blobs = {name: z.read(name) for name in z.namelist()}
    blobs["project/room.radverify.json"] += b"altered"
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as z:
        for name, blob in blobs.items():
            z.writestr(name, blob)
    with pytest.raises(FieldPackageError, match="size mismatch"):
        verify_field_package(tampered)

    with zipfile.ZipFile(tampered, "a") as z:
        z.writestr("unexpected.txt", "not registered")
    with pytest.raises(FieldPackageError, match="do not match"):
        verify_field_package(tampered)


def test_verifier_rejects_zip_slip_and_duplicate_members(tmp_path):
    zipped = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zipped, "w") as z:
        z.writestr("../escape.txt", "bad")
        z.writestr("manifest.json", "{}")
    with pytest.raises(FieldPackageError, match="Unsafe"):
        verify_field_package(zipped)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr("a.txt", "one")
            z.writestr("a.txt", "two")
            z.writestr("manifest.json", "{}")
    with pytest.raises(FieldPackageError, match="Duplicate"):
        verify_field_package(zipped)


def test_uninspected_reference_only_records_can_be_packaged_without_false_pass(tmp_path):
    project = RadVerifyProject()
    project.barriers[0].evidence_items.append(EvidenceItem(evidence_id="REF", reference="Drawing 2"))
    archive = build_field_package(project, tmp_path / "uninspected.zip")
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["verification_state"] == "Incomplete"
        assert manifest["evidence_index"][0]["status"] == "Reference only"
        assert verify_field_package(archive)["valid"]
