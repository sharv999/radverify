from __future__ import annotations

"""
Canonical results/report payload builder.

This module is the single source of truth for generated outputs:

    app/project state
        -> build_results_payload(app)
        -> PDF report
        -> JSON/CSV exports
        -> known-answer pytest snapshots

PDF rendering belongs in report_generator.py.
Machine-readable export writing belongs in results_exporter.py.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.shielding_engine import compute_room_barrier_table
from engine.design_constraints import build_room_constraint_summary
from services.source_readiness import validate_project_source_readiness
from services.report_certification import build_report_certification_state
from services.export_eligibility import apply_export_eligibility_to_payload
from services.payload_integrity import build_payload_calculation_integrity
from services.pet_spect_normal_report_route import (
    build_non_issueable_pet_spect_room_report_payload,
    canonical_result_rows_from_room_report_payload,
    is_pet_spect_report_modality,
    apply_pet_spect_normal_report_output_block,
)
from reports.solver_reasoning_text import solver_reasoning_text
from reports.results_text import (
    dominant_reason_text,
    dominant_source_text,
)
from reports.barrier_schedule import build_canonical_barrier_schedule_payload
from reports.report_semantics import (
    action_priority as _action_priority,
    attach_report_presentation,
    compliance_statement as _build_compliance_statement,
    first_exposed_transmitted_dose as _first_exposed_transmitted_dose,
    governing_requirement_text as _governing_requirement_text,
    normalise_status as _normalise_status,
    recommended_action as _build_recommended_action,
    rollup_room_status as _rollup_room_status,
    safe_float_or_none as _safe_float_or_none,
    status_text as _status_text,
    stringify_value as _stringify_value,
    user_facing_status_from_live as _user_facing_status_from_live,
)
from modalities.registry import (
    construction_shielding_height_for_modality,
    layout_rendering_for_modality,
    report_content_for_modalities,
    report_wording_for_modality,
    source_report_content_for_payload,
)
from services.xray_results_model import build_xray_results_model, XRAY_RESULTS_MODEL_VERSION, xray_results_issueable
from services.opening_physics import (
    opening_display_material,
    opening_live_result,
    opening_parent_barrier,
    opening_type_normalized,
)


def build_results_payload(
    app,
    logo_path: Optional[Path] = None,
    report_revision: str = "Rev 0",
    report_status: str = "Draft",
    reviewer_name: str = "",
    company_name: str = "healthphysics.ai",
) -> Dict[str, Any]:
    """Build the canonical payload used by PDF, JSON/CSV exports, and tests."""
    return _build_report_payload(
        app=app,
        logo_path=logo_path,
        report_revision=report_revision,
        report_status=report_status,
        reviewer_name=reviewer_name,
        company_name=company_name,
    )


def _build_report_payload(
    app,
    logo_path: Optional[Path],
    report_revision: str,
    report_status: str,
    reviewer_name: str,
    company_name: str,
) -> Dict[str, Any]:
    project = app.project

    project_name = _first_nonempty(
        getattr(project, "project_name", None),
        getattr(project, "name", None),
        _project_var(app, "Project Name"),
        "Shielding Assessment",
    )
    client = _first_nonempty(
        getattr(project, "client", None),
        _project_var(app, "Client"),
        "",
    )
    site = _first_nonempty(
        getattr(project, "site", None),
        _project_var(app, "Site"),
        "",
    )
    assessor = _first_nonempty(
        getattr(project, "assessor", None),
        _project_var(app, "Assessor"),
        "",
    )
    report_date = _first_nonempty(
        getattr(project, "date", None),
        _project_var(app, "Date"),
        datetime.now().strftime("%d %B %Y"),
    )
    modality_field = _first_nonempty(
        getattr(project, "modality", None),
        _project_var(app, "Modality"),
        "",
    )

    try:
        project_notes = app.project_notes.get("1.0", "end").strip() if hasattr(app, "project_notes") else ""
    except Exception:
        project_notes = str(getattr(project, "notes", "") or "").strip()

    try:
        global_energy = str(app.global_energy_var.get()).strip()
    except Exception:
        global_energy = ""

    try:
        solver_mode = str(app.solver_mode_var.get()).strip()
    except Exception:
        solver_mode = ""

    report_modality = _first_nonempty(
        modality_field,
        _first_room_modality(getattr(project, "rooms", []) or []),
        "CT",
    )
    report_wording = report_wording_for_modality(report_modality)

    try:
        source_readiness = validate_project_source_readiness(
            app.project,
            get_sources_for_room=app.get_sources_for_room,
        )
    except Exception as exc:
        source_readiness = {
            "overall_status": "UNKNOWN",
            "blocking": True,
            "errors": [f"Source readiness unavailable: {exc}"],
            "warnings": [],
            "room_results": [],
            "source_results": [],
        }

    rooms_payload: List[Dict[str, Any]] = []
    executive_rows: List[Dict[str, Any]] = []
    action_rows: List[Dict[str, Any]] = []
    detailed_source_rows: List[Dict[str, Any]] = []
    source_ksec_rows: List[Dict[str, Any]] = []
    source_input_supplements: dict[str, Dict[str, Any]] = {}
    source_assumption_bullets: List[str] = []

    total_pass = 0
    total_review = 0
    total_fail = 0

    for room in getattr(project, "rooms", []) or []:
        room_summary = build_room_constraint_summary(room.modality)
        wall_count_expected = len(list(getattr(room, "barriers", []) or []))

        pet_spect_room = is_pet_spect_report_modality(room.modality)
        xray_room = str(room.modality or "").strip().upper() == "X-RAY"
        pet_spect_report_route = None
        xray_report_qualification = None
        try:
            if pet_spect_room:
                pet_spect_report_route = build_non_issueable_pet_spect_room_report_payload(app, room)
                room_results = canonical_result_rows_from_room_report_payload(pet_spect_report_route)
            elif xray_room:
                room_results = build_xray_results_model(app.project, room)
                fig52_issueable = xray_results_issueable(room_results)
                xray_report_qualification = {
                    "qualification_version": "xr06-preliminary-pdf-v1",
                    "results_model_version": XRAY_RESULTS_MODEL_VERSION,
                    "issued_output_enabled": fig52_issueable,
                    "report_payload_qualified": True,
                    "barrier_count": len(room_results),
                }
                if all(str(r.get("fig52_section", "")) for r in room_results):
                    has_internal_control_wall = (
                        getattr(getattr(room, "geometry", None), "control_wall", None) is not None
                    )
                    xray_report_qualification.update({
                        "fig52_requalification_version": (
                            "xr17d-issueable-intervening-control-wall-v1"
                            if has_internal_control_wall and any(
                                r.get("control_wall_attenuation_applied") is True for r in room_results
                            )
                            else (
                                "xr15d-issueable-control-wall-v1" if has_internal_control_wall
                                else "xr08e-issueable-project-fig52-v1"
                            )
                        ),
                        "control_wall_qualified": bool(has_internal_control_wall),
                        "method": "NCRP Report No. 147 Section 5.3 / Figure 5.2 project-specific radiographic-room model",
                        "project_specific_geometry": True,
                    })
            else:
                room_results = compute_room_barrier_table(
                    app.project,
                    room.name,
                    app.global_energy_var.get(),
                    solver_mode=app.solver_mode_var.get(),
                )
            risk_by_name = {}
            room_error = ""
        except Exception as exc:
            room_results = []
            risk_by_name = {}
            room_error = str(exc)

        wall_result_count = len(room_results)
        if wall_result_count != wall_count_expected and not room_error:
            room_error = (
                f"Barrier calculation returned {wall_result_count} wall result(s) "
                f"for {wall_count_expected} wall barrier(s)."
            )

        room_sources = []
        try:
            source_objects = list(app.get_sources_for_room(room.name))
        except Exception:
            source_objects = list(getattr(room, "sources", []) or [])

        for src in source_objects:
            params = dict(getattr(src, "params", {}) or {})
            source_type = str(getattr(src, "source_type", "") or "")
            src_row = {
                "name": str(getattr(src, "name", "") or ""),
                "source_type": source_type,
                "radiation_type": str(getattr(src, "radiation_type", "") or ""),
                "params": params,
                "room_name": room.name,
                "room_modality": room.modality,
            }
            source_report_content = source_report_content_for_payload(src_row)
            source_metadata = dict(source_report_content.get("metadata", {}) or {})
            src_row["ksec_basis"] = source_metadata
            src_row["report_content"] = source_report_content
            room_sources.append(src_row)

            if source_metadata.get("is_ct_scatter"):
                source_ksec_rows.append(
                    {
                        "room_name": room.name,
                        "room_modality": room.modality,
                        "source_name": src_row["name"],
                        "source_type": src_row["source_type"],
                        **source_metadata,
                    }
                )

            supplement = dict(source_report_content.get("input_supplement", {}) or {})
            group_key = str(supplement.get("group_key", "") or "").strip()
            if group_key:
                group = source_input_supplements.setdefault(group_key, {
                    "heading": supplement.get("heading", "Source details"),
                    "headings": list(supplement.get("headings", []) or []),
                    "rows": [],
                    "column_widths_mm": list(supplement.get("column_widths_mm", []) or []),
                    "blocking_messages": [],
                    "warning_messages": [],
                })
                group["rows"].append(list(supplement.get("row", []) or []))
                for key, target in (("blocking_message", "blocking_messages"), ("warning_message", "warning_messages")):
                    message = str(supplement.get(key, "") or "").strip()
                    if message and message not in group[target]:
                        group[target].append(message)

            for bullet in source_report_content.get("assumption_bullets", []) or []:
                text = str(bullet or "").strip()
                if text and text not in source_assumption_bullets:
                    source_assumption_bullets.append(text)

            detailed_source_rows.append(
                {
                    "room_name": room.name,
                    "room_modality": room.modality,
                    "source_name": src_row["name"],
                    "source_type": src_row["source_type"],
                    "radiation_type": src_row["radiation_type"],
                    "params": params,
                    "ksec_basis": source_metadata,
                    "report_content": source_report_content,
                }
            )

        room_pass = 0
        room_review = 0
        room_fail = 0

        geom = getattr(room, "geometry", None)
        opening_count_expected = len(list(getattr(geom, "openings", []) or [])) if geom else 0

        try:
            barrier_rows = build_canonical_barrier_schedule_payload(
                app,
                room,
                room_results=room_results,
                risk_by_name=risk_by_name,
                allow_generic_fallback=not pet_spect_room,
            )
        except Exception as exc:
            barrier_rows = []
            room_error = room_error or f"Canonical barrier schedule generation failed: {exc}"

        for row in barrier_rows:
            status = _normalise_status(str(row.get("status") or row.get("compliance_status") or "PASS"))
            row["status"] = status
            row["compliance_status"] = status
            row["status_text"] = _status_text(status)
            row["compliance_statement"] = row.get("compliance_statement") or _build_compliance_statement(row)
            row["governing_requirement_text"] = row.get("governing_requirement_text") or _governing_requirement_text(row)

            if status == "PASS":
                room_pass += 1
                total_pass += 1
            elif status == "REVIEW":
                room_review += 1
                total_review += 1
            else:
                room_fail += 1
                total_fail += 1

            if status in {"FAIL", "REVIEW"}:
                action_rows.append(
                    {
                        "room_name": room.name,
                        "barrier_name": str(row.get("name", "") or row.get("barrier_id", "") or ""),
                        "status": status,
                        "recommended_action": _build_recommended_action(row),
                        "priority": _action_priority(status),
                    }
                )

        opening_count_exported = sum(
            1
            for row in barrier_rows
            if str(row.get("barrier_element_type", "") or "")
            .strip()
            .lower()
            .replace(" ", "_")
            in {"door", "viewing_panel"}
        )

        room_overall = _rollup_room_status(room_pass, room_review, room_fail)

        executive_rows.append(
            {
                "room_name": room.name,
                "modality": room.modality,
                "barriers_assessed": len(barrier_rows),
                "pass_count": room_pass,
                "review_count": room_review,
                "fail_count": room_fail,
                "overall_status": room_overall,
                "wall_count_expected": wall_count_expected,
                "wall_result_count": wall_result_count,
                "opening_count_expected": opening_count_expected,
                "opening_count_exported": opening_count_exported,
                "construction_shielding_height_mm": construction_shielding_height_for_modality(room.modality),
            }
        )

        rooms_payload.append(
            {
                "name": room.name,
                "modality": room.modality,
                "report_meta": {"report_wording": _report_wording_dict(report_wording)},
                "geometry": _room_geometry_dict(getattr(room, "geometry", None), room.modality),
                "classification": str(room_summary.get("classification", "") or ""),
                "default_energy_label": str(room_summary.get("default_energy_label", "") or ""),
                "default_solver_mode": str(room_summary.get("default_solver_mode", "") or ""),
                "expected_source_types": list(room_summary.get("expected_source_types", []) or []),
                "error": room_error,
                "pet_spect_report_route": pet_spect_report_route,
                "xray_report_qualification": xray_report_qualification,
                "sources": room_sources,
                "barriers": barrier_rows,
                "barrier_schedule_rows": barrier_rows,
                "pass_count": room_pass,
                "review_count": room_review,
                "fail_count": room_fail,
                "overall_status": room_overall,
                "wall_count_expected": wall_count_expected,
                "wall_result_count": wall_result_count,
                "opening_count_expected": opening_count_expected,
                "opening_count_exported": opening_count_exported,
                "construction_shielding_height_mm": construction_shielding_height_for_modality(room.modality),
            }
        )

    pet_spect_routes = [
        room.get("pet_spect_report_route")
        for room in rooms_payload
        if isinstance(room.get("pet_spect_report_route"), dict)
    ]
    source_readiness = apply_pet_spect_normal_report_output_block(source_readiness, pet_spect_routes)

    if any(str(room.get("modality", "")).strip().upper() == "X-RAY" for room in rooms_payload):
        source_assumption_bullets.extend([
            "General Radiography shielding is calculated using NCRP Report No. 147 Section 5.3 / Figure 5.2 with project-specific barrier distances.",
            "Primary-beam pre-shielding is explicit: grid/cassette/support for floor and chest-bucky scenarios, and grid/cassette for cross-table lateral exposures.",
            "Cross-table lateral shielding combines transmitted primary and secondary air kerma iteratively; other Section 5.3 scenarios apply their qualified governing rule.",
            "XR-15C carries internal Control Wall geometry and NCRP 147 Section 5.3 result provenance through canonical Results and report payloads; issued output containing a Control Wall remains fail-closed pending XR-15D release.",
        ])

    prepared_report_content = report_content_for_modalities(
        [room.get("modality", "") for room in rooms_payload]
    )
    prepared_report_content["source_input_supplements"] = list(source_input_supplements.values())
    prepared_report_content["assumption_bullets"] = list(
        prepared_report_content.get("assumption_bullets", [])
    ) + [
        bullet for bullet in source_assumption_bullets
        if bullet not in prepared_report_content.get("assumption_bullets", [])
    ]

    report_payload = {
        "meta": {
            "company_name": company_name,
            "logo_path": str(logo_path) if logo_path and logo_path.exists() else None,
            "report_title": report_wording.report_title,
            "report_wording": _report_wording_dict(report_wording),
            "report_revision": report_revision,
            "report_status": report_status,
            "prepared_by": assessor,
            "reviewed_by": reviewer_name,
            "date_issued": report_date,
            "generated_on": datetime.now().strftime("%d %B %Y %H:%M"),
        },
        "project": {
            "project_name": project_name,
            "client": client,
            "site": site,
            "assessor": assessor,
            "date": report_date,
            "modality": modality_field,
            "notes": project_notes,
            "global_energy": global_energy,
            "solver_mode": solver_mode,
        },
        "summary": {
            "room_count": len(rooms_payload),
            "barrier_count": sum(len(room["barriers"]) for room in rooms_payload),
            "pass_count": total_pass,
            "review_count": total_review,
            "fail_count": total_fail,
            "source_ksec_database_count": sum(1 for row in source_ksec_rows if row.get("basis") == "database"),
            "source_ksec_manual_override_count": sum(1 for row in source_ksec_rows if row.get("basis") == "manual_override"),
            "source_ksec_incomplete_count": sum(1 for row in source_ksec_rows if row.get("basis") == "manual_override_required"),
        },
        "rooms": rooms_payload,
        "executive_rows": executive_rows,
        "action_rows": action_rows,
        "source_ksec_rows": source_ksec_rows,
        "source_readiness": source_readiness,
        "detailed_source_rows": detailed_source_rows,
        "report_content": prepared_report_content,
    }

    report_payload["calculation_integrity"] = build_payload_calculation_integrity(report_payload)
    apply_export_eligibility_to_payload(
        report_payload,
        requested_report_status=report_payload["meta"].get("report_status", "Draft"),
    )

    # Apply final report/certification wording after export eligibility and
    # payload-integrity gates are attached, so the PDF cannot overclaim status.
    report_payload["certification"] = build_report_certification_state(report_payload)
    attach_report_presentation(report_payload)
    return report_payload


def _room_geometry_dict(geometry: Any, modality_id: str | None = None) -> Dict[str, Any]:
    """Return a clean, JSON-safe room-geometry dictionary for report/layout rendering."""
    if geometry is None:
        return {}

    def _get(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def _source_dict(source: Any) -> Dict[str, Any]:
        if not source:
            return {}
        return {
            "label": str(_get(source, "label", "") or ""),
            "x_m": _safe_float_or_none(_get(source, "x_m", None)),
            "y_m": _safe_float_or_none(_get(source, "y_m", None)),
            "rotation_deg": _safe_float_or_none(_get(source, "rotation_deg", None)),
        }

    openings = []
    for opening in list(_get(geometry, "openings", []) or []):
        openings.append({
            "id": str(_get(opening, "id", "") or ""),
            "opening_type": str(_get(opening, "opening_type", _get(opening, "type", "")) or ""),
            "wall": str(_get(opening, "wall", _get(opening, "wall_id", "")) or ""),
            "centre_m": _safe_float_or_none(
                _get(opening, "centre_m", _get(opening, "center_m", _get(opening, "offset_m", None)))
            ),
            "offset_m": _safe_float_or_none(_get(opening, "offset_m", None)),
            "width_m": _safe_float_or_none(_get(opening, "width_m", None)),
            "pb_equiv_mm": _safe_float_or_none(_get(opening, "pb_equiv_mm", _get(opening, "pb_mm", None))),
        })

    control_wall_obj = _get(geometry, "control_wall", None)
    control_wall = {}
    if control_wall_obj is not None:
        control_wall = {
            "id": str(_get(control_wall_obj, "id", "CW1") or "CW1"),
            "center_x_m": _safe_float_or_none(_get(control_wall_obj, "center_x_m", None)),
            "center_y_m": _safe_float_or_none(_get(control_wall_obj, "center_y_m", None)),
            "length_m": _safe_float_or_none(_get(control_wall_obj, "length_m", None)),
            "orientation_deg": _safe_float_or_none(_get(control_wall_obj, "orientation_deg", None)),
            "nib_length_m": _safe_float_or_none(_get(control_wall_obj, "nib_length_m", None)),
            "material": str(_get(control_wall_obj, "material", "") or ""),
            "thickness_mm": _safe_float_or_none(_get(control_wall_obj, "thickness_mm", None)),
            "occupancy_factor": _safe_float_or_none(_get(control_wall_obj, "occupancy_factor", None)),
            "design_goal_uSv_per_week": _safe_float_or_none(_get(control_wall_obj, "design_goal_uSv_per_week", None)),
        }

    rendering = layout_rendering_for_modality(modality_id).as_dict()

    return {
        "room_name": str(_get(geometry, "room_name", "") or ""),
        "length_m": _safe_float_or_none(_get(geometry, "length_m", None)),
        "width_m": _safe_float_or_none(_get(geometry, "width_m", None)),
        "height_m": _safe_float_or_none(_get(geometry, "height_m", None)),
        "source": _source_dict(_get(geometry, "source", None)),
        "rendering": rendering,
        "openings": openings,
        "control_wall": control_wall,
    }


def _first_room_modality(rooms: list[Any]) -> str:
    for room in rooms:
        modality = str(getattr(room, "modality", "") or "").strip()
        if modality:
            return modality
    return ""


def _report_wording_dict(wording: Any) -> Dict[str, Any]:
    return {
        "report_title": str(getattr(wording, "report_title", "") or ""),
        "report_subtitle": str(getattr(wording, "report_subtitle", "") or ""),
        "cover_introduction": str(getattr(wording, "cover_introduction", "") or ""),
        "limitations_heading": str(getattr(wording, "limitations_heading", "") or ""),
        "limitation_bullets": [str(item) for item in list(getattr(wording, "limitation_bullets", ()) or ())],
        "room_schedule_prefix": str(getattr(wording, "room_schedule_prefix", "") or ""),
        "room_layout_heading": str(getattr(wording, "room_layout_heading", "") or ""),
        "barrier_schedule_heading": str(getattr(wording, "barrier_schedule_heading", "") or ""),
        "source_inputs_heading": str(getattr(wording, "source_inputs_heading", "") or ""),
    }


def _project_var(app, key: str) -> str:
    try:
        var = app.project_vars.get(key)
        return str(var.get()).strip() if var is not None else ""
    except Exception:
        return ""



def _opening_schedule_rows_from_app(app, room) -> List[Dict[str, Any]]:
    """
    Derive opening/sub-barrier rows from Geometry using the same app helper that
    populates the Barriers/Results UI.

    This is used when get_barrier_schedule_for_report() is unavailable or returns
    no rows. It prevents machine-readable exports from silently omitting doors
    and viewing panels.
    """
    rows: List[Dict[str, Any]] = []

    # Opening helpers are module-owned; failures are handled per opening below.

    geom = getattr(room, "geometry", None)
    openings = list(getattr(geom, "openings", []) or []) if geom else []

    for idx, opening in enumerate(openings, start=1):
        try:
            result = opening_live_result(app, room, opening, idx)
        except Exception:
            continue

        if not result:
            continue

        opening_barrier, live = result
        if opening_barrier is None:
            continue

        if not isinstance(live, dict):
            live = {}

        name = str(getattr(opening_barrier, "name", "") or "").strip()
        if not name:
            continue

        try:
            otype = opening_type_normalized(opening)
        except Exception:
            otype = str(getattr(opening, "opening_type", "door") or "door").strip().lower()

        if otype in {"lead_glass", "viewing_panel", "vp", "pb_glass"}:
            element = "viewing_panel"
        else:
            element = "door"

        try:
            display_material = opening_display_material(opening)
        except Exception:
            display_material = str(getattr(opening, "material", "") or "").strip()

        parent_name = ""
        try:
            display_material = opening_display_material(opening)
            parent_name = str(getattr(parent, "name", "") or "").strip() if parent is not None else ""
        except Exception:
            parent_name = str(getattr(opening_barrier, "adjacent_area", "") or "").strip()

        status = _user_facing_status_from_live(live)

        rows.append({
            "barrier_id": name,
            "barrier_element_type": element,
            "parent_barrier": parent_name,
            "adjacent_area": str(getattr(opening_barrier, "adjacent_area", "") or parent_name),
            "barrier_role": str(getattr(opening_barrier, "barrier_role", "") or element),
            "material": display_material or str(getattr(opening_barrier, "material", "") or ""),
            "provided_thickness_mm": _safe_float_or_none(getattr(opening_barrier, "thickness_mm", None)),
            "required_lead_mm": _safe_float_or_none(live.get("required_lead_mm")),
            "required_concrete_mm": _safe_float_or_none(live.get("required_concrete_mm")),
            "required_thickness_mm": _safe_float_or_none(live.get("required_thickness_mm")),
            "recommended_commercial_lead_mm": _safe_float_or_none(live.get("recommended_commercial_lead_mm")),
            "margin_mm": _safe_float_or_none(live.get("margin_mm")),
            "unshielded_weekly_dose_uSv": _safe_float_or_none(live.get("unshielded_weekly_dose_uSv")),
            "barrier_transmission_factor_B": _safe_float_or_none(live.get("barrier_transmission_factor_B")),
            "transmitted_dose_uSv_per_week": _first_exposed_transmitted_dose(live),
            "distance_m": _safe_float_or_none(getattr(opening_barrier, "distance_m", None)),
            "occupancy_factor": _safe_float_or_none(getattr(opening_barrier, "occupancy_factor", None)),
            "design_goal_uSv_per_week": _safe_float_or_none(getattr(opening_barrier, "design_goal_uSv_per_week", None)),
            "status": status,
            "dominant_source": "Secondary / Scatter",
            "dominant_reason": "",
            "solver_used": str(live.get("solver_used", "") or ""),
            "ct_solver_used": str(live.get("ct_solver_used", "") or ""),
            "solver_reasoning": f"Opening/sub-barrier {name} calculated from Geometry using opening_live_result().",
            "source_contributions": str(live.get("source_contributions", "") or ""),
            "notes": str(live.get("notes", "") or ""),
            "construction_note": f"{element.replace('_', ' ').title()} in {parent_name}" if parent_name else element.replace("_", " ").title(),
            "qa_issues": "",
        })

    return rows



def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""



class _HeadlessVar:
    """Small stand-in for Tkinter StringVar/DoubleVar-style objects."""

    def __init__(self, value: Any = "") -> None:
        self._value = value

    def get(self) -> Any:
        return self._value


class _HeadlessText:
    """Small stand-in for Tkinter Text widget used for project notes."""

    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self, *_args: Any, **_kwargs: Any) -> str:
        return self._value


class _HeadlessObject:
    """
    Dict-backed object allowing attribute access.

    This lets the existing canonical payload builder operate on saved project
    JSON without importing app.py, tkinter, or tabs.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._raw = data
        for key, value in data.items():
            setattr(self, key, _to_headless_object(value))

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def items(self):
        return self._raw.items()

    def keys(self):
        return self._raw.keys()

    def values(self):
        return self._raw.values()

    def __iter__(self):
        return iter(self._raw)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def _to_headless_object(value: Any) -> Any:
    if isinstance(value, dict):
        return _HeadlessObject(value)

    if isinstance(value, list):
        return [_to_headless_object(item) for item in value]

    return value

