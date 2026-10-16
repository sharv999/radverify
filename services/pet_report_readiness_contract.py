"""Frozen PET report-readiness boundary.

This module defines the exact canonical in-app PET Results fields that may be
considered by a future report-payload adapter.  It does not open report,
export, certification, PDF, CSV, or JSON generation and must not be imported by
``reports`` modules until that boundary is deliberately opened.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

PET_REPORT_READINESS_CONTRACT_VERSION = 1
PET_REPORT_READINESS_BASELINE = "pet-report-readiness-v1-closed"
PET_REPORT_INTEGRATION_OPEN = False

PET_REPORT_BOUNDARY_STATUS = (
    "AUDIT COMPLETE — canonical PET Results fields are frozen, but report, PDF, "
    "CSV/JSON, certification and issueable-output integration remain blocked."
)

# Exact fields that a future adapter may copy from one canonical PET Results row.
# The order is deliberate and groups identity, calculation inputs/results, then
# provenance.  UI-only wording and material-specific convenience aliases are
# intentionally excluded.
PET_REPORT_PERMITTED_RESULT_FIELDS: Tuple[str, ...] = (
    "results_model_contract_version",
    "results_source",
    "source_type",
    "barrier_name",
    "solver_mode",
    "material",
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
    "unshielded_weekly_dose_uSv",
    "occupied_unshielded_weekly_dose_uSv",
    "barrier_transmission_factor_B",
    "required_tvl_count",
    "required_thickness_mm",
    "provided_thickness_mm",
    "provided_transmission",
    "transmitted_dose_uSv_per_week",
    "margin_mm",
    "compliance_status",
    "calculation_reasoning",
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

# Every permitted field is required for the first report adapter.  This avoids
# silently producing a partial or weakly-provenanced PET schedule.
PET_REPORT_REQUIRED_RESULT_FIELDS = PET_REPORT_PERMITTED_RESULT_FIELDS

# These current Results fields are explicitly presentation-only, redundant, or
# unsuitable for direct report transfer.
PET_REPORT_FORBIDDEN_RESULT_FIELDS: Tuple[str, ...] = (
    "results_presentation_contract_version",
    "results_presentation_baseline",
    "required_lead_mm",
    "required_concrete_mm",
    "source_contributions",
    "dominant_source",
    "notes",
)

# These source-level facts are not present in a barrier Results row and must be
# supplied by a separate, validated PET source-summary adapter in a later step.
PET_REPORT_SOURCE_FIELDS_REQUIRING_SEPARATE_ADAPTER: Tuple[str, ...] = (
    "radionuclide",
    "administered_activity_mbq_per_patient",
    "patients_per_week",
    "activity_scaling_factor",
    "exposure_periods",
    "pet_position_west_m",
    "pet_position_south_m",
    "pet_position_height_affl_m",
)


def audit_pet_result_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Audit one canonical PET Results row without creating report content."""
    keys = set(row.keys())
    missing = [key for key in PET_REPORT_REQUIRED_RESULT_FIELDS if key not in keys]
    forbidden_present = [key for key in PET_REPORT_FORBIDDEN_RESULT_FIELDS if key in keys]
    permitted = {
        key: row[key]
        for key in PET_REPORT_PERMITTED_RESULT_FIELDS
        if key in row
    }
    return {
        "contract_version": PET_REPORT_READINESS_CONTRACT_VERSION,
        "baseline": PET_REPORT_READINESS_BASELINE,
        "report_integration_open": PET_REPORT_INTEGRATION_OPEN,
        "ready_for_future_adapter": not missing,
        "missing_required_fields": missing,
        "presentation_only_fields_present": forbidden_present,
        "permitted_result_payload": permitted,
    }
