"""Common PET/SPECT report-payload adapter for Step 39.

This module is intentionally non-issueable.  It consumes only the frozen
modality source-summary and Results report contracts.  It performs no shielding
calculation and has no dependency on the generic shielding engine, report
builder, PDF generator, export, certification, signature, or app orchestration.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from engine.pet_ultralow_transmission_policy import (
    PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED,
    PET_ULTRALOW_TRANSMISSION_POLICY_STATUS,
    PET_ULTRALOW_TRANSMISSION_POLICY_VERSION,
    assess_pet_production_barrier_policy,
)
from services.pet_report_readiness_contract import (
    PET_REPORT_INTEGRATION_OPEN,
    PET_REPORT_PERMITTED_RESULT_FIELDS,
    audit_pet_result_row,
)
from services.pet_source_summary_report_contract import (
    PET_SOURCE_SUMMARY_FIELDS,
    PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
    audit_pet_source_summary,
)
from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_STATUS,
    SPECT_LOW_TRANSMISSION_POLICY_VERSION,
    SPECT_LOW_TRANSMISSION_REVIEW_STATUS,
)
from services.spect_report_readiness_contract import (
    SPECT_REPORT_INTEGRATION_OPEN,
    SPECT_REPORT_PERMITTED_RESULT_FIELDS,
    audit_spect_result_row,
)
from services.spect_source_summary_report_contract import (
    SPECT_SOURCE_SUMMARY_FIELDS,
    SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
    audit_spect_source_summary,
)

PET_SPECT_REPORT_PAYLOAD_ADAPTER_CONTRACT_VERSION = 1
PET_SPECT_REPORT_PAYLOAD_ADAPTER_BASELINE = "pet-spect-common-report-payload-v1-non-issueable"
PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE = False
PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN = False


class PetSpectReportPayloadAdapterError(ValueError):
    """Raised when canonical PET/SPECT report inputs fail closed."""


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetSpectReportPayloadAdapterError(f"{field} must be a mapping.")
    return value


def _pet_source_summary(source_payload: Mapping[str, Any]) -> dict[str, Any]:
    if PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN:
        raise PetSpectReportPayloadAdapterError("PET source-summary integration must remain closed at Step 39.")
    summary = _mapping(source_payload.get("source_summary"), "PET source_summary")
    audited = audit_pet_source_summary(summary)
    if audited["missing_required_fields"]:
        raise PetSpectReportPayloadAdapterError("PET source summary does not satisfy the frozen contract.")
    permitted = dict(audited["permitted_source_summary"])
    if tuple(permitted) != PET_SOURCE_SUMMARY_FIELDS:
        raise PetSpectReportPayloadAdapterError("PET source-summary field ordering drifted.")
    return permitted


def _spect_source_summary(source_payload: Mapping[str, Any]) -> dict[str, Any]:
    if SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN:
        raise PetSpectReportPayloadAdapterError("SPECT source-summary integration must remain closed at Step 39.")
    summary = _mapping(source_payload.get("source_summary"), "SPECT source_summary")
    audited = audit_spect_source_summary(summary)
    if audited["missing_required_fields"] or audited["unexpected_fields"]:
        raise PetSpectReportPayloadAdapterError("SPECT source summary does not satisfy the frozen contract.")
    permitted = dict(audited["permitted_source_summary"])
    if tuple(permitted) != SPECT_SOURCE_SUMMARY_FIELDS:
        raise PetSpectReportPayloadAdapterError("SPECT source-summary field ordering drifted.")
    return permitted


def _pet_barriers(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if PET_REPORT_INTEGRATION_OPEN:
        raise PetSpectReportPayloadAdapterError("PET report integration must remain closed at Step 39.")
    if not PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED or PET_ULTRALOW_TRANSMISSION_POLICY_STATUS != "approved_locked":
        raise PetSpectReportPayloadAdapterError("PET ultralow-transmission policy is not approved and locked.")
    barriers: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        audited = audit_pet_result_row(row)
        if audited["missing_required_fields"]:
            raise PetSpectReportPayloadAdapterError(f"PET Results row {index} is incomplete.")
        payload = dict(audited["permitted_result_payload"])
        if tuple(payload) != PET_REPORT_PERMITTED_RESULT_FIELDS:
            raise PetSpectReportPayloadAdapterError("PET Results report field ordering drifted.")
        if payload.get("replay_verified") is not True:
            raise PetSpectReportPayloadAdapterError(f"PET Results row {index} is not replay verified.")
        decision = assess_pet_production_barrier_policy(payload)
        if not decision.automatic_assessment_allowed:
            raise PetSpectReportPayloadAdapterError(
                f"PET barrier {decision.barrier_name!r} requires physicist review under the locked ultralow-transmission policy."
            )
        transmitted = (
            payload.get("transmitted_dose_uSv_per_week")
            if decision.production_transmitted_dose_reportable
            else None
        )
        report_payload = dict(payload)
        report_payload["compliance_status"] = decision.status
        report_payload["transmitted_dose_uSv_per_week"] = transmitted
        barriers.append({
            "barrier_name": payload["barrier_name"],
            "assessment_status": decision.status,
            "automatic_assessment_allowed": True,
            "transmitted_dose_reportable": decision.production_transmitted_dose_reportable,
            "transmitted_dose_uSv_per_week": transmitted,
            "decision_basis": decision.decision_basis,
            "policy_version": PET_ULTRALOW_TRANSMISSION_POLICY_VERSION,
            "policy_status": PET_ULTRALOW_TRANSMISSION_POLICY_STATUS,
            "result_payload": report_payload,
        })
    return barriers


def _spect_barriers(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if SPECT_REPORT_INTEGRATION_OPEN:
        raise PetSpectReportPayloadAdapterError("SPECT report integration must remain closed at Step 39.")
    barriers: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        audited = audit_spect_result_row(row)
        if audited["missing_required_fields"] or audited["closed_gate_mismatches"]:
            raise PetSpectReportPayloadAdapterError(f"SPECT Results row {index} is incomplete or output-open.")
        payload = dict(audited["permitted_result_payload"])
        if tuple(payload) != SPECT_REPORT_PERMITTED_RESULT_FIELDS:
            raise PetSpectReportPayloadAdapterError("SPECT Results report field ordering drifted.")
        if payload.get("production_eligible") is not True:
            raise PetSpectReportPayloadAdapterError(f"SPECT Results row {index} is not production eligible.")
        if (
            payload.get("policy_version") != SPECT_LOW_TRANSMISSION_POLICY_VERSION
            or payload.get("policy_status") != SPECT_LOW_TRANSMISSION_POLICY_STATUS
        ):
            raise PetSpectReportPayloadAdapterError(f"SPECT Results row {index} does not carry the locked Step 25 policy identity.")
        if payload.get("compliance_status") == SPECT_LOW_TRANSMISSION_REVIEW_STATUS:
            raise PetSpectReportPayloadAdapterError(f"SPECT Results row {index} requires Step 25 engineering review.")
        reportable = payload.get("transmitted_dose_reportable") is True
        if not reportable and payload.get("transmitted_dose_uSv_per_week") is not None:
            raise PetSpectReportPayloadAdapterError(
                f"SPECT Results row {index} exposes a dose marked non-reportable by Step 25."
            )
        barriers.append({
            "barrier_name": payload["barrier_name"],
            "assessment_status": payload["compliance_status"],
            "automatic_assessment_allowed": True,
            "transmitted_dose_reportable": reportable,
            "transmitted_dose_uSv_per_week": payload.get("transmitted_dose_uSv_per_week") if reportable else None,
            "decision_basis": payload["policy_decision_basis"],
            "policy_version": payload["policy_version"],
            "policy_status": payload["policy_status"],
            "result_payload": payload,
        })
    return barriers


def build_non_issueable_pet_spect_report_payload(
    *,
    modality: str,
    source_payload: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one common, closed report payload from canonical modality Results.

    No fallback calculation is permitted.  Callers must supply the already
    validated in-app Results rows for the room.
    """
    if PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN or PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE:
        raise PetSpectReportPayloadAdapterError("Step 39 common report payload must remain non-issueable.")
    if isinstance(result_rows, (str, bytes)) or not isinstance(result_rows, Sequence) or not result_rows:
        raise PetSpectReportPayloadAdapterError("At least one canonical Results row is required.")

    modality_name = str(modality or "").strip().upper()
    if modality_name == "PET":
        source_summary = _pet_source_summary(source_payload)
        barriers = _pet_barriers(result_rows)
    elif modality_name == "SPECT":
        source_summary = _spect_source_summary(source_payload)
        barriers = _spect_barriers(result_rows)
    else:
        raise PetSpectReportPayloadAdapterError("Step 39 common report payload supports only PET or SPECT.")

    names = [str(row["barrier_name"]) for row in barriers]
    if len(set(names)) != len(names):
        raise PetSpectReportPayloadAdapterError("Common report payload requires unique barrier names.")

    return {
        "adapter_contract_version": PET_SPECT_REPORT_PAYLOAD_ADAPTER_CONTRACT_VERSION,
        "adapter_baseline": PET_SPECT_REPORT_PAYLOAD_ADAPTER_BASELINE,
        "modality": modality_name,
        "non_issueable": True,
        "issueable": False,
        "report_integration_open": False,
        "machine_export_enabled": False,
        "certification_enabled": False,
        "signature_enabled": False,
        "source_summary": source_summary,
        "barrier_count": len(barriers),
        "barriers": barriers,
    }