def _headless_global_energy_from_project_dict(project_payload: Dict[str, Any]) -> str:
    value = str(project_payload.get("global_energy", "") or "").strip()
    if value:
        return value

    for src in project_payload.get("sources", []) or []:
        if not isinstance(src, dict):
            continue

        params = src.get("params", {}) or {}
        radiation_type = str(src.get("radiation_type", "") or "").strip().lower()
        scanner_kvp = params.get("scanner_kvp")

        if scanner_kvp not in (None, ""):
            try:
                return f"{int(float(scanner_kvp))} kVp"
            except Exception:
                pass

        if "140" in radiation_type:
            return "140 kVp"
        if "120" in radiation_type:
            return "120 kVp"
        if "100" in radiation_type:
            return "100 kVp"
        if "80" in radiation_type:
            return "80 kVp"

    return "140 kVp"


def _headless_solver_mode_from_project_dict(project_payload: Dict[str, Any]) -> str:
    value = str(project_payload.get("solver_mode", "") or "").strip()
    return value or "auto"


def _project_vars_from_project_dict(project_payload: Dict[str, Any]) -> Dict[str, _HeadlessVar]:
    """
    Build the app.project_vars fallback dictionary expected by _project_var().
    """
    return {
        "Project Name": _HeadlessVar(
            _first_nonempty(
                project_payload.get("project_name"),
                project_payload.get("name"),
                "Shielding Assessment",
            )
        ),
        "Client": _HeadlessVar(project_payload.get("client", "")),
        "Site": _HeadlessVar(project_payload.get("site", "")),
        "Assessor": _HeadlessVar(project_payload.get("assessor", "")),
        "Date": _HeadlessVar(project_payload.get("date", "")),
        "Modality": _HeadlessVar(project_payload.get("modality", "")),
    }


