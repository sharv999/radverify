"""Frozen non-issueable SPECT report section/view-model and wording boundary.

Step 30 derives presentation-ready data only from Step 29 harness payloads. It
renders no document and is disconnected from reports/output/export/certification.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Tuple

from services.spect_report_readiness_contract import SPECT_REPORT_PERMITTED_RESULT_FIELDS
from services.spect_source_summary_report_contract import SPECT_SOURCE_SUMMARY_FIELDS

SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION = 1
SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE = "spect-report-section-view-model-v1-non-issueable"
SPECT_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN = False

SPECT_REPORT_SECTION_HEADINGS: Tuple[Tuple[str, str], ...] = (
    ("section", "SPECT shielding assessment — non-issueable preview"),
    ("source_summary", "Tc-99m source summary"),
    ("barrier_results", "SPECT barrier shielding results"),
    ("provenance", "Calculation provenance"),
)
SPECT_REPORT_SECTION_WARNINGS: Tuple[str, ...] = (
    "NON-ISSUEABLE PREVIEW — not for regulatory, construction, certification or issued-report use.",
    "SPECT PDF/report, machine export and certification integration remain blocked.",
    "Automatic production results exclude any barrier requiring Step 25 engineering review.",
    "Transmitted dose is omitted wherever Step 25 marks the modeled value non-reportable.",
)

SPECT_SOURCE_DISPLAY_FIELDS: Tuple[str, ...] = (
    "radionuclide", "administered_activity_mbq", "patients_per_week", "imaging_duration_h",
    "source_position_x_m", "source_position_y_m",
)
SPECT_SOURCE_DISPLAY_LABELS = {
    "radionuclide": "Radionuclide",
    "administered_activity_mbq": "Administered activity",
    "patients_per_week": "Patients per week",
    "imaging_duration_h": "Imaging duration",
    "source_position_x_m": "Source position from West wall",
    "source_position_y_m": "Source position from South wall",
}
SPECT_SOURCE_DISPLAY_UNITS = {
    "radionuclide": "", "administered_activity_mbq": "MBq", "patients_per_week": "patients/week",
    "imaging_duration_h": "h", "source_position_x_m": "m", "source_position_y_m": "m",
}
SPECT_BARRIER_TABLE_FIELDS: Tuple[str, ...] = (
    "barrier_name", "material", "distance_m", "occupancy_factor", "design_goal_uSv_per_week",
    "unshielded_weekly_dose_uSv", "occupied_unshielded_weekly_dose_uSv", "barrier_transmission_factor_B",
    "required_thickness_mm", "provided_thickness_mm", "margin_mm", "transmitted_dose_uSv_per_week",
    "compliance_status", "calculation_reasoning",
)
SPECT_BARRIER_TABLE_LABELS = {
    "barrier_name": "Barrier", "material": "Material", "distance_m": "Distance",
    "occupancy_factor": "Occupancy factor T", "design_goal_uSv_per_week": "Design goal",
    "unshielded_weekly_dose_uSv": "Unshielded weekly dose",
    "occupied_unshielded_weekly_dose_uSv": "Occupied dose before shielding",
    "barrier_transmission_factor_B": "Required transmission B", "required_thickness_mm": "Required shielding",
    "provided_thickness_mm": "Provided shielding", "margin_mm": "Shielding margin",
    "transmitted_dose_uSv_per_week": "Transmitted weekly dose", "compliance_status": "Assessment status",
    "calculation_reasoning": "Calculation reasoning",
}
SPECT_BARRIER_TABLE_UNITS = {
    "barrier_name": "", "material": "", "distance_m": "m", "occupancy_factor": "",
    "design_goal_uSv_per_week": "µSv/week", "unshielded_weekly_dose_uSv": "µSv/week",
    "occupied_unshielded_weekly_dose_uSv": "µSv/week", "barrier_transmission_factor_B": "",
    "required_thickness_mm": "mm", "provided_thickness_mm": "mm", "margin_mm": "mm",
    "transmitted_dose_uSv_per_week": "µSv/week", "compliance_status": "", "calculation_reasoning": "",
}
SPECT_PROVENANCE_DISPLAY_FIELDS: Tuple[str, ...] = (
    "request_sha256", "freeze_id", "source_dataset", "transmission_dataset", "policy_identity",
)


class SpectReportSectionViewModelError(ValueError):
    pass


def _format(value: Any, *, digits: int = 3) -> str:
    if value is None:
        return "Not reported"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        number = float(value)
        if not isfinite(number):
            raise SpectReportSectionViewModelError("Non-finite value cannot enter the SPECT report view model.")
        return f"{number:.{digits}f}"
    text = str(value)
    if "\n" in text or "\r" in text:
        raise SpectReportSectionViewModelError("Multiline text is not permitted in the frozen SPECT wording boundary.")
    return text


def build_non_issueable_spect_report_section_view_model(
    *, source_payload: Mapping[str, Any], barrier_payload: Mapping[str, Any]
) -> dict[str, Any]:
    if SPECT_REPORT_SECTION_VIEW_MODEL_INTEGRATION_OPEN:
        raise SpectReportSectionViewModelError("SPECT report integration must remain closed.")
    for label, payload in (("source", source_payload), ("barrier", barrier_payload)):
        if payload.get("non_issueable") is not True or payload.get("report_integration_open") is not False:
            raise SpectReportSectionViewModelError(f"SPECT {label} harness is not closed and non-issueable.")
    summary = source_payload.get("source_summary")
    barriers = barrier_payload.get("barriers")
    shared = barrier_payload.get("shared_provenance")
    if not isinstance(summary, Mapping) or tuple(summary) != SPECT_SOURCE_SUMMARY_FIELDS:
        raise SpectReportSectionViewModelError("SPECT source summary does not match the frozen field contract.")
    if not isinstance(barriers, list) or not barriers:
        raise SpectReportSectionViewModelError("SPECT barrier payload must contain rows.")
    for index, row in enumerate(barriers):
        if not isinstance(row, Mapping) or tuple(row) != SPECT_REPORT_PERMITTED_RESULT_FIELDS:
            raise SpectReportSectionViewModelError(f"SPECT barrier row {index} does not match the frozen 30-field contract.")
    if not isinstance(shared, Mapping) or summary["physics_freeze"] != shared.get("physics_freeze"):
        raise SpectReportSectionViewModelError("SPECT source and barrier payloads do not share the same physics freeze.")

    source_rows = [
        {"field": field, "label": SPECT_SOURCE_DISPLAY_LABELS[field], "value": _format(summary[field]), "unit": SPECT_SOURCE_DISPLAY_UNITS[field]}
        for field in SPECT_SOURCE_DISPLAY_FIELDS
    ]
    barrier_rows = []
    for row in barriers:
        display = {}
        for field in SPECT_BARRIER_TABLE_FIELDS:
            digits = 6 if field == "barrier_transmission_factor_B" else 3
            display[field] = _format(row[field], digits=digits)
        barrier_rows.append(display)
    columns = [
        {"field": field, "label": SPECT_BARRIER_TABLE_LABELS[field], "unit": SPECT_BARRIER_TABLE_UNITS[field]}
        for field in SPECT_BARRIER_TABLE_FIELDS
    ]
    freeze = summary["physics_freeze"]
    provenance_values = {
        "request_sha256": shared["request_sha256"],
        "freeze_id": freeze["freeze_id"],
        "source_dataset": f"{freeze['radionuclide_source']['dataset_id']} @ {freeze['radionuclide_source']['revision']}",
        "transmission_dataset": f"{freeze['practical_transmission']['dataset_id']} @ {freeze['practical_transmission']['revision']}",
        "policy_identity": f"Step 25 policy v{shared['policy_version']} — {shared['policy_status']}",
    }
    return {
        "view_model_contract_version": SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
        "view_model_baseline": SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE,
        "non_issueable": True,
        "report_integration_open": False,
        "headings": dict(SPECT_REPORT_SECTION_HEADINGS),
        "warnings": list(SPECT_REPORT_SECTION_WARNINGS),
        "source_summary": {"field_order": list(SPECT_SOURCE_DISPLAY_FIELDS), "rows": source_rows},
        "barrier_table": {"field_order": list(SPECT_BARRIER_TABLE_FIELDS), "columns": columns, "rows": barrier_rows},
        "provenance": {
            "field_order": list(SPECT_PROVENANCE_DISPLAY_FIELDS),
            "rows": [{"field": field, "value": provenance_values[field]} for field in SPECT_PROVENANCE_DISPLAY_FIELDS],
        },
    }
