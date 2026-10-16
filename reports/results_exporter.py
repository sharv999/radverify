from __future__ import annotations

"""
Machine-readable results export helpers.

These exports are generated from the same report payload used to build the PDF.
They are intended for:

    - client/project output records
    - known-answer regression tests
    - physics-engine drift detection
    - debugging report/UI inconsistencies

Do not scrape Tkinter tables or PDFs. The payload supplied here should already
come from the model/engine/report pathway.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


def write_results_exports_from_payload(
    payload: Dict[str, Any],
    pdf_output_path: str | Path,
    *,
    include_csv: bool = True,
) -> Dict[str, Path]:
    """
    Write the client-facing barrier-results sidecars beside a generated PDF.

    The canonical barrier-results JSON is produced for every eligible modality.
    Only the canonical barrier-results JSON is written. The include_csv
    argument is retained for call-site compatibility but CSV sidecars are no
    longer generated. Auxiliary source-readiness and compact-payload JSON files
    are also not written.

    Example for Example_Shielding_Assessment.pdf:

        Example_Shielding_Assessment_barrier_results.json
    """
    pdf_output_path = Path(pdf_output_path)
    output_dir = pdf_output_path.parent
    stem = pdf_output_path.stem

    output_dir.mkdir(parents=True, exist_ok=True)

    barrier_results = build_barrier_results_export(payload)

    barrier_json = output_dir / f"{stem}_barrier_results.json"

    _write_json(barrier_json, barrier_results)
    return {"barrier_results_json": barrier_json}


def build_compact_results_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "export_version": 1,
        "generated_on": _generated_on(payload),
        "project": payload.get("project", {}) or {},
        "summary": payload.get("summary", {}) or {},
        "source_readiness": build_source_readiness_export(payload),
        "barrier_results": build_barrier_results_export(payload),
    }


def build_source_readiness_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    canonical = payload.get("source_readiness", {}) or {}
    project = payload.get("project", {}) or {}
    rows: List[Dict[str, Any]] = []

    for row in payload.get("source_ksec_rows", []) or []:
        rows.append({
            "room_name": row.get("room_name", ""),
            "room_modality": row.get("room_modality", ""),
            "source_name": row.get("source_name", ""),
            "source_type": row.get("source_type", ""),
            "scanner_vendor": row.get("scanner_vendor", ""),
            "scanner_model": row.get("scanner_model", ""),
            "scanner_family": row.get("scanner_family", ""),
            "scanner_phantom": row.get("scanner_phantom", ""),
            "scanner_kvp": row.get("scanner_kvp", ""),
            "ksec_mGy_per_100mAs_at_1m": row.get("ksec"),
            "ksec_display": row.get("ksec_display", ""),
            "basis": row.get("basis", ""),
            "basis_label": row.get("basis_label", ""),
            "status": row.get("status", ""),
            "severity": row.get("severity", ""),
            "source_text": row.get("source_text", ""),
            "limitation": row.get("limitation", ""),
            "audit_complete": row.get("audit_complete", ""),
            "manual_override": row.get("manual_override", ""),
            "manual_ksec_entered_by": row.get("manual_ksec_entered_by", ""),
            "manual_ksec_reason": row.get("manual_ksec_reason", ""),
            "manual_ksec_source_reference": row.get("manual_ksec_source_reference", ""),
            "manual_ksec_last_updated": row.get("manual_ksec_last_updated", ""),
            "manual_ksec_audit_text": row.get("manual_ksec_audit_text", ""),
        })

    return {
        "export_version": 1,
        "generated_on": _generated_on(payload),
        "project_name": project.get("project_name", ""),
        "global_energy": project.get("global_energy", ""),
        "solver_mode": project.get("solver_mode", ""),
        "overall_status": canonical.get("overall_status", ""),
        "blocking": canonical.get("blocking", False),
        "errors": canonical.get("errors", []) or [],
        "warnings": canonical.get("warnings", []) or [],
        "room_results": canonical.get("room_results", []) or [],
        "source_results": canonical.get("source_results", []) or [],
        "summary": {
            "database_count": payload.get("summary", {}).get("source_ksec_database_count", 0),
            "manual_override_count": payload.get("summary", {}).get("source_ksec_manual_override_count", 0),
            "incomplete_count": payload.get("summary", {}).get("source_ksec_incomplete_count", 0),
        },
        "rows": rows,
    }


def build_barrier_results_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    project = payload.get("project", {}) or {}
    rows: List[Dict[str, Any]] = []

    for room in payload.get("rooms", []) or []:
        for barrier in room.get("barriers", []) or []:
            rows.append(_barrier_row_for_export(room, barrier))

    return {
        "export_version": 1,
        "generated_on": _generated_on(payload),
        "project_name": project.get("project_name", ""),
        "global_energy": project.get("global_energy", ""),
        "solver_mode": project.get("solver_mode", ""),
        "summary": payload.get("summary", {}) or {},
        "rows": rows,
    }


def _barrier_row_for_export(room: Dict[str, Any], barrier: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "room_name": room.get("name", ""),
        "room_modality": room.get("modality", ""),
        "room_classification": room.get("classification", ""),
        "barrier": barrier.get("name", ""),
        "barrier_element_type": barrier.get("barrier_element_type", ""),
        "parent_barrier": barrier.get("parent_barrier", ""),
        "adjacent_area": barrier.get("adjacent_area", ""),
        "barrier_role": barrier.get("barrier_role", ""),
        "material": barrier.get("material", ""),
        "provided_thickness_mm": barrier.get("provided_thickness_mm"),
        "required_lead_mm": barrier.get("required_lead_mm"),
        "required_concrete_mm": barrier.get("required_concrete_mm"),
        "required_thickness_mm": barrier.get("required_thickness_mm"),
        "recommended_commercial_lead_mm": barrier.get("recommended_commercial_lead_mm"),
        "margin_mm": barrier.get("margin_mm"),
        "unshielded_weekly_dose_uSv": barrier.get("unshielded_weekly_dose_uSv"),
        "barrier_transmission_factor_B": barrier.get("barrier_transmission_factor_B"),
        "transmitted_dose_uSv_per_week": barrier.get("transmitted_dose_uSv_per_week"),
        "distance_m": barrier.get("distance_m"),
        "occupancy_factor": barrier.get("occupancy_factor"),
        "design_goal_uSv_per_week": barrier.get("design_goal_uSv_per_week"),
        "status": barrier.get("status", ""),
        "status_text": barrier.get("status_text", ""),
        "risk_visual_state": barrier.get("risk_visual_state", ""),
        "risk_confidence": barrier.get("risk_confidence"),
        "primary_issue": barrier.get("primary_issue", ""),
        "dominant_source": barrier.get("dominant_source", ""),
        "dominant_reason": barrier.get("dominant_reason", ""),
        "solver_used": barrier.get("solver_used", ""),
        "ct_solver_used": barrier.get("ct_solver_used", ""),
        "solver_reasoning": barrier.get("solver_reasoning", ""),
        "source_contributions": barrier.get("source_contributions", ""),
        "notes": barrier.get("notes", ""),
        "construction_note": barrier.get("construction_note", ""),
        "qa_issues": barrier.get("qa_issues", ""),
        "compliance_statement": barrier.get("compliance_statement", ""),
        "governing_requirement_text": barrier.get("governing_requirement_text", ""),
    }


BARRIER_CSV_FIELDS = [
    "room_name",
    "room_modality",
    "barrier",
    "barrier_element_type",
    "parent_barrier",
    "material",
    "provided_thickness_mm",
    "required_lead_mm",
    "required_concrete_mm",
    "recommended_commercial_lead_mm",
    "margin_mm",
    "unshielded_weekly_dose_uSv",
    "barrier_transmission_factor_B",
    "transmitted_dose_uSv_per_week",
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
    "solver_used",
    "ct_solver_used",
    "status",
    "primary_issue",
    "dominant_source",
    "governing_requirement_text",
]


def _write_barrier_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=BARRIER_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in BARRIER_CSV_FIELDS})


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_safe(data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.10g}"
    return value


def _generated_on(payload: Dict[str, Any]) -> str:
    meta = payload.get("meta", {}) or {}
    return str(meta.get("generated_on", "") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