def _build_headless_app_from_project_dict(project_payload: Dict[str, Any]) -> _HeadlessObject:
    """
    Build the minimum app-shaped object required by _build_report_payload().

    This object is deliberately not an instance of ShieldingDesktopApp and does
    not use Tkinter variables/widgets.
    """
    effective_project_payload = _headless_project_payload_with_room_sources(project_payload)

    project = _HeadlessObject(effective_project_payload)

    def _headless_get_room_by_name(name: str):
        target = str(name or "").strip()
        for room in getattr(project, "rooms", []) or []:
            room_name = str(getattr(room, "name", "") or "").strip()
            if room_name == target:
                return room
        return None


    project.get_room_by_name = _headless_get_room_by_name

    project.get_sources_for_room = (
        lambda room_name: _headless_get_sources_for_room(effective_project_payload, room_name)
    )

    app = _HeadlessObject(
        {
            "project": project,
            "project_vars": _project_vars_from_project_dict(project_payload),
            "project_notes": _HeadlessText(str(project_payload.get("notes", "") or "")),
            "global_energy_var": _HeadlessVar(_headless_global_energy_from_project_dict(project_payload)),
            "solver_mode_var": _HeadlessVar(_headless_solver_mode_from_project_dict(project_payload)),
        }
    )

    # Keep this as a real dict because _build_report_payload() calls .get().
    app.get_barrier_schedule_for_report = (
        lambda room_name: _headless_get_barrier_schedule_for_report(project_payload, room_name)
    )
    app.get_sources_for_room = (
        lambda room_name: _headless_get_sources_for_room(project_payload, room_name)
    )
    app._headless_project_payload = project_payload

    return app


