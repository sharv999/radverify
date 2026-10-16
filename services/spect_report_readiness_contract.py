"""Frozen SPECT Step 28 report-readiness boundary.

This module defines which fields from the Step 27 in-app SPECT production
Results model may be considered by a future report-payload adapter.  It does
not open PDF/report generation, machine-readable export, certification, or any
issueable-output path, and must not be imported by ``reports`` modules until a
later deliberate integration step.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

SPECT_REPORT_READINESS_CONTRACT_VERSION = 1
SPECT_REPORT_READINESS_BASELINE = "spect-report-readiness-v1-closed"
SPECT_REPORT_INTEGRATION_OPEN = False

SPECT_REPORT_BOUNDARY_STATUS = (
    "AUDIT COMPLETE — canonical SPECT Results fields are frozen for a future "
    "report adapter, but PDF/report, export and certification integration remain blocked."
)

# Exact Step 27 Results fields that a future SPECT report adapter may consume.
# The order is deliberate: identity, calculation values, policy/provenance.
SPECT_REPORT_PERMITTED_RESULT_FIELDS: Tuple[str, ...] = (
    "results_model_contract_version",
    "results_source",
    "source_type",
    "barrier_name",
    "barrier_id",
    "solver_mode",
    "material",
    "material_key",
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
    "unshielded_weekly_dose_uSv",
    "occupied_unshielded_weekly_dose_uSv",
    "barrier_transmission_factor_B",
    "required_thickness_mm",
    "provided_thickness_mm",
    "provided_transmission",
    "transmitted_dose_uSv_per_week",
    "transmitted_dose_reportable",
    "compliance_status",
    "margin_mm",
    "calculation_reasoning",
    "production_eligible",
    "request_sha256",
    "physics_freeze",
    "policy_version",
    "policy_status",
    "policy_decision_basis",
    "practical_record_id",
    "practical_provenance",
)

# The first report adapter must fail closed if any permitted field is missing.
SPECT_REPORT_REQUIRED_RESULT_FIELDS = SPECT_REPORT_PERMITTED_RESULT_FIELDS

# Current Step 27 fields that are presentation-only, redundant convenience
# aliases, or explicit closed-output controls.  They must never be copied into
# report content as if they were canonical report data.
SPECT_REPORT_FORBIDDEN_RESULT_FIELDS: Tuple[str, ...] = (
    "results_presentation_contract_version",
    "results_presentation_baseline",
    "required_lead_mm",
    "required_concrete_mm",
    "source_contributions",
    "dominant_source",
    "notes",
    "output_eligible",
    "report_integration_enabled",
    "certification_enabled",
)

# These facts are required for a useful SPECT source narrative but are not
# carried by a barrier Results row.  A later source-summary adapter must obtain
# them from validated Step 23 working state / normal room geometry rather than
# infer them from UI text or barrier calculations.
SPECT_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER: Tuple[str, ...] = (
    "radionuclide",
    "administered_activity_mbq",
    "patients_per_week",
    "imaging_duration_h",
    "source_position_x_m",
    "source_position_y_m",
)

# Closed-output controls that must remain false at Step 28.  They are checked
# during the audit but are not transferred into report content.
SPECT_REPORT_CLOSED_GATE_FIELDS = {
    "output_eligible": False,
    "report_integration_enabled": False,
    "certification_enabled": False,
}


def audit_spect_result_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Audit one canonical Step 27 SPECT Results row without creating a report."""
    keys = set(row.keys())
    missing = [key for key in SPECT_REPORT_REQUIRED_RESULT_FIELDS if key not in keys]
    forbidden_present = [key for key in SPECT_REPORT_FORBIDDEN_RESULT_FIELDS if key in keys]
    closed_gate_mismatches = [
        key
        for key, expected in SPECT_REPORT_CLOSED_GATE_FIELDS.items()
        if row.get(key) is not expected
    ]
    permitted = {
        key: row[key]
        for key in SPECT_REPORT_PERMITTED_RESULT_FIELDS
        if key in row
    }
    return {
        "contract_version": SPECT_REPORT_READINESS_CONTRACT_VERSION,
        "baseline": SPECT_REPORT_READINESS_BASELINE,
        "report_integration_open": SPECT_REPORT_INTEGRATION_OPEN,
        "ready_for_future_adapter": not missing and not closed_gate_mismatches,
        "missing_required_fields": missing,
        "presentation_or_gate_fields_present": forbidden_present,
        "closed_gate_mismatches": closed_gate_mismatches,
        "permitted_result_payload": permitted,
    }
