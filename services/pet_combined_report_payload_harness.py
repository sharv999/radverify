"""Combined non-issueable PET report-payload envelope harness.

This module joins the frozen PET source-summary harness payload with the frozen
31-field barrier harness payload.  It verifies common provenance and replay
status, then returns one in-memory envelope that remains disconnected from PDF,
CSV/JSON, certification, signature, and the normal output pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from services.pet_report_payload_harness import (
    PET_REPORT_PAYLOAD_HARNESS_BASELINE,
    PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
)
from services.pet_report_readiness_contract import PET_REPORT_PERMITTED_RESULT_FIELDS
from services.pet_source_summary_harness import (
    PET_SOURCE_SUMMARY_HARNESS_BASELINE,
    PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
)
from services.pet_source_summary_report_contract import PET_SOURCE_SUMMARY_FIELDS

PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION = 1
PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE = (
    "pet-combined-report-payload-envelope-v1-non-issueable"
)
PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_INTEGRATION_OPEN = False

PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_STATUS = (
    "TEST HARNESS ONLY — this combined PET source-and-barrier envelope is "
    "non-issueable and is not connected to PDF, CSV/JSON, certification, "
    "signature, or the normal output pipeline."
)

# Field names shared by the frozen source summary and the barrier payload's
# room-level provenance block.  Every value must match exactly before joining.
PET_COMBINED_SHARED_PROVENANCE_FIELDS: Tuple[str, ...] = (
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
)


class PetCombinedReportPayloadEnvelopeError(ValueError):
    """Raised when frozen PET harness payloads cannot be safely joined."""


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetCombinedReportPayloadEnvelopeError(f"{field} must be a mapping.")
    return value


def _validate_source_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if payload.get("harness_contract_version") != PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET source-summary harness contract version is unsupported."
        )
    if payload.get("harness_baseline") != PET_SOURCE_SUMMARY_HARNESS_BASELINE:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET source-summary harness baseline is unsupported."
        )
    if payload.get("non_issueable") is not True or payload.get("report_integration_open") is not False:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET source-summary payload is not closed and non-issueable."
        )
    summary = _require_mapping(payload.get("source_summary"), "source_summary")
    if tuple(summary.keys()) != PET_SOURCE_SUMMARY_FIELDS:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET source summary does not match the frozen 18-field contract."
        )
    return summary


def _validate_barrier_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if payload.get("harness_contract_version") != PET_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier harness contract version is unsupported."
        )
    if payload.get("harness_baseline") != PET_REPORT_PAYLOAD_HARNESS_BASELINE:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier harness baseline is unsupported."
        )
    if payload.get("non_issueable") is not True or payload.get("report_integration_open") is not False:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload is not closed and non-issueable."
        )
    if payload.get("permitted_field_count") != len(PET_REPORT_PERMITTED_RESULT_FIELDS):
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload does not declare the frozen 31-field count."
        )
    if tuple(payload.get("permitted_fields", ())) != PET_REPORT_PERMITTED_RESULT_FIELDS:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload field allowlist has drifted."
        )
    shared = _require_mapping(payload.get("shared_provenance"), "shared_provenance")
    if shared.get("replay_verified") is not True:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload is not deterministic-replay verified."
        )
    barriers = payload.get("barriers")
    if not isinstance(barriers, list) or not barriers:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload must contain at least one barrier row."
        )
    for index, row in enumerate(barriers):
        row_map = _require_mapping(row, f"barriers[{index}]")
        if tuple(row_map.keys()) != PET_REPORT_PERMITTED_RESULT_FIELDS:
            raise PetCombinedReportPayloadEnvelopeError(
                f"PET barrier row {index} does not match the frozen 31-field contract."
            )
        if row_map.get("replay_verified") is not True:
            raise PetCombinedReportPayloadEnvelopeError(
                f"PET barrier row {index} is not deterministic-replay verified."
            )
    if payload.get("barrier_count") != len(barriers):
        raise PetCombinedReportPayloadEnvelopeError(
            "PET barrier payload barrier_count does not match its rows."
        )
    return shared


def build_non_issueable_pet_combined_report_payload_envelope(
    *,
    source_payload: Mapping[str, Any],
    barrier_payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """Join frozen PET source and barrier payloads into one closed envelope."""
    if PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_INTEGRATION_OPEN:
        raise PetCombinedReportPayloadEnvelopeError(
            "The combined PET envelope harness cannot run after integration is opened."
        )

    source_summary = _validate_source_payload(source_payload)
    barrier_provenance = _validate_barrier_payload(barrier_payload)

    mismatched = [
        field
        for field in PET_COMBINED_SHARED_PROVENANCE_FIELDS
        if source_summary.get(field) != barrier_provenance.get(field)
    ]
    if mismatched:
        raise PetCombinedReportPayloadEnvelopeError(
            "PET source summary and barrier payload do not share frozen provenance: "
            + ", ".join(mismatched)
        )

    shared_provenance = {
        field: source_summary[field]
        for field in PET_COMBINED_SHARED_PROVENANCE_FIELDS
    }
    shared_provenance["replay_verified"] = True

    return {
        "envelope_contract_version": PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION,
        "envelope_baseline": PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE,
        "status": PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_STATUS,
        "non_issueable": True,
        "report_integration_open": False,
        "replay_verified": True,
        "shared_provenance": shared_provenance,
        "source_summary_payload": dict(source_payload),
        "barrier_payload": dict(barrier_payload),
    }