def _headless_get_sources_for_room(project_payload: Dict[str, Any], room_name: str) -> List[Any]:
    """
    Return sources assigned to the requested room for headless payload builds.

    Saved project JSON may store sources in either:
      1. room["sources"]
      2. project["sources"] with source["room_name"] == room_name

    Prefer room-local sources when present because several tests construct
    modified/manual-ksec fixtures by editing room["sources"].
    """
    target = str(room_name or "").strip()

    room_local_sources: List[Any] = []
    project_level_sources: List[Any] = []

    rooms = project_payload.get("rooms", []) or []
    for room in rooms:
        if not isinstance(room, dict):
            continue

        this_name = str(room.get("name") or room.get("room_name") or "").strip()
        if this_name != target:
            continue

        for src in room.get("sources", []) or []:
            if not isinstance(src, dict):
                continue

            src_copy = dict(src)
            src_copy.setdefault("room_name", target)
            room_local_sources.append(_HeadlessObject(src_copy))

        break

    for src in project_payload.get("sources", []) or []:
        if not isinstance(src, dict):
            continue

        src_room = str(src.get("room_name", "") or "").strip()
        if src_room == target:
            project_level_sources.append(_HeadlessObject(src))

    # Important: room-local sources win when present. This preserves tests that
    # mutate room["sources"] to create manual/review/failure cases.
    if room_local_sources:
        return room_local_sources

    return project_level_sources


