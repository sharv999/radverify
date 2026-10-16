"""Frozen non-issueable SPECT source-summary report boundary for Steps 29-30."""
from __future__ import annotations

from typing import Any, Mapping, Tuple

SPECT_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION = 1
SPECT_SOURCE_SUMMARY_REPORT_BASELINE = "spect-source-summary-v1-non-issueable"
SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN = False

SPECT_SOURCE_SUMMARY_FIELDS: Tuple[str, ...] = (
    "radionuclide",
    "administered_activity_mbq",
    "patients_per_week",
    "imaging_duration_h",
    "source_position_x_m",
    "source_position_y_m",
    "physics_freeze",
)


def audit_spect_source_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in SPECT_SOURCE_SUMMARY_FIELDS if key not in summary]
    extra = [key for key in summary if key not in SPECT_SOURCE_SUMMARY_FIELDS]
    permitted = {key: summary[key] for key in SPECT_SOURCE_SUMMARY_FIELDS if key in summary}
    return {
        "contract_version": SPECT_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
        "baseline": SPECT_SOURCE_SUMMARY_REPORT_BASELINE,
        "report_integration_open": SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
        "missing_required_fields": missing,
        "unexpected_fields": extra,
        "permitted_source_summary": permitted,
    }
