"""Isolated non-issueable PET report-payload adapter harness.

This module exercises the frozen PET report-readiness boundary without opening
PDF, CSV/JSON, certification, signature, or the normal output pipeline.  It
accepts canonical PET Results rows, copies only the 31 permitted fields, and
returns an in-memory test payload marked permanently non-issueable.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from modalities.pet import PET_SOURCE_TYPE
from services.pet_report_readiness_contract import (
    PET_REPORT_INTEGRATION_OPEN,
    PET_REPORT_PERMITTED_RESULT_FIELDS,
    audit_pet_result_row,
)

PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION = 1
PET_REPORT_PAYLOAD_HARNESS_BASELINE = "pet-report-payload-harness-v1-non-issueable"

PET_REPORT_PAYLOAD_HARNESS_STATUS = (
    "TEST HARNESS ONLY — this PET payload is non-issueable and is not connected "
    "to PDF, CSV/JSON, certification, signature, or the normal output pipeline."
)

# These fields must agree across every barrier row because they identify the
# exact frozen calculation/provenance boundary used for the room result set.
PET_REPORT_PAYLOAD_SHARED_FIELDS: Tuple[str, ...] = (
    "results_model_contract_version",
    "results_source",
    "source_type",
    "provenance_manifest_id",
    "provenance_manifest_revision",
    "radionuclide_dataset_id",
    "radionuclide_dataset_revision",
    "radionuclide_records_sha256",
    "attenuation_dataset_id",
    "attenuation_dataset_revision",
    "attenuation_records_sha256",
    "physics_contract_version",
    "solver_contract_version",
    "replay_verified",
)


class PetReportPayloadHarnessError(ValueError):
    """Raised when canonical PET Results cannot cross the frozen harness boundary."""


def _copy_permitted_row(row: Mapping[str, Any], *, index: int) -> Dict[str, Any]:
    audited = audit_pet_result_row(row)
    missing = list(audited["missing_required_fields"])
    if missing:
        raise PetReportPayloadHarnessError(
            f"PET result row {index} is missing required report-boundary fields: "
            + ", ".join(missing)
        )

    payload = dict(audited["permitted_result_payload"])
    if tuple(payload.keys()) != PET_REPORT_PERMITTED_RESULT_FIELDS:
        raise PetReportPayloadHarnessError(
            f"PET result row {index} did not produce the frozen 31-field ordering."
        )
    if payload.get("results_source") != "persisted_pet_single_source":
        raise PetReportPayloadHarnessError(
            f"PET result row {index} has an unsupported results_source."
        )
    if payload.get("source_type") != PET_SOURCE_TYPE:
        raise PetReportPayloadHarnessError(
            f"PET result row {index} has an unsupported source_type."
        )
    if payload.get("replay_verified") is not True:
        raise PetReportPayloadHarnessError(
            f"PET result row {index} is not deterministic-replay verified."
        )
    return payload


def build_non_issueable_pet_report_payload(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build an in-memory PET report-payload test fixture from canonical rows.

    Only the frozen 31-field allowlist crosses this adapter.  The returned
    object is intentionally unsuitable for issue, export, certification, or
    report generation and is not consumed by any ``reports`` module.
    """
    if PET_REPORT_INTEGRATION_OPEN:
        raise PetReportPayloadHarnessError(
            "The non-issueable PET harness cannot run after report integration is opened."
        )
    if not rows:
        raise PetReportPayloadHarnessError(
            "At least one canonical PET Results row is required."
        )

    barrier_rows = [
        _copy_permitted_row(row, index=index)
        for index, row in enumerate(rows)
    ]

    first = barrier_rows[0]
    for index, row in enumerate(barrier_rows[1:], start=1):
        mismatched = [
            key for key in PET_REPORT_PAYLOAD_SHARED_FIELDS
            if row.get(key) != first.get(key)
        ]
        if mismatched:
            raise PetReportPayloadHarnessError(
                f"PET result row {index} does not share the frozen room provenance: "
                + ", ".join(mismatched)
            )

    barrier_names = [str(row["barrier_name"]) for row in barrier_rows]
    if len(set(barrier_names)) != len(barrier_names):
        raise PetReportPayloadHarnessError(
            "PET result rows must contain unique barrier names."
        )

    shared_provenance = {
        key: first[key]
        for key in PET_REPORT_PAYLOAD_SHARED_FIELDS
    }
    return {
        "harness_contract_version": PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
        "harness_baseline": PET_REPORT_PAYLOAD_HARNESS_BASELINE,
        "status": PET_REPORT_PAYLOAD_HARNESS_STATUS,
        "non_issueable": True,
        "report_integration_open": False,
        "permitted_field_count": len(PET_REPORT_PERMITTED_RESULT_FIELDS),
        "permitted_fields": list(PET_REPORT_PERMITTED_RESULT_FIELDS),
        "shared_provenance": shared_provenance,
        "barrier_count": len(barrier_rows),
        "barriers": barrier_rows,
    }
