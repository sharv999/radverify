"""Review and explicitly approve material attenuation datasets.

Run from the project root:

    python -m tools.attenuation_dataset_approval review <dataset.json>

After reviewing the printed records, approve to a separate output file:

    python -m tools.attenuation_dataset_approval approve <dataset.json> \
        --approved-by "Name" \
        --approved-date 2026-07-19 \
        --confirm "APPROVE:<dataset_id>:<revision>" \
        --output <approved-dataset.json>

This utility is intentionally not imported by application, modality, solver, or
report code. Approval changes metadata only; it does not alter attenuation
records or wire the dataset into production use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from engine.material_attenuation_data import (
    APPROVAL_STATUS_PRODUCTION_APPROVED,
    APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL,
    LoadedMaterialAttenuationDataset,
    MaterialAttenuationDataError,
    load_material_attenuation_dataset,
)


class DatasetApprovalError(ValueError):
    """Raised when the explicit dataset approval workflow is not satisfied."""


def _canonical_records_bytes(payload: dict[str, Any]) -> bytes:
    records = payload.get("records")
    return json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def records_sha256(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest of the dataset records only."""

    return hashlib.sha256(_canonical_records_bytes(payload)).hexdigest()


def expected_confirmation_token(dataset: LoadedMaterialAttenuationDataset) -> str:
    """Return the exact token required to approve this dataset revision."""

    return f"APPROVE:{dataset.metadata.dataset_id}:{dataset.metadata.revision}"


