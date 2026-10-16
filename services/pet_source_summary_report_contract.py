"""Frozen PET source-summary report boundary.

This module defines the exact source-level facts that a future PET report
adapter may consume. It does not open PDF, CSV/JSON, certification, signature,
or the normal output pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION = 2
PET_SOURCE_SUMMARY_REPORT_BASELINE = "pet-source-summary-report-v2-activity-retention-closed"
PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN = False

PET_SOURCE_SUMMARY_REPORT_STATUS = (
    "SOURCE-SUMMARY CONTRACT ONLY — PET PDF, CSV/JSON, certification, signature "
    "and normal output-pipeline integration remain blocked."
)

PET_SOURCE_SUMMARY_FIELDS: Tuple[str, ...] = (
    "radionuclide",
    "administered_activity_mbq_per_patient",
    "patients_per_week",
    "activity_scaling_factor",
    "exposure_periods",
    "pet_position_west_m",
    "pet_position_south_m",
    "pet_position_height_affl_m",
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

PET_SOURCE_SUMMARY_REQUIRED_FIELDS = PET_SOURCE_SUMMARY_FIELDS

PET_EXPOSURE_PERIOD_FIELDS: Tuple[str, ...] = (
    "name",
    "start_after_administration_h",
    "duration_h",
    "activity_retention_factor",
)


def audit_pet_source_summary(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Audit a source-summary mapping without creating issueable content."""
    missing = [key for key in PET_SOURCE_SUMMARY_REQUIRED_FIELDS if key not in payload]
    permitted = {
        key: payload[key]
        for key in PET_SOURCE_SUMMARY_FIELDS
        if key in payload
    }
    return {
        "contract_version": PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
        "baseline": PET_SOURCE_SUMMARY_REPORT_BASELINE,
        "report_integration_open": PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
        "ready_for_non_issueable_harness": not missing,
        "missing_required_fields": missing,
        "permitted_source_summary": permitted,
    }
