"""Portable, checksummed RadVerify field-record ZIP exports.

This is an unsigned integrity archive, not an authenticity signature or certificate.
A package contains a copy of a working project and its twin with *relative*
references; the original in-memory project and linked evidence are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo, is_zipfile

from radverify.models import RadVerifyProject
from radverify.radtwin import project_to_radtwin
from radverify.reporting import build_verification_pdf

PACKAGE_SCHEMA = "radverify-field-package-0.1"
MANIFEST_NAME = "manifest.json"
README_NAME = "README.txt"
_PROJECT_MEMBER = "project/room.radverify.json"
_TWIN_MEMBER = "twin/room.radtwin.json"
_REPORT_MEMBER = "report/verification_DRAFT.pdf"
_CHUNK = 1024 * 1024


class FieldPackageError(ValueError):
    """Package rejected because the evidence or archive is inconsistent."""


def _json_bytes(document: Any) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _safe_filename(name: str) -> str:
    # Avoid path traversal, reserved characters and excessively long filenames.
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(name).name).strip("._")
    return clean[:90] or "evidence"


def _walk_evidence(project: RadVerifyProject):
    for barrier in project.barriers:
        for evidence in barrier.evidence_items:
            yield barrier, evidence


def resolve_evidence_paths(project: RadVerifyProject, source_dir: str | Path) -> None:
    """Resolve relative links on a loaded project/twin against *its file location*.

    This prevents a package extracted away from the application's current
    working directory from appearing to have missing evidence.
    """
    source_dir = Path(source_dir).resolve()
    for _barrier, item in _walk_evidence(project):
        if item.file_path and not Path(item.file_path).is_absolute():
            path = (source_dir / item.file_path).resolve()
            # Archive members always live within their extraction root.
            # For ordinary user files, allow existing relative links that
            # explicitly lead outside the project directory.
            item.file_path = str(path)


def build_field_package(project: RadVerifyProject, output: str | Path) -> Path:
    """Create an atomic portable archive. Reject unreadable/missing/changed evidence.

    Original project state remains unchanged. Evidence files are checked both
    before and during the ZIP read to detect changes while packaging.
    """
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot = deepcopy(project)
    snapshot.sync_opening_inspections()

    evidence_blobs: dict[str, Path] = {}
    evidence_hashes: dict[str, tuple[str, int]] = {}
    path_rewrites: dict[str, str] = {}
    evidence_index: list[dict[str, Any]] = []
    for barrier, item in _walk_evidence(snapshot):
        if not item.file_path:
            evidence_index.append({
                "barrier_id": barrier.barrier_id,
                "evidence_id": item.evidence_id,
                "reference": item.reference,
                "path": None,
                "status": "Reference only",
            })
            continue

        original = Path(item.file_path)
        try:
            if not original.is_file():
                raise FieldPackageError(
                    f"Missing evidence for {barrier.barrier_id} / {item.evidence_id}: {original}"
                )
            if not item.sha256:
                raise FieldPackageError(
                    f"No recorded SHA-256 for {barrier.barrier_id} / {item.evidence_id}; "
                    "re-attach the file or record its hash before export."
                )
            actual_hash, size = _file_sha256(original)
        except OSError as exc:
            raise FieldPackageError(f"Cannot read evidence {item.evidence_id}: {exc}") from exc
        if actual_hash.lower() != item.sha256.lower():
            raise FieldPackageError(
                f"Evidence changed since its SHA-256 was recorded: "
                f"{barrier.barrier_id} / {item.evidence_id} ({original.name})"
            )
        if original.is_symlink():
            raise FieldPackageError(f"Evidence symlinks are not packaged: {original}")
        # The digest supplies globally stable naming and safely handles
        # duplicate basenames without overwriting one another.
        suffix = _safe_filename(original.name)
        member = f"evidence/{actual_hash}_{suffix}"
        if member not in evidence_blobs:
            evidence_blobs[member] = original
            evidence_hashes[member] = (actual_hash, size)
        # The JSON records remain relative to their own subdirectory.
        path_rewrites[item.file_path] = "../" + member
        evidence_index.append({
            "barrier_id": barrier.barrier_id,
            "evidence_id": item.evidence_id,
            "reference": item.reference,
            "path": member,
            "sha256": actual_hash,
            "status": "Included",
        })

    # Derive readiness/integrity while the evidence links still refer to real
    # existing source files. Rewriting the *model* first would falsely flag
    # all relative ZIP links as missing, and turn ready rooms into not-ready.
    native_document = snapshot.to_dict()
    twin_document = project_to_radtwin(snapshot)

    def rewrite_json_evidence_links(node: Any) -> None:
        if isinstance(node, dict):
            if "file_path" in node and node["file_path"] in path_rewrites:
                node["file_path"] = path_rewrites[node["file_path"]]
            for child in node.values():
                rewrite_json_evidence_links(child)
        elif isinstance(node, list):
            for child in node:
                rewrite_json_evidence_links(child)

    # Both JSON files live exactly one level below the package root.
    rewrite_json_evidence_links(native_document)
    rewrite_json_evidence_links(twin_document)
    native_bytes = _json_bytes(native_document)
    twin_bytes = _json_bytes(twin_document)
    readme = (
        "RadVerify portable field record — draft, not a compliance certificate.\n"
        "\n"
        "project/room.radverify.json     Editable RadVerify project\n"
        "twin/room.radtwin.json         Radiation Room Digital Twin\n"
        "report/verification_DRAFT.pdf Draft survey report\n"
        "evidence/                     Linked supporting files\n"
        "manifest.json                 SHA-256 / size inventory\n"
        "\n"
        "Extract the whole ZIP before opening either JSON file. Evidence links\n"
        "are relative to each JSON file and can be opened using RadVerify.\n"
        "Use python -m radverify.packaging <archive.zip> to check integrity.\n"
        "SHA-256 checks accidental modification but does NOT authenticate the\n"
        "author or prevent a person from replacing files AND the manifest.\n"
        "Formal inspection sign-off and regulatory assessment remain separate.\n"
    ).encode("utf-8")

    # Build PDF from the original snapshot, so its evidence-integrity report
    # sees real source paths rather than ZIP-relative links.
    pdf_project = deepcopy(project)
    with tempfile.TemporaryDirectory(prefix="radverify-field-") as tmpdir:
        report_path = build_verification_pdf(pdf_project, Path(tmpdir) / "verification.pdf")
        regular_blobs: dict[str, bytes] = {
            _PROJECT_MEMBER: native_bytes,
            _TWIN_MEMBER: twin_bytes,
            _REPORT_MEMBER: report_path.read_bytes(),
            README_NAME: readme,
        }
        files = []
        for name, payload in sorted(regular_blobs.items()):
            files.append({"path": name, "size": len(payload), "sha256": _sha256(payload)})
        for name, (digest, size) in sorted(evidence_hashes.items()):
            files.append({"path": name, "size": size, "sha256": digest})
        files.sort(key=lambda entry: entry["path"])
        manifest = {
            "schema": PACKAGE_SCHEMA,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "project_id": snapshot.details.project_id,
            "verification_state": project.verification_summary()["verification_state"],
            "documents": {
                "project": _PROJECT_MEMBER,
                "digital_twin": _TWIN_MEMBER,
                "draft_report": _REPORT_MEMBER,
            },
            "evidence_index": evidence_index,
            "files": files,
            "integrity_note": "Unsigned SHA-256 inventory; not an authenticated signature or compliance certification.",
        }
        descriptor = _json_bytes(manifest)

        fd, tempname = tempfile.mkstemp(prefix=".radverify-package-", suffix=".zip", dir=destination.parent)
        os.close(fd)
        temporary = Path(tempname)
        try:
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                for name, payload in sorted(regular_blobs.items()):
                    archive.writestr(name, payload)
                for name, source in sorted(evidence_blobs.items()):
                    with archive.open(name, "w") as output_stream, source.open("rb") as input_stream:
                        digest = hashlib.sha256()
                        length = 0
                        for chunk in iter(lambda: input_stream.read(_CHUNK), b""):
                            digest.update(chunk)
                            length += len(chunk)
                            output_stream.write(chunk)
                        if (digest.hexdigest(), length) != evidence_hashes[name]:
                            raise FieldPackageError(f"Evidence changed during ZIP export: {source}")
                archive.writestr(MANIFEST_NAME, descriptor)
            verify_field_package(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def _safe_member_name(name: str) -> bool:
    # ZIP members always use POSIX paths, and no absolute, dot, or parent paths.
    path = PurePosixPath(name)
    return bool(name and not name.startswith(("/", "\\")) and "\\" not in name
                and ":" not in name and path.parts
                and all(part not in ("..", ".", "") for part in path.parts)
                and not name.endswith("/"))


def verify_field_package(path: str | Path) -> dict[str, Any]:
    """Validate an archive independently, without extracting it or trusting names."""
    archive_path = Path(path)
    if not is_zipfile(archive_path):
        raise FieldPackageError("Not a ZIP archive")
    with ZipFile(archive_path, "r") as archive:
        info = archive.infolist()
        if len(info) > 2000:
            raise FieldPackageError("Too many ZIP entries")
        names = [entry.filename for entry in info]
        if len(names) != len(set(names)):
            raise FieldPackageError("Duplicate ZIP entries")
        for entry in info:
            if not _safe_member_name(entry.filename):
                raise FieldPackageError(f"Unsafe ZIP member name: {entry.filename!r}")
            if ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                raise FieldPackageError(f"ZIP symlinks are not allowed: {entry.filename}")
        if MANIFEST_NAME not in names:
            raise FieldPackageError("Missing manifest.json")
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        except (ValueError, UnicodeError) as exc:
            raise FieldPackageError("Invalid manifest.json") from exc
        if not isinstance(manifest, dict) or manifest.get("schema") != PACKAGE_SCHEMA:
            raise FieldPackageError("Unrecognised manifest schema")
        file_entries = manifest.get("files")
        if not isinstance(file_entries, list) or any(not isinstance(row, dict) for row in file_entries):
            raise FieldPackageError("Manifest files must be an array")
        declared = {row.get("path") for row in file_entries}
        if len(declared) != len(file_entries) or any(not isinstance(name, str) for name in declared):
            raise FieldPackageError("Duplicate or invalid manifest file path")
        if set(names) != declared | {MANIFEST_NAME}:
            raise FieldPackageError("ZIP contents do not match manifest inventory")
        if sum(entry.file_size for entry in info) > 10 * 1024**3:
            raise FieldPackageError("ZIP uncompressed contents exceed 10 GiB")
        for row in file_entries:
            if not _safe_member_name(row["path"]):
                raise FieldPackageError("Unsafe path in manifest")
            entry = archive.getinfo(row["path"])
            if not isinstance(row.get("size"), int) or entry.file_size != row["size"]:
                raise FieldPackageError(f"File size mismatch: {row['path']}")
            digest = hashlib.sha256()
            try:
                with archive.open(entry) as handle:
                    for chunk in iter(lambda: handle.read(_CHUNK), b""):
                        digest.update(chunk)
            except Exception as exc:
                raise FieldPackageError(f"Cannot read ZIP entry {row['path']}: {exc}") from exc
            if digest.hexdigest() != row.get("sha256"):
                raise FieldPackageError(f"SHA-256 mismatch: {row['path']}")
        return {
            "valid": True,
            "files": len(file_entries),
            "evidence_items": len(manifest.get("evidence_index", [])),
            "project_id": manifest.get("project_id", ""),
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check integrity of a RadVerify field-record ZIP")
    parser.add_argument("zip_path", help="Path to a RadVerify field package ZIP")
    args = parser.parse_args()
    try:
        result = verify_field_package(args.zip_path)
    except (FieldPackageError, OSError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"VALID: {result['files']} files, {result['evidence_items']} evidence links (unsigned integrity check)")
