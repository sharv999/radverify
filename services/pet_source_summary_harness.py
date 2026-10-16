"""Isolated non-issueable PET source-summary harness.

The harness converts validated persisted PET working state into the frozen
source-summary contract. It returns an in-memory object only and is deliberately
not imported by report, export, certification, PDF, CSV, or JSON modules.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Mapping

from engine.pet_calculation_input_provenance import (
    load_pet_calculation_input_provenance_manifest,
)
from modalities.pet import PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
from serialization.pet_working_project_state import get_room_pet_working_state
from services.pet_source_summary_report_contract import (
    PET_EXPOSURE_PERIOD_FIELDS,
    PET_SOURCE_SUMMARY_FIELDS,
    PET_SOURCE_SUMMARY_REPORT_BASELINE,
    PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
    PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN,
    PET_SOURCE_SUMMARY_REPORT_STATUS,
    audit_pet_source_summary,
)

PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION = 1
PET_SOURCE_SUMMARY_HARNESS_BASELINE = "pet-source-summary-harness-v1-non-issueable"


class PetSourceSummaryHarnessError(ValueError):
    """Raised when PET source state cannot cross the frozen source boundary."""


def _finite_positive(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetSourceSummaryHarnessError(f"{field} must be numeric.") from exc
    if not isfinite(number) or number <= 0:
        raise PetSourceSummaryHarnessError(f"{field} must be finite and greater than zero.")
    return number


def _finite_unit_interval(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetSourceSummaryHarnessError(f"{field} must be numeric.") from exc
    if not isfinite(number) or not 0 < number <= 1:
        raise PetSourceSummaryHarnessError(f"{field} must be greater than zero and no greater than 1.")
    return number


def build_non_issueable_pet_source_summary(room: Any) -> Dict[str, Any]:
    """Build the frozen non-issueable source summary for one PET room."""
    if PET_SOURCE_SUMMARY_REPORT_INTEGRATION_OPEN:
        raise PetSourceSummaryHarnessError(
            "The non-issueable PET source-summary harness cannot run after report integration is opened."
        )
    state = get_room_pet_working_state(room)
    if state is None:
        raise PetSourceSummaryHarnessError("Persisted PET working state is required.")

    source = state.source
    position = state.position
    phases = []
    for index, phase in enumerate(source.exposure_phases):
        item = {
            "name": str(phase.name),
            "start_after_administration_h": float(phase.start_time_h),
            "duration_h": _finite_positive(phase.duration_h, f"exposure_periods[{index}].duration_h"),
            "activity_retention_factor": _finite_unit_interval(
                phase.activity_retention_factor, f"exposure_periods[{index}].activity_retention_factor"
            ),
        }
        if tuple(item.keys()) != PET_EXPOSURE_PERIOD_FIELDS:
            raise PetSourceSummaryHarnessError("Exposure-period field ordering drifted.")
        phases.append(item)
    if not phases:
        raise PetSourceSummaryHarnessError("At least one exposure period is required.")

    manifest = load_pet_calculation_input_provenance_manifest(
        PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
    )
    summary = {
        "radionuclide": str(source.radionuclide_spec.code),
        "administered_activity_mbq_per_patient": _finite_positive(
            source.injected_activity_mbq, "administered_activity_mbq_per_patient"
        ),
        "patients_per_week": _finite_positive(source.patients_per_week, "patients_per_week"),
        "activity_scaling_factor": _finite_unit_interval(
            source.residual_activity_factor, "activity_scaling_factor"
        ),
        "exposure_periods": phases,
        "pet_position_west_m": float(position.x_from_west_m),
        "pet_position_south_m": float(position.y_from_south_m),
        "pet_position_height_affl_m": float(position.height_above_ffl_m),
        "provenance_manifest_id": manifest.manifest_id,
        "provenance_manifest_revision": manifest.revision,
        "radionuclide_dataset_id": manifest.radionuclide_dataset.dataset_id,
        "radionuclide_dataset_revision": manifest.radionuclide_dataset.revision,
        "radionuclide_records_sha256": manifest.radionuclide_dataset.records_sha256,
        "attenuation_dataset_id": manifest.attenuation_dataset.dataset_id,
        "attenuation_dataset_revision": manifest.attenuation_dataset.revision,
        "attenuation_records_sha256": manifest.attenuation_dataset.records_sha256,
        "physics_contract_version": manifest.physics_contract_version,
        "solver_contract_version": manifest.solver_contract_version,
    }
    audited = audit_pet_source_summary(summary)
    if audited["missing_required_fields"]:
        raise PetSourceSummaryHarnessError(
            "PET source summary is missing frozen fields: "
            + ", ".join(audited["missing_required_fields"])
        )
    permitted = dict(audited["permitted_source_summary"])
    if tuple(permitted.keys()) != PET_SOURCE_SUMMARY_FIELDS:
        raise PetSourceSummaryHarnessError("PET source-summary field ordering drifted.")

    return {
        "harness_contract_version": PET_SOURCE_SUMMARY_HARNESS_CONTRACT_VERSION,
        "harness_baseline": PET_SOURCE_SUMMARY_HARNESS_BASELINE,
        "source_summary_contract_version": PET_SOURCE_SUMMARY_REPORT_CONTRACT_VERSION,
        "source_summary_baseline": PET_SOURCE_SUMMARY_REPORT_BASELINE,
        "status": PET_SOURCE_SUMMARY_REPORT_STATUS,
        "non_issueable": True,
        "report_integration_open": False,
        "source_summary": permitted,
    }
