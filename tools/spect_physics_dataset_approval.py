"""Verify the SPECT Step 20 approved/frozen physics input set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from engine.spect_radionuclide_data import load_frozen_spect_radionuclide_dataset
from engine.spect_practical_transmission import (
    load_frozen_spect_tc99m_practical_dataset,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "spect" / "spect_physics_approval_manifest.json"


class SpectPhysicsApprovalError(ValueError):
    """Raised when the Step 20 physics freeze cannot be verified."""


def canonical_json_sha256(path: Path) -> str:
    """Hash semantic JSON content independent of CRLF/LF or indentation."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectPhysicsApprovalError(
            f"Unable to read frozen SPECT dataset {path}."
        ) from exc
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectPhysicsApprovalError(f"Unable to read SPECT approval manifest {path}.") from exc
    if not isinstance(payload, dict):
        raise SpectPhysicsApprovalError("SPECT approval manifest root must be an object.")
    if payload.get("schema_version") != 1:
        raise SpectPhysicsApprovalError("Unsupported SPECT approval manifest schema version.")
    if payload.get("status") != "approved_locked_verified_nonproduction":
        raise SpectPhysicsApprovalError("SPECT approval manifest is not in the frozen Step 20 state.")
    if payload.get("production_enabled") is not False:
        raise SpectPhysicsApprovalError("SPECT Step 20 manifest must keep production_enabled=false.")
    if not isinstance(payload.get("datasets"), dict):
        raise SpectPhysicsApprovalError("SPECT approval manifest requires datasets.")
    return payload


def _resolve_dataset_path(entry: dict) -> Path:
    rel = str(entry.get("path") or "").strip()
    if not rel:
        raise SpectPhysicsApprovalError("Dataset manifest entry is missing path.")
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SpectPhysicsApprovalError("Dataset manifest path must stay inside the repository.") from exc
    return path


def verify_manifest(path: str | Path = DEFAULT_MANIFEST) -> str:
    manifest_path = Path(path).resolve()
    payload = _load_manifest(manifest_path)
    datasets = payload["datasets"]

    source_entry = datasets.get("radionuclide_source")
    practical_entry = datasets.get("practical_transmission")
    reference_entry = datasets.get("narrow_beam_reference")
    if not all(isinstance(entry, dict) for entry in (source_entry, practical_entry, reference_entry)):
        raise SpectPhysicsApprovalError("SPECT approval manifest is missing required dataset entries.")

    source_path = _resolve_dataset_path(source_entry)
    practical_path = _resolve_dataset_path(practical_entry)
    reference_path = _resolve_dataset_path(reference_entry)

    source = load_frozen_spect_radionuclide_dataset(source_path)
    practical = load_frozen_spect_tc99m_practical_dataset(practical_path)

    for entry, file_path in ((source_entry, source_path), (practical_entry, practical_path)):
        expected = str(entry.get("canonical_payload_sha256") or "").strip()
        if len(expected) != 64 or canonical_json_sha256(file_path) != expected:
            raise SpectPhysicsApprovalError(
                f"Frozen SPECT dataset canonical payload SHA-256 mismatch: {file_path.name}."
            )

    if source.metadata.records_sha256 != source_entry.get("records_sha256"):
        raise SpectPhysicsApprovalError("Frozen SPECT radionuclide records digest mismatch.")
    if practical.metadata.records_sha256 != practical_entry.get("records_sha256"):
        raise SpectPhysicsApprovalError("Frozen SPECT practical records digest mismatch.")

    if not reference_path.exists():
        raise SpectPhysicsApprovalError("SPECT narrow-beam reference dataset is missing.")
    reference_payload = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_meta = reference_payload.get("metadata", {})
    if reference_meta.get("approval_status") != "development_nonproduction":
        raise SpectPhysicsApprovalError(
            "SPECT narrow-beam attenuation reference must remain non-production reference data."
        )
    if reference_meta.get("records_sha256") != reference_entry.get("records_sha256"):
        raise SpectPhysicsApprovalError("SPECT narrow-beam reference digest mismatch.")

    return "\n".join(
        (
            "SPECT STEP 20 PHYSICS FREEZE",
            "============================",
            f"Freeze ID: {payload['freeze_id']}",
            "Radionuclide source: APPROVED / LOCKED / VERIFIED",
            f"  {source.metadata.dataset_id} @ {source.metadata.revision}",
            f"  records SHA-256: {source.metadata.records_sha256}",
            "Practical transmission: APPROVED / LOCKED / VERIFIED",
            f"  {practical.metadata.dataset_id} @ {practical.metadata.revision}",
            f"  records SHA-256: {practical.metadata.records_sha256}",
            "Narrow-beam attenuation: REFERENCE ONLY / NON-PRODUCTION",
            "SPECT production enabled: NO",
        )
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Step 20 approval manifest to verify.",
    )
    args = parser.parse_args(argv)
    try:
        print(verify_manifest(args.manifest))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