def _build_report_payload_from_project_dict(project_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a canonical report/output payload directly from a saved project dict.

    This is the headless project JSON -> results payload adapter used by the
    golden-output regression test.
    """
    headless_app = _build_headless_app_from_project_dict(project_payload)

    return _build_report_payload(
        app=headless_app,
        logo_path=None,
        report_revision=str(project_payload.get("report_revision", "Rev 0") or "Rev 0"),
        report_status=str(project_payload.get("report_status", "Draft") or "Draft"),
        reviewer_name=str(project_payload.get("reviewer_name", "") or ""),
        company_name=str(project_payload.get("company_name", "healthphysics.ai") or "healthphysics.ai"),
    )


def build_results_payload_from_project_dict(project_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public headless adapter.

    Takes a saved project JSON dictionary and returns the same canonical payload
    used for PDF, JSON/CSV exports, and snapshot tests.
    """
    return _build_report_payload_from_project_dict(project_payload)


def _dominant_reason_text(contributions: Any) -> str:
    """
    Headless-safe replacement for app._dominant_reason_text().

    Produces a short explanation of which source governs the barrier result.
    """
    if not contributions:
        return ""

    try:
        from reports.results_text import largest_contribution_label

        label = largest_contribution_label(contributions)
    except Exception:
        label = ""

    if label:
        return f"Governing source contribution: {label}."

    if isinstance(contributions, str):
        text = contributions.strip()
        return text if text else ""

    return "Governing source contribution determined from calculated source contributions."


def _headless_get_barrier_schedule_for_report(project_payload: Dict[str, Any], room_name: str) -> List[Dict[str, Any]]:
    """
    Return saved/exported barrier schedule rows for a room, if the project JSON
    contains them.

    This keeps the headless golden-output adapter aligned with the app export
    payload without using the Tkinter UI.
    """
    rooms = project_payload.get("rooms", []) or []

    for room in rooms:
        if not isinstance(room, dict):
            continue

        this_name = str(room.get("name") or room.get("room_name") or "").strip()
        if this_name != str(room_name).strip():
            continue

        for key in (
            "barrier_schedule",
            "barrier_schedule_rows",
            "construction_schedule",
            "opening_schedule_rows",
            "openings_schedule",
            "report_barrier_schedule",
        ):
            rows = room.get(key)
            if isinstance(rows, list):
                return rows

        geometry = room.get("geometry") or {}
        if isinstance(geometry, dict):
            for key in (
                "barrier_schedule",
                "barrier_schedule_rows",
                "opening_schedule_rows",
                "openings_schedule",
            ):
                rows = geometry.get(key)
                if isinstance(rows, list):
                    return rows

    return _headless_opening_schedule_rows_from_project_dict(project_payload, room_name)


def _headless_project_payload_with_room_sources(project_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of project_payload where project-level sources assigned by
    room_name are mirrored into room["sources"] for the headless engine path.

    The desktop app treats project-level sources as the source of truth via
    get_sources_for_room(). The deprecated compute_room_barrier_table() path
    still reads room.sources directly, so the headless adapter must provide
    the same effective source inventory.
    """
    import copy

    payload = copy.deepcopy(project_payload)

    project_sources = [
        src for src in payload.get("sources", []) or []
        if isinstance(src, dict)
    ]

    for room in payload.get("rooms", []) or []:
        if not isinstance(room, dict):
            continue

        room_name = str(room.get("name") or room.get("room_name") or "").strip()

        room_sources = [
            src for src in room.get("sources", []) or []
            if isinstance(src, dict)
        ]

        if room_sources:
            continue

        matched_sources = []
        for src in project_sources:
            src_room = str(src.get("room_name", "") or "").strip()
            if src_room == room_name:
                src_copy = copy.deepcopy(src)
                src_copy.setdefault("room_name", room_name)
                matched_sources.append(src_copy)

        room["sources"] = matched_sources

    return payload


def _headless_opening_schedule_rows_from_project_dict(
    project_payload: Dict[str, Any],
    room_name: str,
) -> List[Dict[str, Any]]:
    rooms = project_payload.get("rooms", []) or []

    for room in rooms:
        if not isinstance(room, dict):
            continue

        this_name = str(room.get("name") or room.get("room_name") or "").strip()
        if this_name != str(room_name).strip():
            continue

        geometry = room.get("geometry") or {}
        if not isinstance(geometry, dict):
            return []

        openings = geometry.get("openings") or []
        if not isinstance(openings, list):
            return []

        rows: List[Dict[str, Any]] = []

        for idx, opening in enumerate(openings, start=1):
            if not isinstance(opening, dict):
                continue

            project_obj = _HeadlessObject(project_payload)

            room_obj = _HeadlessObject(room)
            room_obj.sources = _headless_get_sources_for_room(project_payload, this_name)

            opening_obj = _HeadlessObject(opening)

            def _get_room_by_name(name: str):
                target = str(name or "").strip()
                if target == this_name:
                    return room_obj
                return None

            project_obj.get_room_by_name = _get_room_by_name
            project_obj.get_sources_for_room = (
                lambda rn: _headless_get_sources_for_room(project_payload, rn)
            )

            app_obj = _HeadlessObject(
                {
                    "project": project_obj,
                    "global_energy_var": _HeadlessVar(
                        _headless_global_energy_from_project_dict(project_payload)
                    ),
                    "solver_mode_var": _HeadlessVar(
                        _headless_solver_mode_from_project_dict(project_payload)
                    ),
                }
            )

            app_obj.get_room_by_name = _get_room_by_name
            app_obj.get_sources_for_room = (
                lambda rn: _headless_get_sources_for_room(project_payload, rn)
            )

            opening_barrier, live = opening_live_result(
                app_obj,
                room_obj,
                opening_obj,
                idx,
            )

            if opening_barrier is None:
                continue

            if not isinstance(live, dict):
                live = {}

            parent_obj = opening_parent_barrier(room_obj, opening_obj)
            parent = str(
                getattr(parent_obj, "name", None)
                or getattr(parent_obj, "barrier_id", None)
                or getattr(parent_obj, "id", None)
                or parent_obj
                or ""
            )

            opening_type = opening_type_normalized(opening_obj)
            display_material = opening_display_material(opening_obj)

            name = str(getattr(opening_barrier, "name", "") or "").strip()

            if not name:
                label = str(opening.get("label", "") or "").strip()
                opening_id = str(opening.get("id", "") or "").strip()

                if label:
                    name = label
                elif opening_id:
                    name = opening_id
                elif opening_type in {"viewing_panel", "viewing panel", "vp"}:
                    name = f"VP{idx}"
                else:
                    name = f"D{idx}"

            is_viewing_panel = opening_type in {"viewing_panel", "viewing panel", "vp"}

            status = _user_facing_status_from_live(live)

            rows.append(
                {
                    "barrier_id": name,
                    "barrier_element_type": "viewing_panel" if is_viewing_panel else "door",
                    "parent_barrier": parent,
                    "adjacent_area": parent,
                    "barrier_role": "viewing_panel" if is_viewing_panel else "door",
                    "material": display_material,
                    "provided_thickness_mm": (
                        opening.get("provided_thickness_mm")
                        or opening.get("thickness_mm")
                        or opening.get("pb_equiv_mm")
                        or opening.get("lead_equiv_mm")
                    ),
                    "required_lead_mm": live.get("required_lead_mm"),
                    "required_concrete_mm": live.get("required_concrete_mm"),
                    "required_thickness_mm": live.get("required_thickness_mm"),
                    "recommended_commercial_lead_mm": live.get("recommended_commercial_lead_mm"),
                    "margin_mm": live.get("margin_mm"),
                    "unshielded_weekly_dose_uSv": live.get("unshielded_weekly_dose_uSv"),
                    "barrier_transmission_factor_B": live.get("barrier_transmission_factor_B"),
                    "transmitted_dose_uSv_per_week": (
                        live.get("transmitted_dose_uSv_per_week")
                        or live.get("Tx_uSv_per_week")
                    ),
                    "distance_m": (
                        live.get("distance_m")
                        or getattr(opening_barrier, "distance_m", None)
                        or opening.get("distance_m")
                    ),
                    "occupancy_factor": (
                        live.get("occupancy_factor")
                        or getattr(opening_barrier, "occupancy_factor", None)
                        or opening.get("occupancy_factor")
                    ),
                    "design_goal_uSv_per_week": (
                        live.get("design_goal_uSv_per_week")
                        or getattr(opening_barrier, "design_goal_uSv_per_week", None)
                        or opening.get("design_goal_uSv_per_week")
                    ),
                    "status": status,
                    "risk_visual_state": status,
                    "risk_colour": "",
                    "risk_confidence": None,
                    "primary_issue": "",
                    "dominant_source": str(live.get("dominant_source", "") or "Secondary / Scatter"),
                    "dominant_reason": str(live.get("dominant_reason", "") or ""),
                    "solver_used": str(live.get("solver_used", "") or "Construction schedule"),
                    "ct_solver_used": str(live.get("ct_solver_used", "") or ""),
                    "solver_reasoning": str(
                        live.get("solver_reasoning", "")
                        or "Local opening/sub-barrier generated from Geometry and calculated using the same physics path as the Barriers tab."
                    ),
                    "source_contributions": str(live.get("source_contributions", "") or ""),
                    "notes": str(opening.get("notes", "") or ""),
                    "construction_note": str(opening.get("construction_note", "") or ""),
                    "qa_issues": str(opening.get("qa_issues", "") or ""),
                }
            )

        return rows

    return []
