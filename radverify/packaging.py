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
import shutil
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


def project_json_for_save(project: RadVerifyProject, path: str | Path) -> dict[str, Any]:
    """Keep package-managed evidence links relative after a restored project is saved.

    Other ordinary project/evidence links retain their existing behaviour.
    Newly attached *external* files remain external until the next ZIP export.
    """
    document = project.to_dict()
    project_path = Path(path).resolve()
    if project_path.parent.name != "project":
        return document
    package_root = project_path.parent.parent
    if not (package_root / MANIFEST_NAME).is_file():
        return document
    evidence_root = (package_root / "evidence").resolve()

    def update(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("file_path")
            if isinstance(value, str) and value:
                actual = Path(value)
                if actual.is_absolute():
                    try:
                        rel = actual.resolve().relative_to(evidence_root)
                    except ValueError:
                        pass
                    else:
                        node["file_path"] = "../evidence/" + rel.as_posix()
            for child in node.values():
                update(child)
        elif isinstance(node, list):
            for child in node:
                update(child)

    update(document)
    return document


def _validate_restorable_member_names(names: list[str]) -> None:
    """Reject ZIP paths that could collide or escape on Windows filesystems."""
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    normalised: set[str] = set()
    for name in names:
        if not _safe_member_name(name) or PurePosixPath(name).as_posix() != name:
            raise FieldPackageError(f"Unsafe archive member: {name!r}")
        components = name.split("/")
        if any(not component or component in (".", "..")
               or component.endswith((".", " "))
               or component.split(".")[0].upper() in reserved
               or any(ord(char) < 32 for char in component)
               for component in components):
            raise FieldPackageError(f"Unsafe Windows archive member: {name!r}")
        key = name.casefold()
        if key in normalised:
            raise FieldPackageError(f"Case-insensitive filename collision: {name!r}")
        normalised.add(key)


def _validate_restoration_documents(archive: ZipFile, manifest: dict[str, Any]) -> None:
    """Require known documents and strictly contained, recorded evidence links."""
    documents = manifest.get("documents")
    expected = {"project": _PROJECT_MEMBER, "digital_twin": _TWIN_MEMBER,
                "draft_report": _REPORT_MEMBER}
    if not isinstance(documents, dict) or any(documents.get(k) != v for k, v in expected.items()):
        raise FieldPackageError("Package does not declare expected RadVerify documents")

    entries = {row["path"]: row for row in manifest["files"]}
    for member in (*expected.values(), README_NAME):
        if member not in entries:
            raise FieldPackageError(f"Missing required file: {member}")

    try:
        native = json.loads(archive.read(_PROJECT_MEMBER))
        twin = json.loads(archive.read(_TWIN_MEMBER))
    except (UnicodeError, ValueError) as exc:
        raise FieldPackageError("Invalid project or Digital Twin JSON") from exc
    if not isinstance(native, dict) or native.get("schema_version") != "radverify-0.1":
        raise FieldPackageError("Unsupported native RadVerify project schema")
    if not isinstance(twin, dict) or twin.get("schema") != "radiation-room-digital-twin-0.1":
        raise FieldPackageError("Unsupported Radiation Room Digital Twin schema")
    if not archive.read(_REPORT_MEMBER).startswith(b"%PDF"):
        raise FieldPackageError("Draft verification report is not a PDF")

    index = manifest.get("evidence_index")
    if not isinstance(index, list):
        raise FieldPackageError("Missing evidence index")
    indexed: set[tuple[str, str]] = set()
    for item in index:
        if not isinstance(item, dict):
            raise FieldPackageError("Invalid evidence index entry")
        path = item.get("path")
        if path is None:
            if item.get("status") != "Reference only":
                raise FieldPackageError("Inconsistent reference-only evidence")
            continue
        if not isinstance(path, str) or not path.startswith("evidence/") or path not in entries:
            raise FieldPackageError("Evidence index references an absent file")
        if item.get("sha256") != entries[path]["sha256"] or item.get("status") != "Included":
            raise FieldPackageError("Evidence index hash/status mismatch")
        indexed.add((path, item["sha256"]))

    def walk(node: Any, member: str):
        if isinstance(node, dict):
            if "file_path" in node:
                path = node["file_path"]
                if path:
                    if not isinstance(path, str) or not path.startswith("../evidence/"):
                        raise FieldPackageError(f"Unsafe evidence link in {member}")
                    # Both JSON files live one level below the archive root.
                    linked = path[3:]
                    if (path != "../" + linked or not _safe_member_name(linked)
                            or linked not in entries or (linked, node.get("sha256")) not in indexed):
                        raise FieldPackageError(f"Unlisted or changed evidence link in {member}")
                    linked_files[member].add(linked)
                elif not isinstance(path, str):
                    raise FieldPackageError(f"Invalid evidence file path in {member}")
            for child in node.values():
                walk(child, member)
        elif isinstance(node, list):
            for child in node:
                walk(child, member)

    linked_files = {_PROJECT_MEMBER: set(), _TWIN_MEMBER: set()}
    walk(native, _PROJECT_MEMBER)
    walk(twin, _TWIN_MEMBER)
    indexed_files = {path for path, _digest in indexed}
    if linked_files[_PROJECT_MEMBER] != indexed_files or linked_files[_TWIN_MEMBER] != indexed_files:
        raise FieldPackageError("Native project, Digital Twin and evidence index disagree")


def restore_field_package(package: str | Path, destination: str | Path) -> Path:
    """Verify then restore to a *new* directory. Return the native project path.

    Rejects modified, incomplete or unsafe packages. Never extracts into an
    existing directory or changes the active application project on failure.
    An unsigned manifest establishes transport integrity, not authorship.
    """
    archive_path = Path(package)
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FieldPackageError(f"Restoration destination already exists: {target}")
    if not target.parent.is_dir():
        raise FieldPackageError(f"Choose an existing destination parent folder: {target.parent}")

    verify_field_package(archive_path)
    stage: Path | None = None
    try:
        with ZipFile(archive_path, "r") as archive:
            names = archive.namelist()
            _validate_restorable_member_names(names)
            manifest = json.loads(archive.read(MANIFEST_NAME))
            _validate_restoration_documents(archive, manifest)
            inventory = {row["path"]: row for row in manifest["files"]}

            stage = Path(tempfile.mkdtemp(prefix=".radverify-restore-", dir=target.parent))
            for name in names:
                # Do not call extractall: write to paths that passed our checks.
                dest_file = stage.joinpath(*name.split("/"))
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                expected = inventory.get(name)
                digest = hashlib.sha256()
                size = 0
                with archive.open(name, "r") as source, dest_file.open("xb") as output:
                    for chunk in iter(lambda: source.read(_CHUNK), b""):
                        size += len(chunk)
                        if expected and size > expected["size"]:
                            raise FieldPackageError(f"ZIP member exceeds declared size: {name}")
                        digest.update(chunk)
                        output.write(chunk)
                if expected and (size != expected["size"] or digest.hexdigest() != expected["sha256"]):
                    raise FieldPackageError(f"File changed during restoration: {name}")

            # Make sure the extracted project is actually readable by RadVerify.
            project_path = stage / _PROJECT_MEMBER
            from radverify.models import RadVerifyProject
            restored = RadVerifyProject.from_dict(json.loads(project_path.read_text(encoding="utf-8")))
            resolve_evidence_paths(restored, project_path.parent)
            for barrier, evidence in _walk_evidence(restored):
                if evidence.file_path and evidence.integrity_status() != "Verified":
                    raise FieldPackageError(f"Restored evidence failed integrity check: {barrier.barrier_id} / {evidence.evidence_id}")

        if target.exists() or target.is_symlink():
            raise FieldPackageError(f"Restoration destination appeared during extraction: {target}")
        stage.rename(target)
        stage = None
        return target / _PROJECT_MEMBER
    except FieldPackageError:
        raise
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        raise FieldPackageError(f"Unable to restore field package: {exc}") from exc
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def default_restore_folder(package: str | Path, parent: str | Path) -> Path:
    """Suggest a new destination folder; never choose an existing one."""
    basename = _safe_filename(Path(package).stem)
    base = Path(parent) / f"{basename}_restored"
    if not base.exists():
        return base
    n = 2
    while (candidate := Path(f"{base}_{n}")).exists():
        n += 1
    return candidate


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check integrity of a RadVerify field-record ZIP")
    parser.add_argument("zip_path", help="Path to a RadVerify field package ZIP")
    parser.add_argument("--restore-to", metavar="NEW_FOLDER", help="Verify and restore into a new (non-existing) folder")
    args = parser.parse_args()
    try:
        if args.restore_to:
            project_path = restore_field_package(args.zip_path, args.restore_to)
            print(f"RESTORED: {project_path} (unsigned integrity check)")
        else:
            result = verify_field_package(args.zip_path)
            print(f"VALID: {result['files']} files, {result['evidence_items']} evidence links (unsigned integrity check)")
    except (FieldPackageError, OSError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
