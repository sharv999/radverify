"""Non-issueable SPECT barrier report-payload harness for Step 29."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple

from services.spect_report_readiness_contract import (
    SPECT_REPORT_INTEGRATION_OPEN,
    SPECT_REPORT_PERMITTED_RESULT_FIELDS,
    audit_spect_result_row,
)

SPECT_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION = 1
SPECT_REPORT_PAYLOAD_HARNESS_BASELINE = "spect-report-payload-harness-v1-non-issueable"
SPECT_REPORT_PAYLOAD_SHARED_FIELDS: Tuple[str, ...] = (
    "results_model_contract_version",
    "results_source",
    "source_type",
    "request_sha256",
    "physics_freeze",
    "policy_version",
    "policy_status",
)


class SpectReportPayloadHarnessError(ValueError):
    pass


def build_non_issueable_spect_report_payload(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if SPECT_REPORT_INTEGRATION_OPEN:
        raise SpectReportPayloadHarnessError("SPECT report integration must remain closed.")
    if not rows:
        raise SpectReportPayloadHarnessError("At least one SPECT Results row is required.")
    copied = []
    for index, row in enumerate(rows):
        audited = audit_spect_result_row(row)
        missing = audited["missing_required_fields"]
        if missing:
            raise SpectReportPayloadHarnessError(
                f"SPECT result row {index} is missing required fields: " + ", ".join(missing)
            )
        payload = dict(audited["permitted_result_payload"])
        if tuple(payload) != SPECT_REPORT_PERMITTED_RESULT_FIELDS:
            raise SpectReportPayloadHarnessError("Frozen SPECT report field ordering drifted.")
        if payload["results_source"] != "spect_step26_production_dispatch" or payload["source_type"] != "spect_patient":
            raise SpectReportPayloadHarnessError(f"SPECT result row {index} has unsupported provenance identity.")
        if payload["transmitted_dose_reportable"] is False and payload["transmitted_dose_uSv_per_week"] is not None:
            raise SpectReportPayloadHarnessError(
                f"SPECT result row {index} exposes a transmitted dose that Step 25 marked non-reportable."
            )
        copied.append(payload)
    first = copied[0]
    for index, row in enumerate(copied[1:], 1):
        mismatch = [key for key in SPECT_REPORT_PAYLOAD_SHARED_FIELDS if row.get(key) != first.get(key)]
        if mismatch:
            raise SpectReportPayloadHarnessError(
                f"SPECT result row {index} does not share frozen room provenance: " + ", ".join(mismatch)
            )
    ids = [str(row["barrier_id"]) for row in copied]
    names = [str(row["barrier_name"]) for row in copied]
    if len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise SpectReportPayloadHarnessError("SPECT report rows require unique barrier IDs and names.")
    shared = {key: first[key] for key in SPECT_REPORT_PAYLOAD_SHARED_FIELDS}
    return {
        "harness_contract_version": SPECT_REPORT_PAYLOAD_HARNESS_CONTRACT_VERSION,
        "harness_baseline": SPECT_REPORT_PAYLOAD_HARNESS_BASELINE,
        "non_issueable": True,
        "report_integration_open": False,
        "permitted_field_count": len(SPECT_REPORT_PERMITTED_RESULT_FIELDS),
        "permitted_fields": list(SPECT_REPORT_PERMITTED_RESULT_FIELDS),
        "shared_provenance": shared,
        "barrier_count": len(copied),
        "barriers": copied,
    }