def _read_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetApprovalError(f"Unable to read dataset {path}.") from exc
    except json.JSONDecodeError as exc:
        raise DatasetApprovalError(f"Dataset {path} is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise DatasetApprovalError("Dataset root must be a JSON object.")
    return payload


def _validate_iso_date(value: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise DatasetApprovalError("approved_date must use YYYY-MM-DD format.") from exc
    return parsed.isoformat()


def render_dataset_review(path: str | Path) -> str:
    """Validate an unapproved/approved dataset and render its audit summary."""

    source_path = Path(path)
    dataset = load_material_attenuation_dataset(source_path, allow_unapproved=True)
    payload = _read_payload(source_path)
    digest = records_sha256(payload)
    metadata = dataset.metadata

    lines = [
        "MATERIAL ATTENUATION DATASET REVIEW",
        "=" * 39,
        f"Source path: {dataset.source_path}",
        f"Dataset ID: {metadata.dataset_id}",
        f"Revision: {metadata.revision}",
        f"Description: {metadata.description}",
        f"Approval status: {metadata.approval_status}",
        f"Reviewed by: {metadata.reviewed_by}",
        f"Reviewed date: {metadata.reviewed_date}",
        f"Approved by: {metadata.approved_by or '[not approved]'}",
        f"Approved date: {metadata.approved_date or '[not approved]'}",
        f"Records SHA-256: {digest}",
        f"Record count: {len(dataset.library.records)}",
        "",
        "RECORDS",
        "-------",
    ]

    for index, record in enumerate(dataset.library.records, start=1):
        radionuclides = ", ".join(record.radionuclides) or "[none specified]"
        lines.extend(
            [
                f"[{index}] {record.record_id}",
                f"  Lookup: {record.tvl_key} / {record.material_key}",
                f"  Radiation: {record.radiation_type}",
                f"  Energy: {record.nominal_energy_kev:g} keV"
                if record.nominal_energy_kev is not None
                else "  Energy: [not specified]",
                f"  Radionuclides: {radionuclides}",
                f"  TVL1: {record.tvl1_mm:g} mm",
                f"  TVLe: {record.tvle_mm:g} mm",
                f"  Provenance: {record.provenance.summary}",
                f"  Notes: {record.provenance.notes or '[none]'}",
                "",
            ]
        )

    if metadata.approval_status == APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL:
        lines.extend(
            [
                "PENDING APPROVAL",
                "----------------",
                "This dataset remains blocked from production loading.",
                "After independently verifying every record above, use the approve command.",
                f"Required confirmation token: {expected_confirmation_token(dataset)}",
            ]
        )
    else:
        lines.extend(
            [
                "PRODUCTION APPROVAL",
                "-------------------",
                "This dataset metadata is marked production_approved.",
            ]
        )

    return "\n".join(lines)


def approve_dataset(
    source: str | Path,
    output: str | Path,
    *,
    approved_by: str,
    approved_date: str,
    confirmation: str,
    overwrite: bool = False,
) -> Path:
    """Create a separately written production-approved dataset.

    The source must be pending approval. The exact confirmation token binds the
    approval action to the dataset ID and revision printed during review.
    Attenuation records are preserved byte-for-byte at the JSON-data level and
    verified by a canonical SHA-256 digest before and after metadata mutation.
    """

    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    if source_path == output_path:
        raise DatasetApprovalError(
            "Approval output must be a separate file; the pending source is never overwritten."
        )
    if output_path.exists() and not overwrite:
        raise DatasetApprovalError(
            f"Approval output already exists: {output_path}. Use --overwrite explicitly to replace it."
        )

    dataset = load_material_attenuation_dataset(source_path, allow_unapproved=True)
    metadata = dataset.metadata
    if metadata.approval_status != APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL:
        raise DatasetApprovalError(
            "Only reviewed_pending_user_approval datasets can enter this approval workflow."
        )

    approver = str(approved_by or "").strip()
    if not approver:
        raise DatasetApprovalError("approved_by must not be blank.")
    approval_date = _validate_iso_date(approved_date)

    required_token = expected_confirmation_token(dataset)
    if str(confirmation or "") != required_token:
        raise DatasetApprovalError(
            "Explicit confirmation did not match this dataset ID and revision. "
            f"Required token: {required_token}"
        )

    payload = _read_payload(source_path)
    before_digest = records_sha256(payload)
    metadata_mapping = payload.get("metadata")
    if not isinstance(metadata_mapping, dict):
        raise DatasetApprovalError("Dataset metadata must be a JSON object.")

    metadata_mapping["approval_status"] = APPROVAL_STATUS_PRODUCTION_APPROVED
    metadata_mapping["approved_by"] = approver
    metadata_mapping["approved_date"] = approval_date
    metadata_mapping["approved_records_sha256"] = before_digest

    after_digest = records_sha256(payload)
    if after_digest != before_digest:
        raise DatasetApprovalError("Attenuation records changed during approval; output was not written.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_name, output_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise

    # Fail closed if the newly written file does not satisfy the ordinary
    # production loader contract.
    approved = load_material_attenuation_dataset(output_path)
    if approved.metadata.approval_status != APPROVAL_STATUS_PRODUCTION_APPROVED:
        raise DatasetApprovalError("Approved output failed production-status validation.")

    approved_payload = _read_payload(output_path)
    if records_sha256(approved_payload) != before_digest:
        raise DatasetApprovalError("Approved output record digest does not match the reviewed source.")

    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review and explicitly approve material attenuation datasets."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Validate and print the full review summary.")
    review.add_argument("dataset", type=Path)

    approve = subparsers.add_parser(
        "approve", help="Create a separately written production-approved dataset."
    )
    approve.add_argument("dataset", type=Path)
    approve.add_argument("--output", type=Path, required=True)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--approved-date", required=True, help="Approval date in YYYY-MM-DD format.")
    approve.add_argument("--confirm", required=True, help="Exact token printed by the review command.")
    approve.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace an existing output file; never overwrites the pending source.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "review":
            print(render_dataset_review(args.dataset))
            return 0

        output = approve_dataset(
            args.dataset,
            args.output,
            approved_by=args.approved_by,
            approved_date=args.approved_date,
            confirmation=args.confirm,
            overwrite=args.overwrite,
        )
        print(f"Production-approved dataset written to: {output}")
        print(render_dataset_review(output))
        return 0
    except (DatasetApprovalError, MaterialAttenuationDataError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
