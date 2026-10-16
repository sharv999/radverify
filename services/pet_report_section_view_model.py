"""Frozen non-issueable PET report-section view model.

This module derives deterministic, presentation-ready section data solely from
an already validated Step 25 combined PET envelope.  It does not render a
document, write files, or connect PET data to PDF, CSV/JSON, certification,
signature, or the normal output pipeline.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from services.pet_combined_report_payload_harness import (
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE,
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION,
    PET_COMBINED_SHARED_PROVENANCE_FIELDS,
)
from services.pet_report_readiness_contract import PET_REPORT_PERMITTED_RESULT_FIELDS
from services.pet_source_summary_report_contract import (
    PET_EXPOSURE_PERIOD_FIELDS,
    PET_SOURCE_SUMMARY_FIELDS,
)

PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION = 1
PET_REPORT_SECTION_VIEW_MODEL_BASELINE = (
    "pet-report-section-view-model-v1-non-issueable"
)
PET_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN = False

PET_REPORT_SECTION_VIEW_MODEL_STATUS = (
    "VIEW MODEL ONLY — this PET report-section model is non-issueable and is "
    "not connected to PDF, CSV/JSON, certification, signature, or the normal "
    "output pipeline."
)

PET_REPORT_SECTION_HEADINGS: Tuple[Tuple[str, str], ...] = (
    ("section", "PET shielding assessment — non-issueable preview"),
    ("source_summary", "PET source summary"),
    ("exposure_periods", "PET exposure periods"),
    ("barrier_results", "PET barrier shielding results"),
    ("provenance", "Calculation provenance"),
)

PET_REPORT_SECTION_WARNINGS: Tuple[str, ...] = (
    "NON-ISSUEABLE PREVIEW — not for clinical, regulatory, construction or certification use.",
    "PET PDF, CSV/JSON, certification, signature and normal output-pipeline integration remain blocked.",
    "All barrier results are derived from one persisted PET patient/source position per room.",
    "Deterministic replay and shared source/barrier provenance must remain verified.",
)

PET_SOURCE_DISPLAY_FIELDS: Tuple[str, ...] = (
    "radionuclide",
    "administered_activity_mbq_per_patient",
    "patients_per_week",
    "activity_scaling_factor",
    "pet_position_west_m",
    "pet_position_south_m",
    "pet_position_height_affl_m",
)

PET_SOURCE_DISPLAY_LABELS = {
    "radionuclide": "Radionuclide",
    "administered_activity_mbq_per_patient": "Administered activity per patient",
    "patients_per_week": "Patients per week",
    "activity_scaling_factor": "Activity scaling factor",
    "pet_position_west_m": "Source position from West wall",
    "pet_position_south_m": "Source position from South wall",
    "pet_position_height_affl_m": "Source height AFFL",
}

PET_SOURCE_DISPLAY_UNITS = {
    "radionuclide": "",
    "administered_activity_mbq_per_patient": "MBq/patient",
    "patients_per_week": "patients/week",
    "activity_scaling_factor": "",
    "pet_position_west_m": "m",
    "pet_position_south_m": "m",
    "pet_position_height_affl_m": "m AFFL",
}

PET_EXPOSURE_TABLE_FIELDS: Tuple[str, ...] = PET_EXPOSURE_PERIOD_FIELDS
PET_EXPOSURE_TABLE_LABELS = {
    "name": "Exposure period",
    "start_after_administration_h": "Start after administration",
    "duration_h": "Duration",
    "activity_retention_factor": "Activity retention factor",
}
PET_EXPOSURE_TABLE_UNITS = {
    "name": "",
    "start_after_administration_h": "h",
    "duration_h": "h",
    "activity_retention_factor": "",
}

PET_BARRIER_TABLE_FIELDS: Tuple[str, ...] = (
    "barrier_name",
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
    "margin_mm",
    "transmitted_dose_uSv_per_week",
    "compliance_status",
    "calculation_reasoning",
)

PET_BARRIER_TABLE_LABELS = {
    "barrier_name": "Barrier",
    "material": "Material",
    "distance_m": "Distance",
    "occupancy_factor": "Occupancy factor T",
    "design_goal_uSv_per_week": "Design goal",
    "unshielded_weekly_dose_uSv": "Unshielded weekly dose",
    "occupied_unshielded_weekly_dose_uSv": "Occupied dose before shielding",
    "barrier_transmission_factor_B": "Required transmission B",
    "required_tvl_count": "Required attenuation",
    "required_thickness_mm": "Required shielding",
    "provided_thickness_mm": "Provided shielding",
    "margin_mm": "Shielding margin",
    "transmitted_dose_uSv_per_week": "Transmitted weekly dose",
    "compliance_status": "Compliance status",
    "calculation_reasoning": "Calculation reasoning",
}

PET_BARRIER_TABLE_UNITS = {
    "barrier_name": "",
    "material": "",
    "distance_m": "m",
    "occupancy_factor": "",
    "design_goal_uSv_per_week": "µSv/week",
    "unshielded_weekly_dose_uSv": "µSv/week",
    "occupied_unshielded_weekly_dose_uSv": "µSv/week",
    "barrier_transmission_factor_B": "",
    "required_tvl_count": "TVL",
    "required_thickness_mm": "mm",
    "provided_thickness_mm": "mm",
    "margin_mm": "mm",
    "transmitted_dose_uSv_per_week": "µSv/week",
    "compliance_status": "",
    "calculation_reasoning": "",
}

PET_PROVENANCE_DISPLAY_FIELDS: Tuple[str, ...] = (
    *PET_COMBINED_SHARED_PROVENANCE_FIELDS,
    "replay_verified",
)
PET_PROVENANCE_DISPLAY_LABELS = {
    "provenance_manifest_id": "Provenance manifest",
    "provenance_manifest_revision": "Manifest revision",
    "radionuclide_dataset_id": "Radionuclide dataset",
    "radionuclide_dataset_revision": "Radionuclide dataset revision",
    "radionuclide_records_sha256": "Radionuclide records SHA-256",
    "attenuation_dataset_id": "Attenuation dataset",
    "attenuation_dataset_revision": "Attenuation dataset revision",
    "attenuation_records_sha256": "Attenuation records SHA-256",
    "physics_contract_version": "PET physics contract",
    "solver_contract_version": "PET solver contract",
    "replay_verified": "Deterministic replay verified",
}


class PetReportSectionViewModelError(ValueError):
    """Raised when a Step 25 envelope cannot produce the frozen view model."""


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetReportSectionViewModelError(f"{field} must be a mapping.")
    return value


def _sequence(value: object, field: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise PetReportSectionViewModelError(f"{field} must be a list.")
    return value


def _format_number(value: object, decimals: int, field: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PetReportSectionViewModelError(f"{field} must be numeric.") from exc
    if not isfinite(number):
        raise PetReportSectionViewModelError(f"{field} must be finite.")
    return f"{number:.{decimals}f}"


def _format_value(field: str, value: object) -> str:
    if field in {
        "administered_activity_mbq_per_patient",
        "patients_per_week",
        "pet_position_west_m",
        "pet_position_south_m",
        "pet_position_height_affl_m",
        "start_after_administration_h",
        "duration_h",
        "distance_m",
        "design_goal_uSv_per_week",
        "unshielded_weekly_dose_uSv",
        "occupied_unshielded_weekly_dose_uSv",
        "required_tvl_count",
        "required_thickness_mm",
        "provided_thickness_mm",
        "margin_mm",
        "transmitted_dose_uSv_per_week",
    }:
        return _format_number(value, 3, field)
    if field in {"activity_scaling_factor", "activity_retention_factor", "occupancy_factor"}:
        return _format_number(value, 3, field)
    if field == "barrier_transmission_factor_B":
        return _format_number(value, 6, field)
    if field == "replay_verified":
        if value is not True:
            raise PetReportSectionViewModelError(
                "Deterministic replay must be verified before building the view model."
            )
        return "Yes"
    text = str(value or "").strip()
    if not text:
        raise PetReportSectionViewModelError(f"{field} must not be blank.")
    return text


def _columns(fields: Tuple[str, ...], labels: Mapping[str, str], units: Mapping[str, str]) -> List[Dict[str, str]]:
    return [
        {"field": field, "heading": labels[field], "unit": units[field]}
        for field in fields
    ]


def build_non_issueable_pet_report_section_view_model(
    envelope: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build the frozen section view model solely from a Step 25 envelope."""
    if PET_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN:
        raise PetReportSectionViewModelError(
            "The PET section view model cannot run after integration is opened."
        )
    if envelope.get("envelope_contract_version") != PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION:
        raise PetReportSectionViewModelError("Unsupported PET combined-envelope contract version.")
    if envelope.get("envelope_baseline") != PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE:
        raise PetReportSectionViewModelError("Unsupported PET combined-envelope baseline.")
    if envelope.get("non_issueable") is not True or envelope.get("report_integration_open") is not False:
        raise PetReportSectionViewModelError("PET combined envelope is not closed and non-issueable.")
    if envelope.get("replay_verified") is not True:
        raise PetReportSectionViewModelError("PET combined envelope replay is not verified.")

    shared = _mapping(envelope.get("shared_provenance"), "shared_provenance")
    if tuple(shared.keys()) != PET_PROVENANCE_DISPLAY_FIELDS:
        raise PetReportSectionViewModelError("Shared provenance field ordering has drifted.")
    if shared.get("replay_verified") is not True:
        raise PetReportSectionViewModelError("Shared provenance replay is not verified.")

    source_payload = _mapping(envelope.get("source_summary_payload"), "source_summary_payload")
    if source_payload.get("non_issueable") is not True or source_payload.get("report_integration_open") is not False:
        raise PetReportSectionViewModelError("Source-summary child payload is not closed and non-issueable.")
    source = _mapping(source_payload.get("source_summary"), "source_summary")
    if tuple(source.keys()) != PET_SOURCE_SUMMARY_FIELDS:
        raise PetReportSectionViewModelError("Source-summary field ordering has drifted.")

    barrier_payload = _mapping(envelope.get("barrier_payload"), "barrier_payload")
    if barrier_payload.get("non_issueable") is not True or barrier_payload.get("report_integration_open") is not False:
        raise PetReportSectionViewModelError("Barrier child payload is not closed and non-issueable.")
    barriers = _sequence(barrier_payload.get("barriers"), "barriers")
    if not barriers or barrier_payload.get("barrier_count") != len(barriers):
        raise PetReportSectionViewModelError("Barrier rows are empty or barrier_count is inconsistent.")

    source_rows = [
        {
            "field": field,
            "label": PET_SOURCE_DISPLAY_LABELS[field],
            "value": _format_value(field, source[field]),
            "unit": PET_SOURCE_DISPLAY_UNITS[field],
        }
        for field in PET_SOURCE_DISPLAY_FIELDS
    ]

    exposure_rows: List[Dict[str, str]] = []
    periods = _sequence(source.get("exposure_periods"), "source_summary.exposure_periods")
    if not periods:
        raise PetReportSectionViewModelError("At least one exposure period is required.")
    for index, period in enumerate(periods):
        item = _mapping(period, f"exposure_periods[{index}]")
        if tuple(item.keys()) != PET_EXPOSURE_TABLE_FIELDS:
            raise PetReportSectionViewModelError(
                f"Exposure-period row {index} field ordering has drifted."
            )
        exposure_rows.append({field: _format_value(field, item[field]) for field in PET_EXPOSURE_TABLE_FIELDS})

    barrier_rows: List[Dict[str, str]] = []
    for index, row in enumerate(barriers):
        item = _mapping(row, f"barriers[{index}]")
        if tuple(item.keys()) != PET_REPORT_PERMITTED_RESULT_FIELDS:
            raise PetReportSectionViewModelError(
                f"Barrier row {index} does not match the frozen 31-field contract."
            )
        if item.get("replay_verified") is not True:
            raise PetReportSectionViewModelError(
                f"Barrier row {index} replay is not verified."
            )
        barrier_rows.append({field: _format_value(field, item[field]) for field in PET_BARRIER_TABLE_FIELDS})

    provenance_rows = [
        {
            "field": field,
            "label": PET_PROVENANCE_DISPLAY_LABELS[field],
            "value": _format_value(field, shared[field]),
            "unit": "",
        }
        for field in PET_PROVENANCE_DISPLAY_FIELDS
    ]

    return {
        "view_model_contract_version": PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
        "view_model_baseline": PET_REPORT_SECTION_VIEW_MODEL_BASELINE,
        "status": PET_REPORT_SECTION_VIEW_MODEL_STATUS,
        "non_issueable": True,
        "report_integration_open": False,
        "replay_verified": True,
        "headings": dict(PET_REPORT_SECTION_HEADINGS),
        "warnings": list(PET_REPORT_SECTION_WARNINGS),
        "source_summary": {
            "field_order": list(PET_SOURCE_DISPLAY_FIELDS),
            "rows": source_rows,
        },
        "exposure_period_table": {
            "field_order": list(PET_EXPOSURE_TABLE_FIELDS),
            "columns": _columns(PET_EXPOSURE_TABLE_FIELDS, PET_EXPOSURE_TABLE_LABELS, PET_EXPOSURE_TABLE_UNITS),
            "rows": exposure_rows,
        },
        "barrier_table": {
            "field_order": list(PET_BARRIER_TABLE_FIELDS),
            "columns": _columns(PET_BARRIER_TABLE_FIELDS, PET_BARRIER_TABLE_LABELS, PET_BARRIER_TABLE_UNITS),
            "rows": barrier_rows,
        },
        "provenance": {
            "field_order": list(PET_PROVENANCE_DISPLAY_FIELDS),
            "rows": provenance_rows,
        },
    }
