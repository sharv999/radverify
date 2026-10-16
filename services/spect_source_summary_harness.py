"""Non-issueable SPECT source-summary harness.

The harness reads only validated Step 23 working state plus saved room geometry.
It does not write files or connect to report/output/certification code.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

from serialization.spect_working_project_state import get_room_spect_working_state
from services.spect_source_summary_report_contract import (
    SPECT_SOURCE_SUMMARY_FIELDS,
    SPECT_SOURCE_SUMMARY_REPORT_BASELINE,
    SPECT_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
    SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
    audit_spect_source_summary,
)

SPECT_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION = 1
SPECT_SOURCE_SUMMARY_HARNESS_BASELINE = "spect-source-summary-harness-v1-non-issueable"


class SpectSourceSummaryHarnessError(ValueError):
    pass


def _finite(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectSourceSummaryHarnessError(f"{field} must be numeric.") from exc
    if not isfinite(number):
        raise SpectSourceSummaryHarnessError(f"{field} must be finite.")
    return number


def build_non_issueable_spect_source_summary(room: Any) -> dict[str, Any]:
    if SPECT_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN:
        raise SpectSourceSummaryHarnessError("SPECT source-summary report integration must remain closed.")
    state = get_room_spect_working_state(room)
    if state is None:
        raise SpectSourceSummaryHarnessError("Persisted Step 23 SPECT working state is required.")
    geometry = getattr(room, "geometry", None)
    if geometry is None or getattr(geometry, "source", None) is None:
        raise SpectSourceSummaryHarnessError("Saved room geometry/source position is required.")
    width = _finite(getattr(geometry, "width_m", None), "room width")
    length = _finite(getattr(geometry, "length_m", None), "room length")
    x = _finite(getattr(geometry.source, "x_m", None), "source_position_x_m")
    y = _finite(getattr(geometry.source, "y_m", None), "source_position_y_m")
    if width <= 0 or length <= 0 or not (0 <= x <= width) or not (0 <= y <= length):
        raise SpectSourceSummaryHarnessError("Saved SPECT source position must lie within the room geometry.")
    source = state.source
    summary = {
        "radionuclide": str(source.radionuclide_spec.code),
        "administered_activity_mbq": float(source.administered_activity_mbq),
        "patients_per_week": float(source.patients_per_week),
        "imaging_duration_h": float(source.imaging_duration_h),
        "source_position_x_m": x,
        "source_position_y_m": y,
        "physics_freeze": dict(state.physics_freeze),
    }
    audited = audit_spect_source_summary(summary)
    if audited["missing_required_fields"] or audited["unexpected_fields"]:
        raise SpectSourceSummaryHarnessError("SPECT source-summary contract drift detected.")
    permitted = dict(audited["permitted_source_summary"])
    if tuple(permitted) != SPECT_SOURCE_SUMMARY_FIELDS:
        raise SpectSourceSummaryHarnessError("SPECT source-summary field ordering drifted.")
    return {
        "harness_contract_version": SPECT_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
        "harness_baseline": SPECT_SOURCE_SUMMARY_HARNESS_BASELINE,
        "source_summary_contract_version": SPECT_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
        "source_summary_baseline": SPECT_SOURCE_SUMMARY_REPORT_BASELINE,
        "non_issueable": True,
        "report_integration_open": False,
        "source_summary": permitted,
    }
