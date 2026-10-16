from __future__ import annotations

import math

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageBreakIfNotEmpty,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)

from modalities.registry import (
    source_contribution_group,
    source_report_summary_columns_for_type,
    source_report_summary_row_for_payload,
)
from reports.results_exporter import write_results_exports_from_payload
from reports.results_payload_builder import build_results_payload
from reports.pdf_style import build_styles, section_divider, styled_table
from reports.report_semantics import (
    fmt_float as _fmt_float,
    normalise_status as _normalise_status,
    report_presentation,
    safe_float_or_none as _safe_float_or_none,
    stringify_value as _stringify_value,
)

from geometry.source_marker_layout import resolve_source_marker_points

from config.ui_constants import (
    BARRIER_OVERLAY_WIDTH,
    COLOUR_ALERT,
    COLOUR_CANVAS_BG,
    COLOUR_FAIL,
    COLOUR_GRID_MAJOR,
    COLOUR_GRID_MINOR,
    COLOUR_OUTLINE,
    COLOUR_PASS,
    COLOUR_REVIEW_DARK,
    COLOUR_SCANNER,
    COLOUR_TEXT,
    COLOUR_TEXT_MUTED,
    OPENING_THICKNESS_PX,
    ROOM_OUTLINE_WIDTH,
    WALL_LABEL_LINE_SPACING,
    WALL_LABEL_OFFSET_EW,
)


# =====================================================# Public entry point
# =====================================================

def render_pdf_from_payload(
    payload: Dict[str, Any],
    output_path: str | Path,
) -> Path:
    """
    Render a PDF from an already-built canonical payload.

    This is used by reports.output_pipeline so PDF/JSON/CSV generation share the
    same payload and the app does not need to know PDF internals.
    """
    output_path = Path(output_path)
    _build_pdf(payload, output_path)
    return output_path


def pdf_payload_with_project_context(payload: Dict[str, Any], app: Any) -> Dict[str, Any]:
    """Return a shallow PDF-only payload enriched with report presentation context.

    The canonical results payload is intentionally left unchanged.  This helper
    exists so PDF-only fields such as project type can be displayed without
    changing JSON/CSV exports or any shielding calculation/result structures.
    """
    pdf_payload = dict(payload or {})
    project_payload = dict(pdf_payload.get("project", {}) or {})
    project = getattr(app, "project", None)
    project_type = str(getattr(project, "project_type", "new_build") or "new_build").strip().lower()
    project_payload["project_type"] = "refurbishment" if project_type == "refurbishment" else "new_build"
    pdf_payload["project"] = project_payload
    return pdf_payload


def generate_report_from_app(
    app,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    report_revision: str = "Rev 0",
    report_status: str = "Draft",
    reviewer_name: str = "",
    company_name: str = "healthphysics.ai",
) -> Path:
    output_path = Path(output_path)
    payload = build_results_payload(
        app=app,
        logo_path=Path(logo_path) if logo_path else None,
        report_revision=report_revision,
        report_status=report_status,
        reviewer_name=reviewer_name,
        company_name=company_name,
    )
    render_pdf_from_payload(pdf_payload_with_project_context(payload, app), output_path)

    # Generate machine-readable outputs beside the PDF so results can be tested
    # against known-answer fixtures without scraping the Tkinter UI or PDF.
    try:
        write_results_exports_from_payload(payload, output_path, include_csv=False)
    except Exception as exc:
        # PDF generation should remain the primary user action. Export failures
        # are surfaced as a warning in stdout rather than blocking report output.
        print(f"[WARN] Results export failed: {exc}")

    return output_path


# Payload building lives in reports.results_payload_builder.

# =====================================================# PDF build
# =====================================================

def _build_pdf(payload: Dict[str, Any], output_path: Path) -> None:
    """Build the client-facing preliminary shielding assessment PDF.

    This renderer consumes only the already-built report/results payload.  It
    does not calculate shielding, change physics inputs, or alter canonical
    result values.  The six-page structure is designed to answer the practical
    client questions: what was assessed, what assumptions were used, what must
    be built/verified, and what is required before final acceptance.
    """
    styles = build_styles()

    doc = _ShieldingDocTemplate(
        filename=str(output_path),
        pagesize=landscape(A4),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
    )
    doc.meta_payload = payload

    story: List[Any] = []
    story.extend(_section_preliminary_cover(payload, styles))

    rooms = list(payload.get("rooms", []) or [])
    for room in rooms:
        story.append(PageBreakIfNotEmpty())
        story.extend(_section_preliminary_design_basis(payload, room, styles, section_number=3))
        story.append(PageBreakIfNotEmpty())
        story.extend(_section_preliminary_barrier_plan(room, styles, section_number=4))
        story.append(PageBreakIfNotEmpty())
        story.extend(_section_preliminary_barrier_schedule(payload, room, styles, section_number=5))
        story.append(PageBreakIfNotEmpty())
        story.extend(_section_preliminary_actions(payload, room, styles, section_number=6))
        story.append(PageBreakIfNotEmpty())
        story.extend(_section_preliminary_conclusion(payload, room, styles, section_number=7))

    doc.build(story)


def _section_preliminary_cover(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    meta = payload.get("meta", {}) or {}
    project = payload.get("project", {}) or {}
    summary = payload.get("summary", {}) or {}

    project_name = str(project.get("project_name", "Shielding Assessment") or "Shielding Assessment")
    project_type = _human_project_type(project.get("project_type", "new_build"))
    modality = _payload_modality(payload)
    title = f"Preliminary Shielding Assessment - {project_type}"
    rooms = list(payload.get("rooms", []) or [])
    room_name = ""
    if rooms:
        first_room = rooms[0] or {}
        room_name = str(
            first_room.get("room_name")
            or first_room.get("name")
            or (first_room.get("geometry", {}) or {}).get("room_name")
            or ""
        )

    rows = [
        ["Project name", project_name],
        ["Room name", room_name],
        ["Modality", modality],
        ["Project type", project_type],
    ]
    project_note = str(project.get("notes", "") or "").strip()
    if project_note:
        rows.append(["Project note", project_note])
    rows.extend([
        ["Client", str(project.get("client", "") or "")],
        ["Site", str(project.get("site", "") or "")],
        ["Assessor", str(project.get("assessor", "") or "")],
        ["Date", str(project.get("date", "") or "")],
        ["Report status", str(meta.get("report_status", "Draft") or "Draft")],
        ["Revision", str(meta.get("report_revision", "Rev 0") or "Rev 0")],
    ])

    status = _preliminary_overall_status(payload)
    action_count = int(summary.get("review_count", 0) or 0) + int(summary.get("fail_count", 0) or 0)
    outcome_rows = [
        ["Overall preliminary outcome", status],
        ["Barriers assessed", str(summary.get("barrier_count", 0))],
        ["Barriers requiring review / redesign", str(action_count)],
        ["Design decision", _preliminary_design_decision(payload)],
    ]

    flow: List[Any] = [
        Spacer(1, 8 * mm),
        Paragraph(title, styles["CoverTitle"]),
        Spacer(1, 3 * mm),
        Paragraph(
            "A client-facing preliminary assessment for design development and shielding coordination. "
            "It identifies the adopted design basis, preliminary barrier requirements, and the information "
            "that must be confirmed before final shielding acceptance.",
            styles["Body"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "This report is not a certificate of shielding compliance.",
            styles["Muted"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("1. Project details", styles["SectionHeading"]),
        _client_key_value_table(rows, [38 * mm, 114 * mm]),
        Spacer(1, 5 * mm),
        Paragraph("2. Assessment outcome", styles["SectionHeading"]),
        _client_outcome_table(outcome_rows, status),
    ]
    return flow


def _section_preliminary_design_basis(
    payload: Dict[str, Any],
    room: Dict[str, Any],
    styles: StyleSheet1,
    section_number: int,
) -> List[Any]:
    geometry = room.get("geometry", {}) or {}
    source = geometry.get("source", {}) or {}
    room_name = str(room.get("name") or geometry.get("room_name") or "Room")
    modality = str(room.get("modality", "") or "Not stated")

    room_rows = [
        ["Room", room_name],
        ["Modality", modality],
        ["Room dimensions", _room_dimensions_text(geometry)],
        ["FFL to FCL", _fmt_dimension(geometry.get("height_m"))],
        ["Source position", _source_position_text(source)],
    ]

    criteria_rows: List[List[str]] = [["Barrier", "Adjacent area", "Distance (m)", "Occupancy T", "P (uSv/wk)"]]
    for row in list(room.get("barriers", []) or []):
        criteria_rows.append([
            str(row.get("name", "") or ""),
            str(row.get("adjacent_area", "") or "Not stated"),
            _fmt_pdf_number(row.get("distance_m"), 2),
            _fmt_pdf_number(row.get("occupancy_factor"), 3),
            _fmt_pdf_number(row.get("design_goal_uSv_per_week"), 1),
        ])

    flow: List[Any] = [
        Paragraph(f"{section_number}. Design basis", styles["SectionHeading"]),
        Paragraph(
            "The preliminary result is valid only for the room geometry, source/workload and occupancy assumptions "
            "summarised below. These values should be confirmed by the client/design team before detailed design.",
            styles["Body"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("3.1 Room and geometry", styles["RoomHeading"]),
        _client_key_value_table(room_rows, [42 * mm, 110 * mm]),
        Spacer(1, 5 * mm),
        Paragraph("3.2 Source and workload assumptions", styles["RoomHeading"]),
        _source_design_basis_table(room),
        Spacer(1, 5 * mm),
        Paragraph("3.3 Design criteria and occupancy", styles["RoomHeading"]),
        styled_table(criteria_rows, [34 * mm, 62 * mm, 30 * mm, 24 * mm, 32 * mm], header=True),
    ]
    return flow


def _section_preliminary_barrier_plan(
    room: Dict[str, Any],
    styles: StyleSheet1,
    section_number: int,
) -> List[Any]:
    return [
        Paragraph(f"{section_number}. Barrier plan", styles["SectionHeading"]),
        Spacer(1, 3 * mm),
        _RoomLayoutFlowable(room, width=220 * mm, height=132 * mm),
        Spacer(1, 2 * mm),
        Paragraph(
            "Barrier labels show the entered construction and the calculated preliminary result. "
            "The architectural drawing, openings and service penetrations must be coordinated separately before final acceptance.",
            styles["Muted"],
        ),
    ]


def _section_preliminary_barrier_schedule(
    payload: Dict[str, Any],
    room: Dict[str, Any],
    styles: StyleSheet1,
    section_number: int,
) -> List[Any]:
    barrier_rows = list(room.get("barriers", []) or [])
    flow: List[Any] = [
        Paragraph(f"{section_number}. Barrier schedule", styles["SectionHeading"]),
        Paragraph(
            "The schedule below reports the canonical calculation results for the assessed barriers.",
            styles["Body"],
        ),
        Spacer(1, 3 * mm),
        _barriers_tab_pdf_table(barrier_rows),
    ]
    # XR-17C: an attenuation credit must be explicit in the report rather than
    # being hidden inside the downstream barrier result.  XR-17D will separately
    # decide issueability; this is presentation/provenance only.
    bucky_credited = [b for b in barrier_rows if b.get("bucky_shield_attenuation_applied") is True]
    if bucky_credited:
        flow.append(Spacer(1, 2 * mm))
        flow.append(Paragraph("Chest Bucky Shield primary attenuation credit:", styles["Body"]))
        for b in bucky_credited:
            provenance = str(b.get("bucky_shield_provenance", "") or "").strip()
            if provenance:
                flow.append(Paragraph(f"{b.get('name', 'Barrier')}: {provenance}", styles["Muted"]))

    credited = [b for b in barrier_rows if b.get("control_wall_attenuation_applied") is True]
    if credited:
        flow.append(Spacer(1, 2 * mm))
        flow.append(Paragraph("Intervening Control Wall attenuation credit:", styles["Body"]))
        for b in credited:
            provenance = str(b.get("control_wall_provenance", "") or "").strip()
            if provenance:
                flow.append(Paragraph(f"{b.get('name', 'Barrier')}: {provenance}", styles["Muted"]))
    return flow


def _section_preliminary_actions(
    payload: Dict[str, Any],
    room: Dict[str, Any],
    styles: StyleSheet1,
    section_number: int,
) -> List[Any]:
    flow: List[Any] = [
        Paragraph(f"{section_number}. Design actions and verification", styles["SectionHeading"]),
        Paragraph(
            "This page identifies the items that should be closed out before the preliminary assessment is relied upon for "
            "construction or final shielding acceptance.",
            styles["Body"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("6.1 Project coordination actions", styles["RoomHeading"]),
        _project_action_register(payload, room),
        Spacer(1, 5 * mm),
        Paragraph("6.2 Changes that trigger reassessment", styles["RoomHeading"]),
    ]
    for item in _change_trigger_bullets(room):
        flow.append(_bullet_para(item, styles))
        flow.append(Spacer(1, 0.8 * mm))
    return flow


def _section_preliminary_conclusion(
    payload: Dict[str, Any],
    room: Dict[str, Any],
    styles: StyleSheet1,
    section_number: int,
) -> List[Any]:
    status = _preliminary_overall_status(payload)
    summary = payload.get("summary", {}) or {}
    project_type = _human_project_type((payload.get("project", {}) or {}).get("project_type", "new_build"))
    assessed = int(summary.get("barrier_count", 0) or 0)
    passed = int(summary.get("pass_count", 0) or 0)
    review = int(summary.get("review_count", 0) or 0)
    failed = int(summary.get("fail_count", 0) or 0)

    if status == "PASS":
        conclusion = (
            f"All {assessed} assessed barrier rows satisfy the preliminary shielding criteria for the stated design basis. "
            "The design may proceed to the next coordination stage, subject to completion of the verification items in Section 6."
        )
    elif status == "REVIEW":
        conclusion = (
            f"The preliminary assessment contains {review} item(s) requiring review before the shielding design is frozen. "
            "Resolve the identified assumptions/actions and rerun the assessment before construction documentation is issued."
        )
    else:
        conclusion = (
            f"The preliminary assessment contains {failed} barrier failure(s). The affected barriers require redesign and reassessment "
            "before the shielding arrangement is accepted for construction."
        )

    next_stage = (
        "For a refurbishment, the next stage should verify existing barrier construction, thickness, openings, penetrations and adjacent-area use "
        "against coordinated architectural information before issuing a detailed/final shielding assessment."
        if project_type == "Refurbishment"
        else
        "For a new build, the next stage should coordinate the shielding schedule with architectural drawings, door/window schedules, penetrations "
        "and confirmed operating assumptions before issuing a detailed/construction shielding assessment."
    )

    flow: List[Any] = [
        Paragraph(f"{section_number}. Conclusion and next stage", styles["SectionHeading"]),
        _client_outcome_table([
            ["Overall preliminary outcome", status],
            ["Barrier result", f"{passed} PASS | {review} REVIEW | {failed} FAIL"],
            ["Client decision", _preliminary_design_decision(payload)],
        ], status),
        Spacer(1, 5 * mm),
        Paragraph("7.1 Preliminary conclusion", styles["RoomHeading"]),
        Paragraph(conclusion, styles["Body"]),
        Spacer(1, 4 * mm),
        Paragraph("7.2 Recommended next stage", styles["RoomHeading"]),
        Paragraph(next_stage, styles["Body"]),
        Spacer(1, 4 * mm),
        Paragraph("7.3 Information normally required for the detailed/final assessment", styles["RoomHeading"]),
    ]
    for item in _next_stage_information(payload):
        flow.append(_bullet_para(item, styles))
        flow.append(Spacer(1, 0.8 * mm))

    flow.extend([
        Spacer(1, 4 * mm),
        Paragraph("8. Preliminary assessment limitations", styles["SectionHeading"]),
    ])
    for item in _modality_specific_limitations(_report_modality(payload)):
        flow.append(_bullet_para(item, styles))
        flow.append(Spacer(1, 0.8 * mm))
    return flow


def _preliminary_overall_status(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {}) or {}
    if int(summary.get("fail_count", 0) or 0) > 0:
        return "FAIL"
    if int(summary.get("review_count", 0) or 0) > 0:
        return "REVIEW"
    rooms = list(payload.get("rooms", []) or [])
    room_statuses = [str((room or {}).get("overall_status", "") or "").strip().upper() for room in rooms]
    if any(status == "FAIL" for status in room_statuses):
        return "FAIL"
    if any(status == "REVIEW" for status in room_statuses):
        return "REVIEW"
    return "PASS"


def _preliminary_design_decision(payload: Dict[str, Any]) -> str:
    status = _preliminary_overall_status(payload)
    if status == "PASS":
        return "Proceed with design development, subject to confirmation of the stated assumptions and verification items."
    if status == "REVIEW":
        return "Resolve the identified review items before the shielding design is frozen or issued for construction."
    return "Do not rely on the current shielding arrangement for construction; redesign the failed barrier(s) and reassess."


def _client_key_value_table(rows: Sequence[Sequence[str]], col_widths: Sequence[float]) -> Table:
    """Key/value client table with dark label cells matching report table headers."""
    table = Table(rows, colWidths=list(col_widths))
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CCD3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#182230")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]
    for row_index in range(len(rows)):
        if row_index % 2 == 1:
            style.append(("BACKGROUND", (1, row_index), (-1, row_index), colors.HexColor("#F7F8FA")))
    table.setStyle(TableStyle(style))
    return table


def _client_outcome_table(rows: Sequence[Sequence[str]], status: str) -> Table:
    status_colour = _status_colour(status)
    table = Table(rows, colWidths=[54 * mm, 172 * mm])
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("LEADING", (0, 0), (-1, -1), 10.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CCD3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#182230")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("TEXTCOLOR", (1, 0), (1, 0), status_colour),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
    ]
    table.setStyle(TableStyle(style))
    return table


def _fmt_dimension(value: Any) -> str:
    number = _layout_float(value, None)
    return "Not stated" if number is None else f"{number:.2f} m"


def _room_dimensions_text(geometry: Dict[str, Any]) -> str:
    width = _layout_float(geometry.get("width_m"), None)
    length = _layout_float(geometry.get("length_m"), None)
    if width is None or length is None:
        return "Not stated"
    return f"{width:.2f} m x {length:.2f} m"


def _source_position_text(source: Dict[str, Any]) -> str:
    x = _layout_float(source.get("x_m"), None)
    y = _layout_float(source.get("y_m"), None)
    if x is None or y is None:
        return "Not stated"
    return f"{x:.2f} m from west | {y:.2f} m from south"


def _patient_source_summary_from_room(room: Dict[str, Any]) -> Dict[str, Any]:
    route = room.get("pet_spect_report_route", {}) or {}
    payload = route.get("payload", {}) or {}
    return dict(payload.get("source_summary", {}) or {})


def _source_design_basis_table(room: Dict[str, Any]) -> Table:
    modality = str(room.get("modality", "") or "").strip().upper()
    summary = _patient_source_summary_from_room(room)
    rows: List[List[str]] = [["Parameter", "Adopted preliminary input"]]

    if modality == "SPECT" and summary:
        radionuclide = _human_radionuclide_code(summary.get("radionuclide"))
        rows.extend([
            ["Radionuclide", radionuclide or "Not stated"],
            ["Administered activity per patient", _fmt_with_unit(summary.get("administered_activity_mbq"), "MBq", 1)],
            ["Patient throughput", _fmt_with_unit(summary.get("patients_per_week"), "patients/week", 0)],
            ["Imaging duration", _fmt_with_unit(summary.get("imaging_duration_h"), "h/patient", 2)],
            ["Source position", f"{_fmt_pdf_number(summary.get('source_position_x_m'), 2)} m from west | {_fmt_pdf_number(summary.get('source_position_y_m'), 2)} m from south"],
        ])
    elif modality == "PET" and summary:
        radionuclide = _human_radionuclide_code(summary.get("radionuclide"))
        rows.extend([
            ["Radionuclide", radionuclide or "Not stated"],
            ["Administered activity per patient", _fmt_with_unit(summary.get("administered_activity_mbq_per_patient"), "MBq", 1)],
            ["Patient throughput", _fmt_with_unit(summary.get("patients_per_week"), "patients/week", 0)],
            ["Activity scaling factor", _fmt_pdf_number(summary.get("activity_scaling_factor"), 3)],
            ["Patient position", f"{_fmt_pdf_number(summary.get('pet_position_west_m'), 2)} m from west | {_fmt_pdf_number(summary.get('pet_position_south_m'), 2)} m from south | {_fmt_pdf_number(summary.get('pet_position_height_affl_m'), 2)} m AFFL"],
        ])
        periods = list(summary.get("exposure_periods", []) or [])
        if periods:
            labels = []
            for period in periods:
                labels.append(
                    f"{period.get('name', 'Period')}: {float(period.get('duration_h', 0) or 0):g} h, retention {float(period.get('activity_retention_factor', 0) or 0):g}"
                )
            rows.append(["Exposure periods", "; ".join(labels)])
    else:
        sources = list(room.get("sources", []) or [])
        if not sources:
            rows.append(["Source / workload", "No source detail is available in the report payload."])
        for source in sources:
            rows.append(["Source", str(source.get("name", "") or "")])
            rows.append([
                "Type / radiation",
                f"{_human_source_type(source.get('source_type', ''))} | {_human_radiation_type(source.get('radiation_type', ''))}",
            ])
            params = source.get("params", {}) or {}
            if modality == "CT":
                scanner_name = str(params.get("scanner_model", "") or "").strip()
                if not scanner_name:
                    scanner_name = str(params.get("scanner_vendor", "") or "").strip()
                rows.append(["Scanner", scanner_name or "Not stated"])
            if modality == "X-RAY":
                method = str(params.get("xray_method", "") or "").strip()
                room_type = str(params.get("exam_room_type", "") or "").strip()
                rows.extend([
                    ["Shielding method", "NCRP 147 simplified general radiography" if method == "ncrp_simplified" else (method or "Not stated")],
                    ["Exam room type", room_type.replace("_", " ").title() or "Not stated"],
                    ["Examinations per week", _fmt_with_unit(params.get("exams_per_week"), "exams/week", 0)],
                    ["Tube potential", _fmt_with_unit(params.get("tube_potential_kvp"), "kVp", 0)],
                ])
            for key, label, unit, decimals in (
                ("scans_per_week", "Scans per week", "", 0),
                ("workload_mAs_per_scan", "Workload per scan", "mAs", 1),
                ("ksec_mGy_per_100mAs_at_1m", "ksec at 1 m", "mGy/100 mAs", 3),
                ("scanner_kvp", "Tube potential", "kVp", 0),
            ):
                if params.get(key) not in (None, ""):
                    rows.append([label, _fmt_with_unit(params.get(key), unit, decimals)])

    return styled_table(rows, [64 * mm, 118 * mm], header=True)


def _human_radionuclide_code(value: Any) -> str:
    raw = str(value or "").strip()
    import re
    match = re.fullmatch(r"([A-Za-z]+)-?(\d+[A-Za-z]*)", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return raw


def _fmt_with_unit(value: Any, unit: str, decimals: int = 1) -> str:
    if value in (None, ""):
        return "Not stated"
    try:
        number = float(value)
        if decimals <= 0:
            text = f"{number:.0f}"
        else:
            text = f"{number:.{decimals}f}".rstrip("0").rstrip(".")
        return f"{text} {unit}".strip()
    except Exception:
        return f"{value} {unit}".strip()


def _construction_interpretation_table(payload: Dict[str, Any], barrier_rows: Sequence[Dict[str, Any]]) -> Table:
    project_type = str((payload.get("project", {}) or {}).get("project_type", "new_build") or "new_build").strip().lower()
    refurbishment = project_type == "refurbishment"
    shielding_heading = "Actual shielding" if refurbishment else "Prescribed shielding"
    rows: List[List[str]] = [["Barrier", shielding_heading, "Min. required shielding", "Design interpretation"]]
    for row in barrier_rows:
        material = str(row.get("material", "") or "")
        actual = _fmt_with_unit(row.get("provided_thickness_mm", row.get("thickness_mm")), f"mm {material}", 2)
        required = _fmt_with_unit(row.get("display_required_thickness_mm", row.get("required_thickness_mm")), f"mm {material}", 2)
        status = str(row.get("compliance_status") or row.get("status") or "").strip().upper()
        if status == "FAIL":
            interpretation = "Prescribed shielding is below the preliminary requirement. Revise the barrier design and rerun the assessment."
        elif status == "REVIEW":
            interpretation = "Review the input/model assumptions before the shielding design is frozen."
        elif refurbishment:
            interpretation = "Prescribed shielding exceeds the minimum required shielding. Verify the existing construction, thickness and shielding continuity."
        else:
            interpretation = "Prescribed shielding exceeds the minimum required shielding. Coordinate construction and shielding continuity."
        rows.append([str(row.get("name", "") or ""), actual, required, interpretation])
    return _client_wrapped_table(rows, [30 * mm, 42 * mm, 42 * mm, 112 * mm], header=True, font_size=7.5)


def _project_action_register(payload: Dict[str, Any], room: Dict[str, Any]) -> Table:
    project_type = str((payload.get("project", {}) or {}).get("project_type", "new_build") or "new_build").strip().lower()
    refurbishment = project_type == "refurbishment"
    rows: List[List[str]] = [["Action", "Suggested responsibility", "Required before"]]

    for item in list(payload.get("action_rows", []) or []):
        if str(item.get("room_name", "") or "") == str(room.get("name", "") or ""):
            rows.append([
                str(item.get("recommended_action", "") or ""),
                "Client / design team / physicist",
                "Design freeze",
            ])

    rows.extend([
        ["Confirm the current architectural drawing number/revision, room orientation and dimensions.", "Architect / client", "Detailed assessment"],
        ["Confirm the use and occupancy of areas beyond each wall, floor and ceiling.", "Client / architect", "Detailed assessment"],
        ["Provide door, viewing panel, duct, conduit and service-penetration details so shielding continuity can be assessed.", "Architect / builder", "Construction documentation"],
        ["Confirm radionuclide/scanner workload and operating assumptions with the intended operator.", "Imaging operator / client", "Detailed assessment"],
    ])
    if refurbishment:
        rows.insert(1, [
            "Verify existing wall, floor and ceiling construction/thickness against the entered shielding values.",
            "Client / builder; physicist review",
            "Final assessment",
        ])
    return _client_wrapped_table(rows, [116 * mm, 64 * mm, 46 * mm], header=True, font_size=7.4)


def _client_wrapped_table(
    rows: Sequence[Sequence[Any]],
    col_widths: Sequence[float],
    *,
    header: bool = True,
    font_size: float = 7.6,
) -> Table:
    """Client-facing table with wrapped Paragraph cells for long design text."""
    body_style = ParagraphStyle(
        "ClientTableBody",
        fontName="Helvetica",
        fontSize=font_size,
        leading=font_size + 1.6,
        textColor=colors.HexColor("#111111"),
        spaceBefore=0,
        spaceAfter=0,
    )
    header_style = ParagraphStyle(
        "ClientTableHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    converted: List[List[Any]] = []
    for row_index, row in enumerate(rows):
        style = header_style if header and row_index == 0 else body_style
        converted.append([Paragraph(_xml_escape(str(cell or "")), style) for cell in row])

    table = Table(converted, colWidths=list(col_widths), repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CCD3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE0")),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182230")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ])
        start = 1
    else:
        start = 0
    for row_index in range(start, len(converted)):
        if (row_index - start) % 2 == 1:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F7F8FA")))
    table.setStyle(TableStyle(commands))
    return table


def _change_trigger_bullets(room: Dict[str, Any]) -> List[str]:
    modality = str(room.get("modality", "") or "").upper()
    triggers = [
        "Any change to room dimensions, source position, adjacent-area use or occupancy.",
        "Any change to barrier construction, doors, glazing, penetrations or shielding continuity.",
        "Addition of radiation-producing equipment or a source not represented in this assessment.",
    ]
    if modality in {"PET", "SPECT"}:
        triggers.insert(0, "Any increase in administered activity, patient throughput or time spent in the assessed source position.")
    elif modality == "CT":
        triggers.insert(0, "Any change to scanner model, ksec basis, examination workload or scan technique assumptions.")
    return triggers


def _next_stage_information(payload: Dict[str, Any]) -> List[str]:
    project_type = str((payload.get("project", {}) or {}).get("project_type", "new_build") or "new_build").strip().lower()
    items = [
        "Current coordinated architectural drawings showing room dimensions, wall construction, doors, glazing and service penetrations.",
        "Confirmed use and occupancy of all adjacent areas, including above and below the room.",
        "Confirmed clinical workload/source assumptions and any additional radiation-producing equipment.",
    ]
    if project_type == "refurbishment":
        items.insert(1, "Evidence or site verification of existing wall, floor and ceiling construction and shielding thickness/equivalence.")
    return items


def _payload_report_wording(payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = payload.get("meta", {}) or {}
    raw = meta.get("report_wording", {}) or {}
    return {
        "report_title": str(raw.get("report_title", "Preliminary Shielding Schedule") or "Preliminary Shielding Schedule"),
        "report_subtitle": str(raw.get("report_subtitle", "Preliminary shielding assessment schedule") or "Preliminary shielding assessment schedule"),
        "cover_introduction": str(
            raw.get(
                "cover_introduction",
                "This output is intended as an internal calculation schedule to support early project pricing and design review. It is not a certified radiation shielding assessment report.",
            )
            or ""
        ),
        "limitations_heading": str(raw.get("limitations_heading", "Preliminary assessment limitations") or "Preliminary assessment limitations"),
        "limitation_bullets": [str(item) for item in list(raw.get("limitation_bullets", []) or [])],
        "room_schedule_prefix": str(raw.get("room_schedule_prefix", "Room schedule") or "Room schedule"),
        "room_layout_heading": str(raw.get("room_layout_heading", "Room layout") or "Room layout"),
        "barrier_schedule_heading": str(raw.get("barrier_schedule_heading", "Barrier schedule") or "Barrier schedule"),
        "source_inputs_heading": str(raw.get("source_inputs_heading", "Source inputs") or "Source inputs"),
    }


def _payload_report_wording_from_room(room: Dict[str, Any]) -> Dict[str, Any]:
    # Room payloads are embedded inside the top-level payload, but this helper
    # allows the room section to remain explicit and testable.  The report
    # generator attaches no CT-specific strings here; missing metadata falls
    # back to generic wording.
    return _payload_report_wording({"meta": room.get("report_meta", {}) or {}})


def _source_inputs_table(sources: Sequence[Dict[str, Any]]) -> Table:
    rows: List[List[str]] = [["Source", "Type", "Radiation / energy"]]
    for source in sources:
        rows.append([
            str(source.get("name", "") or ""),
            _human_source_type(source.get("source_type", "")),
            _human_radiation_type(source.get("radiation_type", "")),
        ])
    return styled_table(rows, [62 * mm, 48 * mm, 58 * mm], header=True)


# =====================================================# Barrier schedule table mirrors app Barriers tab
# =====================================================

PDF_BARRIER_COLUMNS = (
    "name",
    "thickness_mm",
    "barrier_role",
    "distance_m",
    "occupancy_factor",
    "design_goal_uSv_per_week",
    "unshielded_weekly_dose_uSv",
    "transmitted_dose_uSv_per_week",
    "barrier_transmission_factor_B",
    "display_required_thickness_mm",
    "solver_used",
    "compliance_status",
)

PDF_BARRIER_HEADINGS = {
    "name": "Barrier",
    "thickness_mm": "Actual (mm)",
    "barrier_role": "Role",
    "distance_m": "Distance (m)",
    "occupancy_factor": "T",
    "design_goal_uSv_per_week": "P (uSv/wk)",
    "unshielded_weekly_dose_uSv": "Unshielded (uSv/wk)",
    "transmitted_dose_uSv_per_week": "Transmitted (uSv/wk)",
    "barrier_transmission_factor_B": "B",
    "display_required_thickness_mm": "Required (mm)",
    "solver_used": "Solver",
    "compliance_status": "Status",
}

PDF_BARRIER_COLUMN_WIDTHS_MM = [18, 18, 24, 22, 11, 19, 28, 28, 14, 20, 29, 16]


def _human_solver_label(value: Any) -> str:
    raw = str(value or "").strip()
    mapping = {
        "spect_tc99m_practical_archer": "SPECT practical Archer",
        "pet_aapm_tg108": "PET AAPM TG-108",
    }
    if raw in mapping:
        return mapping[raw]
    return raw.replace("_", " ").strip()


def _barriers_tab_pdf_table(barrier_rows: List[Dict[str, Any]]) -> Table:
    """Render a concise, report-facing barrier schedule without internal engine fields."""
    header_style = ParagraphStyle(
        "BarrierTableHeader",
        fontName="Helvetica-Bold",
        fontSize=6.2,
        leading=6.8,
        textColor=colors.white,
        alignment=0,
        spaceAfter=0,
        spaceBefore=0,
    )
    rows: List[List[Any]] = [
        [Paragraph(PDF_BARRIER_HEADINGS.get(col, col), header_style) for col in PDF_BARRIER_COLUMNS]
    ]

    for row in barrier_rows:
        rows.append([_fmt_barriers_tab_cell(row, col) for col in PDF_BARRIER_COLUMNS])

    if len(rows) == 1:
        rows.append(["No barrier rows"] + [""] * (len(PDF_BARRIER_COLUMNS) - 1))

    col_widths = [w * mm for w in PDF_BARRIER_COLUMN_WIDTHS_MM]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.6),
        ("LEADING", (0, 0), (-1, -1), 7.4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CCD3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE0")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182230")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 6.2),
    ]

    numeric_columns = {
        "thickness_mm", "distance_m", "occupancy_factor",
        "design_goal_uSv_per_week", "unshielded_weekly_dose_uSv",
        "transmitted_dose_uSv_per_week", "barrier_transmission_factor_B",
        "display_required_thickness_mm",
    }
    for col_idx, col in enumerate(PDF_BARRIER_COLUMNS):
        if col in numeric_columns:
            style.append(("ALIGN", (col_idx, 1), (col_idx, -1), "RIGHT"))

    status_col = PDF_BARRIER_COLUMNS.index("compliance_status")
    for row_idx, row in enumerate(barrier_rows, start=1):
        status = str(row.get("compliance_status") or row.get("status") or "").strip().upper()
        if status == "FAIL":
            bg = colors.HexColor("#FADADA")
            fg = colors.HexColor("#A32121")
        elif status == "REVIEW":
            bg = colors.HexColor("#FFF1C7")
            fg = colors.HexColor("#9A6A00")
        else:
            bg = colors.HexColor("#E6F4EA")
            fg = colors.HexColor("#1D6B43")
        style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))
        style.append(("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), fg))
        style.append(("FONTNAME", (status_col, row_idx), (status_col, row_idx), "Helvetica-Bold"))
        style.append(("ALIGN", (status_col, row_idx), (status_col, row_idx), "CENTER"))

    table.setStyle(TableStyle(style))
    return table


def _fmt_barriers_tab_cell(row: Dict[str, Any], col: str) -> str:
    if col == "barrier_role":
        return _human_barrier_role(row.get(col, ""))
    if col == "compliance_status":
        return str(row.get(col) or row.get("status") or "").strip().upper()
    if col in {"thickness_mm", "display_required_thickness_mm"}:
        return _fmt_pdf_number(row.get(col), 2)
    if col == "distance_m":
        return _fmt_pdf_number(row.get(col), 2)
    if col == "occupancy_factor":
        return _fmt_pdf_number(row.get(col), 3)
    if col in {"design_goal_uSv_per_week", "unshielded_weekly_dose_uSv", "transmitted_dose_uSv_per_week"}:
        return _fmt_pdf_number(row.get(col), 3)
    if col == "barrier_transmission_factor_B":
        return _fmt_pdf_number(row.get(col), 6)
    if col == "solver_used":
        return str(row.get(col, "") or "")
    return str(row.get(col, "") or "")

def _section_preliminary_limitations(payload: Dict[str, Any], styles: StyleSheet1, section_number: int) -> List[Any]:
    modality = _report_modality(payload)
    bullets = _modality_specific_limitations(modality)
    flow: List[Any] = [
        Paragraph(f"{section_number}. Conclusion", styles["Subheading"]),
    ]
    for item in bullets:
        flow.append(_bullet_para(item, styles))
        flow.append(Spacer(1, 1.2 * mm))
    return flow


def _report_modality(payload: Dict[str, Any]) -> str:
    rooms = list(payload.get("rooms", []) or [])
    values = [str(room.get("modality", "") or "").strip().upper() for room in rooms if isinstance(room, dict)]
    values = [value for value in values if value]
    if values:
        return values[0]
    return str((payload.get("project", {}) or {}).get("modality", "") or "").strip().upper()


def _modality_specific_limitations(modality: str) -> List[str]:
    m = str(modality or "").strip().upper()
    common = [
        "This document is a preliminary shielding assessment for design development and shielding review; it is not a final shielding compliance certificate.",
        "Final shielding acceptance requires professional review of architectural drawings, construction details, source and workload assumptions, occupancy assumptions, and installed materials.",
        "Calculated results depend on the entered room geometry, source position, operating assumptions, design goals, occupancy factors, and barrier construction.",
    ]
    if m == "X-RAY":
        return common + [
            "General radiography results use the NCRP Report No. 147 Section 5.3 / Figure 5.2 radiographic-room methodology with project-specific barrier distances.",
            "Primary-beam pre-shielding is explicit for the floor, chest-bucky and cross-table scenarios; cross-table lateral shielding combines transmitted primary and secondary air kerma iteratively.",
            "Changes to examination workload, tube potential, source or wall-bucky position, primary-beam use, occupancy, design goals or barrier construction require reassessment.",
            "Issueable Preliminary Shielding Assessment output is limited to the qualified NCRP 147 General Radiography pathway; unsupported or manual X-ray configurations require separate assessment.",
        ]
    if m == "CT":
        return common + [
            "CT results depend on the selected scanner model or verified ksec basis, examination workload, scan technique assumptions, and room geometry.",
            "Any manual ksec override must be independently verified before final certification.",
        ]
    if "PET" in m:
        return common + [
            "PET results depend on the selected radionuclide, administered activity, patient throughput, uptake and imaging assumptions, source location, and occupancy model.",
            "Any additional radiation-producing equipment or operational source not represented in this assessment requires separate evaluation before final acceptance.",
        ]
    if "SPECT" in m:
        return common + [
            "SPECT results depend on the selected radionuclide, administered activity, patient throughput and timing assumptions, source location, and occupancy model.",
            "Any additional radiation-producing equipment or operational source not represented in this assessment requires separate evaluation before final acceptance.",
        ]
    return common



def _payload_modality(payload: Dict[str, Any]) -> str:
    rooms = list(payload.get("rooms", []) or [])
    modalities = []
    for room in rooms:
        value = str(room.get("modality", "") or "").strip().upper()
        if value and value not in modalities:
            modalities.append(value)
    if len(modalities) == 1:
        return modalities[0]
    if modalities:
        return " / ".join(modalities)
    return str((payload.get("project", {}) or {}).get("modality", "") or "Not stated")


def _preliminary_display_title(payload: Dict[str, Any], fallback: str) -> str:
    modality = _payload_modality(payload)
    if modality and modality != "Not stated":
        return f"Preliminary Shielding Assessment - {modality}"
    return fallback

def _human_project_type(value: Any) -> str:
    return "Refurbishment" if str(value or "").strip().lower() == "refurbishment" else "New build"


def _human_barrier_role(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "secondary_wall": "Secondary wall",
        "primary_wall": "Primary wall",
        "wall": "Wall",
        "floor": "Floor",
        "ceiling": "Ceiling",
        "door": "Door",
        "viewing_panel": "Viewing panel",
        "lead_glass": "Viewing panel",
    }
    return mapping.get(raw, raw.replace("_", " ").title())


def _human_source_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "spect_patient": "SPECT patient",
        "pet_patient": "PET patient",
        "ct_scatter": "CT scatter",
        "xray_primary": "X-ray primary",
    }
    return mapping.get(raw, raw.replace("_", " ").title())


def _human_radiation_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "tc99m_140kev": "Tc-99m (140 keV)",
        "tc_99m_140kev": "Tc-99m (140 keV)",
        "f18_511kev": "F-18 (511 keV)",
        "18f_511kev": "F-18 (511 keV)",
        "ga68_511kev": "Ga-68 (511 keV)",
        "lu177": "Lu-177",
        "i131": "I-131",
    }
    if raw in mapping:
        return mapping[raw]
    return str(value or "").replace("_", " ").strip()

def _fmt_pdf_number(value: Any, decimals: int = 2) -> str:
    try:
        if value in (None, ""):
            return ""
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value or "")


def _provided_pdf(row: Dict[str, Any]) -> str:
    material = str(row.get("material", "") or "")
    value = _fmt_pdf_number(row.get("provided_thickness_mm"), 2 if material == "Pb" else 1)
    return f"{value} mm {material}".strip() if value else material


def _required_pdf(row: Dict[str, Any]) -> str:
    material = str(row.get("material", "") or "")
    if material == "Concrete" and row.get("required_concrete_mm") not in (None, ""):
        return f"{_fmt_pdf_number(row.get('required_concrete_mm'), 1)} mm Concrete"
    if row.get("required_lead_mm") not in (None, ""):
        return f"{_fmt_pdf_number(row.get('required_lead_mm'), 2)} mm Pb"
    if row.get("required_thickness_mm") not in (None, ""):
        return f"{_fmt_pdf_number(row.get('required_thickness_mm'), 2)} mm {material}".strip()
    return ""


class _RoomLayoutFlowable(Flowable):
    """ReportLab rendition of the Geometry tab canvas.

    The PDF layout deliberately mirrors the Tk geometry canvas rather than using
    a separate simplified room sketch.  The drawing uses the same fixed 12 m x
    8 m design field, 1 m / 0.2 m grid, wall/opening risk colours, wall labels,
    floor/ceiling labels, source circle, CT scanner/table symbol, source dose
    annotation, room title, and scale marker conventions used by the Geometry
    tab.

    This keeps the report graphic visually aligned with the on-screen Geometry
    canvas while avoiding fragile screenshot or Tk PostScript export behaviour.
    """

    DESIGN_FIELD_WIDTH_M = 12.0
    DESIGN_FIELD_HEIGHT_M = 8.0

    def __init__(self, room_payload: Dict[str, Any], width: float, height: float):
        super().__init__()
        self.room = room_payload or {}
        self.geometry = (self.room.get("geometry", {}) or {}) if isinstance(self.room, dict) else {}
        self.width = width
        self.height = height
        self.hAlign = "CENTER"
        self._scale = 1.0
        self._field_x0 = 0.0
        self._field_y0 = 0.0
        self._room_x0 = 0.0
        self._room_y0 = 0.0
        self._room_x1 = 0.0
        self._room_y1 = 0.0
        self._risk_by_name = self._build_risk_map()
        self._rows_by_name = self._build_row_map()

    def draw(self) -> None:
        c = self.canv
        geom = self.geometry
        room_w = _layout_float(geom.get("width_m"), 5.0) or 5.0
        room_l = _layout_float(geom.get("length_m"), 5.0) or 5.0
        if room_w <= 0 or room_l <= 0:
            self._draw_text(self.width / 2, self.height / 2, "Enter valid room dimensions", anchor="center", fill=COLOUR_ALERT, size=8, bold=True)
            return

        self._configure_geometry(room_w, room_l)

        c.saveState()
        self._draw_grid()
        self._draw_room_outline()
        self._draw_wall_labels(room_w, room_l)
        self._draw_floor_ceiling_labels()
        self._draw_status_legend()
        self._draw_room_title(room_w, room_l)
        self._draw_scale_marker(metres=2)
        self._draw_openings(room_w, room_l)
        self._draw_source_and_scanner(room_w, room_l)
        c.restoreState()

    # ------------------------------------------------------------------
    # Geometry and low-level drawing helpers
    # ------------------------------------------------------------------

    def _configure_geometry(self, room_w: float, room_l: float) -> None:
        pad = 3 * mm
        drawable_w = max(1.0, self.width - 2 * pad)
        drawable_h = max(1.0, self.height - 2 * pad)
        self._scale = min(
            drawable_w / self.DESIGN_FIELD_WIDTH_M,
            drawable_h / self.DESIGN_FIELD_HEIGHT_M,
        )

        field_w = self.DESIGN_FIELD_WIDTH_M * self._scale
        field_h = self.DESIGN_FIELD_HEIGHT_M * self._scale
        self._field_x0 = (self.width - field_w) / 2
        self._field_y0 = (self.height - field_h) / 2

        room_w_px = room_w * self._scale
        room_h_px = room_l * self._scale
        self._room_x0 = self._field_x0 + (field_w - room_w_px) / 2
        self._room_y0 = self._field_y0 + (field_h - room_h_px) / 2
        self._room_x1 = self._room_x0 + room_w_px
        self._room_y1 = self._room_y0 + room_h_px

    def _map_point(self, x_m: float, y_m_from_south: float) -> Tuple[float, float]:
        return (
            self._room_x0 + x_m * self._scale,
            self._room_y1 - y_m_from_south * self._scale,
        )

    def _to_rl(self, x: float, y_down: float) -> Tuple[float, float]:
        return x, self.height - y_down

    def _line(self, x0: float, y0: float, x1: float, y1: float, *, fill: str, width: float = 1, dash: Optional[Tuple[int, ...]] = None) -> None:
        c = self.canv
        c.setStrokeColor(_pdf_colour(fill))
        c.setLineWidth(width)
        if dash:
            c.setDash(dash)
        else:
            c.setDash()
        rx0, ry0 = self._to_rl(x0, y0)
        rx1, ry1 = self._to_rl(x1, y1)
        c.line(rx0, ry0, rx1, ry1)
        c.setDash()

    def _rect(self, x0: float, y0: float, x1: float, y1: float, *, outline: str, fill: Optional[str] = None, width: float = 1) -> None:
        c = self.canv
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        c.setLineWidth(width)
        c.setStrokeColor(_pdf_colour(outline))
        c.setFillColor(_pdf_colour(fill or COLOUR_CANVAS_BG))
        c.rect(left, self.height - bottom, right - left, bottom - top, stroke=1, fill=1 if fill else 0)

    def _rounded_rect(self, x0: float, y0: float, x1: float, y1: float, *, radius: float, outline: str, width: float = 1) -> None:
        c = self.canv
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        c.setLineWidth(width)
        c.setStrokeColor(_pdf_colour(outline))
        c.roundRect(left, self.height - bottom, right - left, bottom - top, radius, stroke=1, fill=0)

    def _circle(
        self,
        cx: float,
        cy_down: float,
        radius: float,
        *,
        outline: str,
        fill: Optional[str] = None,
        width: float = 1,
        dash: Optional[Tuple[float, ...]] = None,
    ) -> None:
        c = self.canv
        x, y = self._to_rl(cx, cy_down)
        c.saveState()
        c.setLineWidth(width)
        c.setStrokeColor(_pdf_colour(outline))
        c.setFillColor(_pdf_colour(fill or COLOUR_CANVAS_BG))
        if dash:
            c.setDash(*dash)
        c.circle(x, y, radius, stroke=1, fill=1 if fill else 0)
        c.restoreState()

    def _polygon(self, points: Sequence[Tuple[float, float]], *, outline: str, fill: str, width: float = 1) -> None:
        c = self.canv
        path = c.beginPath()
        first = True
        for x, y in points:
            rx, ry = self._to_rl(x, y)
            if first:
                path.moveTo(rx, ry)
                first = False
            else:
                path.lineTo(rx, ry)
        path.close()
        c.setLineWidth(width)
        c.setStrokeColor(_pdf_colour(outline))
        c.setFillColor(_pdf_colour(fill))
        c.drawPath(path, stroke=1, fill=1)

    def _draw_text(
        self,
        x: float,
        y_down: float,
        text: str,
        *,
        anchor: str = "center",
        fill: str = COLOUR_TEXT,
        size: float = 6.8,
        bold: bool = False,
        justify: str = "center",
        angle: float = 0.0,
        line_spacing: Optional[float] = None,
    ) -> None:
        if text is None:
            return
        lines = str(text).splitlines() or [""]
        line_spacing = line_spacing or (size + 2.0)
        c = self.canv
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFillColor(_pdf_colour(fill))
        c.setFont(font, size)

        if anchor in {"center", "n", "s"}:
            align = "center"
        elif anchor in {"e", "ne", "se"}:
            align = "right"
        elif anchor in {"w", "nw", "sw"}:
            align = "left"
        else:
            align = justify

        total_h = line_spacing * (len(lines) - 1)
        start_y = y_down - total_h / 2
        if anchor in {"n", "ne", "nw"}:
            start_y = y_down
        elif anchor in {"s", "se", "sw"}:
            start_y = y_down - total_h

        c.saveState()
        rx, ry = self._to_rl(x, start_y)
        c.translate(rx, ry)
        if angle:
            c.rotate(angle)
        for i, line in enumerate(lines):
            y_line = -i * line_spacing
            if align == "center":
                c.drawCentredString(0, y_line, line)
            elif align == "right":
                c.drawRightString(0, y_line, line)
            else:
                c.drawString(0, y_line, line)
        c.restoreState()

    # ------------------------------------------------------------------
    # Canvas-equivalent drawing primitives
    # ------------------------------------------------------------------

    def _draw_grid(self) -> None:
        field_x0 = self._field_x0
        field_y0 = self._field_y0
        field_x1 = field_x0 + self.DESIGN_FIELD_WIDTH_M * self._scale
        field_y1 = field_y0 + self.DESIGN_FIELD_HEIGHT_M * self._scale
        major = self._scale
        minor = self._scale * 0.2

        x = field_x0
        while x <= field_x1 + 0.1:
            self._line(x, field_y0, x, field_y1, fill=COLOUR_GRID_MAJOR, width=0.55)
            if x + major <= field_x1 + 0.1:
                for i in range(1, 5):
                    mx = x + i * minor
                    if mx < field_x1:
                        self._line(mx, field_y0, mx, field_y1, fill=COLOUR_GRID_MINOR, width=0.3)
            x += major

        y = field_y0
        while y <= field_y1 + 0.1:
            self._line(field_x0, y, field_x1, y, fill=COLOUR_GRID_MAJOR, width=0.55)
            if y + major <= field_y1 + 0.1:
                for i in range(1, 5):
                    my = y + i * minor
                    if my < field_y1:
                        self._line(field_x0, my, field_x1, my, fill=COLOUR_GRID_MINOR, width=0.3)
            y += major

    def _draw_room_outline(self) -> None:
        self._rect(
            self._room_x0,
            self._room_y0,
            self._room_x1,
            self._room_y1,
            outline=COLOUR_OUTLINE,
            width=max(0.8, ROOM_OUTLINE_WIDTH * 0.45),
        )

        # Risk-coloured wall overlays match GeometryTab._draw_current_room().
        w = max(1.3, BARRIER_OVERLAY_WIDTH * 0.42)
        self._line(self._room_x0, self._room_y0, self._room_x1, self._room_y0, fill=self._risk_colour("N wall"), width=w)
        self._line(self._room_x1, self._room_y0, self._room_x1, self._room_y1, fill=self._risk_colour("E wall"), width=w)
        self._line(self._room_x0, self._room_y1, self._room_x1, self._room_y1, fill=self._risk_colour("S wall"), width=w)
        self._line(self._room_x0, self._room_y0, self._room_x0, self._room_y1, fill=self._risk_colour("W wall"), width=w)

    def _draw_wall_labels(self, room_w: float, room_l: float) -> None:
        cx = (self._room_x0 + self._room_x1) / 2
        cy = (self._room_y0 + self._room_y1) / 2
        for wall, x, y, anchor in (
            # North/South blocks use edge anchors so their full multi-line text
            # maintains a consistent clearance from the room outline.
            ("N", cx, self._room_y0 - 5, "s"),
            ("S", cx, self._room_y1 + 5, "n"),
            ("E", self._room_x1 + WALL_LABEL_OFFSET_EW * 0.55, cy, "w"),
            ("W", self._room_x0 - WALL_LABEL_OFFSET_EW * 0.55, cy, "e"),
        ):
            name = f"{wall} wall"
            lines = [wall]
            row = self._rows_by_name.get(name.lower(), {})
            t = row.get("occupancy_factor")
            p = row.get("design_goal_uSv_per_week")
            material = self._material_label(row)
            dose = self._dose_label(row)
            if t not in (None, ""):
                lines.append(f"T={_compact_float(t)}")
            if p not in (None, ""):
                lines.append(f"P={_compact_float(p)} µSv/wk")
            if material:
                lines.append(material)
            if dose:
                lines.extend(dose.splitlines())

            self._draw_text(
                x,
                y,
                "\n".join(lines),
                anchor=anchor,
                fill=self._risk_colour(name),
                size=4.9,
                bold=True,
                line_spacing=5.0,
            )

    def _draw_floor_ceiling_labels(self) -> None:
        ceiling = self._rows_by_name.get("ceiling", {})
        floor = self._rows_by_name.get("floor", {})
        y = self._field_y0 + 0.55 * self._scale
        self._draw_planar_label("Ceiling", ceiling, self._field_x0 + 0.75 * self._scale, y, "w")
        self._draw_planar_label("Floor", floor, self._field_x0 + self.DESIGN_FIELD_WIDTH_M * self._scale - 0.75 * self._scale, y, "e")

    def _draw_planar_label(self, label: str, row: Dict[str, Any], x: float, y: float, anchor: str) -> None:
        lines = [label]
        if row:
            t = row.get("occupancy_factor")
            p = row.get("design_goal_uSv_per_week")
            material = self._material_label(row)
            dose = self._dose_label(row)
            if t not in (None, ""):
                lines.append(f"T={_compact_float(t)}")
            if p not in (None, ""):
                lines.append(f"P={_compact_float(p)} µSv/wk")
            if material:
                lines.append(material)
            if dose:
                lines.extend(dose.splitlines())
        self._draw_text(x, y, "\n".join(lines), anchor=anchor, fill=self._risk_colour(label), size=4.7, bold=True, line_spacing=5.0)

    def _draw_status_legend(self) -> None:
        x = self._field_x0 + self.DESIGN_FIELD_WIDTH_M * self._scale - 2 * self._scale
        scale_y = self._field_y0 + self.DESIGN_FIELD_HEIGHT_M * self._scale - 0.36 * self._scale
        # Position the legend with approximately 5 mm clear space above the Scale label.
        y = scale_y - (12 * mm)
        self._draw_text(x, y, "Legend", anchor="sw", fill=COLOUR_TEXT_MUTED, size=5.6)

        items = [
            ("PASS", COLOUR_PASS),
            ("REVIEW", COLOUR_REVIEW_DARK),
            ("FAIL", COLOUR_FAIL),
        ]
        item_y = y + 10
        box_size = 5.2
        cursor_x = x
        text_gap = 3.2
        item_gap = 10.0

        for label, colour in items:
            self._rect(
                cursor_x,
                item_y - box_size + 0.6,
                cursor_x + box_size,
                item_y + 0.6,
                outline=colour,
                fill=colour,
                width=0.3,
            )
            label_x = cursor_x + box_size + text_gap
            self._draw_text(label_x, item_y, label, anchor="sw", fill=COLOUR_TEXT, size=5.2, bold=True)
            label_width = max(12.0, len(label) * 3.4)
            cursor_x = label_x + label_width + item_gap

    def _draw_room_title(self, room_w: float, room_l: float) -> None:
        room_name = str(self.geometry.get("room_name") or self.room.get("name") or "Room")
        height = _layout_float(self.geometry.get("height_m"), None)
        x = self._field_x0 + 0.22 * self._scale
        y = self._field_y0 + self.DESIGN_FIELD_HEIGHT_M * self._scale - 0.42 * self._scale
        self._draw_text(x, y, room_name, anchor="sw", fill=COLOUR_TEXT, size=7.2, bold=True)
        if height is not None:
            self._draw_text(x, y + 10, f"FFL to FCL: {height:.2f} m", anchor="sw", fill=COLOUR_TEXT_MUTED, size=5.6)

    def _draw_scale_marker(self, metres: int = 2) -> None:
        scale = self._scale
        bar_h = 4.0
        # Match the desktop geometry canvas: right-align the 2 m bar to the
        # design-field grid so the 0, 1 and 2 m ticks sit on major grid lines.
        x = self._field_x0 + self.DESIGN_FIELD_WIDTH_M * scale - metres * scale
        y = self._field_y0 + self.DESIGN_FIELD_HEIGHT_M * scale - 0.36 * scale
        self._draw_text(x, y - 6, "Scale: 1 m", anchor="sw", fill=COLOUR_TEXT_MUTED, size=5.5)
        for i in range(metres):
            self._rect(x + i * scale, y, x + (i + 1) * scale, y + bar_h, outline=COLOUR_TEXT, fill=(COLOUR_TEXT if i % 2 == 0 else COLOUR_CANVAS_BG), width=0.4)
        for i in range(metres + 1):
            tx = x + i * scale
            self._line(tx, y + bar_h, tx, y + bar_h + 3.5, fill=COLOUR_TEXT, width=0.35)
            self._draw_text(tx, y + bar_h + 9, str(i), anchor="n", fill=COLOUR_TEXT, size=4.8)
        self._draw_text(x + metres * scale + 8, y + bar_h + 9, "m", anchor="nw", fill=COLOUR_TEXT, size=4.8, bold=True)

    def _draw_openings(self, room_w: float, room_l: float) -> None:
        openings = list(self.geometry.get("openings", []) or [])
        for idx, opening in enumerate(openings, start=1):
            wall = str(opening.get("wall", "") or "").strip().upper()[:1]
            if wall not in {"N", "E", "S", "W"}:
                continue
            width_m = max(0.0, _layout_float(opening.get("width_m"), 0.9) or 0.9)
            centre_m = _layout_float(opening.get("centre_m"), None)
            if centre_m is None:
                centre_m = _layout_float(opening.get("offset_m"), None)
            max_len = room_w if wall in {"N", "S"} else room_l
            half_width_m = width_m / 2.0
            centre = centre_m if centre_m is not None else max_len / 2.0
            centre = max(half_width_m, min(centre, max_len - half_width_m)) if max_len > 0 else centre
            start = centre - half_width_m
            end = centre + half_width_m
            if wall == "N":
                p0 = self._map_point(start, room_l)
                p1 = self._map_point(end, room_l)
            elif wall == "S":
                p0 = self._map_point(start, 0)
                p1 = self._map_point(end, 0)
            elif wall == "E":
                p0 = self._map_point(room_w, start)
                p1 = self._map_point(room_w, end)
            else:
                p0 = self._map_point(0, start)
                p1 = self._map_point(0, end)

            oid = self._opening_id(opening, idx)
            row = self._rows_by_name.get(oid.lower(), {})
            colour = self._risk_colour(oid)
            half_px = max(1.1, OPENING_THICKNESS_PX * 0.35) / 2
            x_a, y_a = p0
            x_b, y_b = p1
            if wall in {"N", "S"}:
                self._rect(min(x_a, x_b), y_a - half_px, max(x_a, x_b), y_a + half_px, outline=colour, fill=colour, width=0.2)
            else:
                self._rect(x_a - half_px, min(y_a, y_b), x_a + half_px, max(y_a, y_b), outline=colour, fill=colour, width=0.2)

            mid_x = (p0[0] + p1[0]) / 2
            mid_y = (p0[1] + p1[1]) / 2
            material = str(opening.get("material", "") or row.get("material", "") or "").strip()
            pb = _layout_float(opening.get("pb_equiv_mm"), row.get("provided_thickness_mm"))
            lines = [oid]
            if material:
                lines.append(material)
            if pb not in (None, "") and pb and pb > 0:
                lines.append(f"Pb eq {pb:g} mm")
            dose = self._dose_label(row)
            if dose:
                lines.extend(dose.splitlines())

            if wall == "N":
                lx, ly, anchor = mid_x, mid_y + 22, "center"
            elif wall == "S":
                lx, ly, anchor = mid_x, mid_y - 22, "center"
            elif wall == "E":
                lx, ly, anchor = mid_x - 7, mid_y, "e"
            else:
                lx, ly, anchor = mid_x + 7, mid_y, "w"
            self._draw_text(lx, ly, "\n".join(lines), anchor=anchor, fill=colour, size=4.8, bold=True, line_spacing=5.0)

    def _draw_source_and_scanner(self, room_w: float, room_l: float) -> None:
        source = self.geometry.get("source", {}) or {}
        rendering = self.geometry.get("rendering", {}) or {}
        sx_m = _layout_float(source.get("x_m"), room_w / 2) or room_w / 2
        sy_m = _layout_float(source.get("y_m"), room_l / 2) or room_l / 2
        sx_m = max(0.0, min(sx_m, room_w))
        sy_m = max(0.0, min(sy_m, room_l))
        iso_x, iso_y = self._map_point(sx_m, sy_m)
        rotation = int(_layout_float(source.get("rotation_deg"), 0) or 0) % 360
        source_label = str(source.get("label", "") or "Source").strip()

        marker_points = resolve_source_marker_points(iso_x, iso_y, self._scale, rotation, rendering)
        reference_x, reference_y = marker_points.reference_circle
        reference_radius = float(rendering.get("reference_circle_radius_m", 1.0) or 1.0) * self._scale

        if bool(rendering.get("show_one_m_circle", True)):
            self._circle(reference_x, reference_y, reference_radius, outline=COLOUR_ALERT, width=0.7, dash=(4.0, 3.0))

        # Use the same visible 1 m dose annotation as the desktop canvas.
        # CT derives it from ksec/workload; PET/SPECT use the already-calculated
        # report barrier result (unshielded dose at barrier x distance^2).
        label = ""
        if str(rendering.get("annotation_kind", "") or "") == "ct_weekly_scatter":
            label = self._ct_weekly_scatter_label()
        else:
            label = self._patient_weekly_one_m_label()
        if label:
            label_gap = float(rendering.get("reference_circle_label_gap_px", 10.0) or 0.0)
            self._draw_text(
                reference_x,
                reference_y - reference_radius - label_gap,
                label,
                anchor="center",
                fill=COLOUR_ALERT,
                size=5.6,
                bold=True,
                line_spacing=5.4,
            )

        symbol_kind = str(rendering.get("source_symbol_kind", "point_source") or "point_source")
        if symbol_kind == "ct_scanner":
            self._draw_equipment_symbol(*marker_points.source, rotation, source_label, rendering)
        elif symbol_kind == "xray_machine":
            self._draw_xray_machine_symbol(*marker_points.source, rotation, source_label)

        if bool(rendering.get("show_radiation_symbol", True)):
            self._draw_radiation_symbol(*marker_points.radiation, radius=8.5)
        if bool(rendering.get("show_patient_symbol", False)):
            self._draw_nm_patient_symbol(
                *marker_points.patient,
                label=self._patient_source_label(rendering),
                label_offset=float(rendering.get("patient_label_offset_px", 42.0) or 42.0),
            )

    def _draw_nm_patient_symbol(self, px: float, py: float, *, label: str = "", label_offset: float = 42.0) -> None:
        """ReportLab equivalent of geometry.canvas_symbols.draw_nm_patient_icon."""
        outline = "#dc2626"
        y_scale = 0.8
        # Tk canvas symbol coordinates are pixel based. Scale them down for the
        # report canvas while preserving the exact silhouette proportions.
        sf = 0.42 * 1.2

        def pt(dx: float, dy: float) -> Tuple[float, float]:
            return px + dx * sf, py + dy * y_scale * sf

        head_r = 9.0 * sf
        head_x, head_y = pt(0.0, -30.0)
        self._circle(head_x, head_y, head_r, outline=outline, width=0.85)

        left_outline = [
            (-4,-22),(-7,-20),(-17,-15),(-23,-4),(-24,10),(-22,24),(-18,38),(-21,52),
            (-18,49),(-15,40),(-12,17),(-10,3),(-8,16),(-8,30),(-10,50),(-10,72),
            (-7,92),(-5,112),(-5,132),(-7,150),(-11,162),(-8,166),(-2,166),
        ]
        right_outline = [(-dx, dy) for dx, dy in left_outline]
        left_inner_leg = [(-2,72),(-1,96),(-1,122),(-3,150),(-1.5,162)]
        right_inner_leg = [(2,72),(1,96),(1,122),(3,150),(1.5,162)]

        for seq in (left_outline, right_outline, left_inner_leg, right_inner_leg):
            points = [pt(dx, dy) for dx, dy in seq]
            for a, b in zip(points, points[1:]):
                self._line(a[0], a[1], b[0], b[1], fill=outline, width=0.85)

        if str(label or "").strip():
            self._draw_text(px, py - label_offset * sf, str(label).strip(), fill=outline, size=5.3, bold=True)

    def _draw_equipment_symbol(self, iso_x: float, iso_y: float, rotation: int, source_label: str, rendering: Dict[str, Any]) -> None:
        px_per_m = self._scale
        equipment_width = max(0.0, _layout_float(rendering.get("equipment_width_m"), 0.0) or 0.0) * px_per_m
        equipment_depth = max(0.0, _layout_float(rendering.get("equipment_depth_m"), 0.0) or 0.0) * px_per_m
        table_width = max(0.0, _layout_float(rendering.get("table_width_m"), 0.0) or 0.0) * px_per_m
        table_length = max(0.0, _layout_float(rendering.get("table_length_m"), 0.0) or 0.0) * px_per_m
        projection = max(0.0, _layout_float(rendering.get("projection_length_m"), 0.5) or 0.5) * px_per_m
        if equipment_width <= 0 or equipment_depth <= 0:
            return
        corner_r = max(2.0, 0.2 * px_per_m)

        def rot(dx: float, dy: float) -> Tuple[float, float]:
            if rotation == 0: return iso_x + dx, iso_y + dy
            if rotation == 90: return iso_x - dy, iso_y + dx
            if rotation == 180: return iso_x - dx, iso_y - dy
            if rotation == 270: return iso_x + dy, iso_y - dx
            return iso_x + dx, iso_y + dy

        def rect_points(cx: float, cy: float, w: float, h: float) -> List[Tuple[float, float]]:
            return [rot(cx-w/2, cy-h/2), rot(cx+w/2, cy-h/2), rot(cx+w/2, cy+h/2), rot(cx-w/2, cy+h/2)]

        if rotation in {0, 180}:
            gx0, gy0 = rot(-equipment_width / 2, -equipment_depth / 2)
            gx1, gy1 = rot(equipment_width / 2, equipment_depth / 2)
            self._rounded_rect(gx0, gy0, gx1, gy1, radius=corner_r, outline=COLOUR_SCANNER, width=0.9)
        else:
            self._polygon(rect_points(0, 0, equipment_width, equipment_depth), outline=COLOUR_SCANNER, fill=COLOUR_CANVAS_BG, width=0.9)

        table_cy = equipment_depth / 2 + table_length / 2
        if table_width > 0 and table_length > 0:
            self._polygon(rect_points(0, table_cy, table_width, table_length), outline=COLOUR_SCANNER, fill=COLOUR_CANVAS_BG, width=0.9)

        hx0, hy0 = rot(-equipment_width / 2 - projection, 0)
        hx1, hy1 = rot(equipment_width / 2 + projection, 0)
        vx0, vy0 = rot(0, -equipment_depth / 2 - projection)
        vx1, vy1 = rot(0, equipment_depth / 2 + table_length + projection)
        self._line(hx0, hy0, hx1, hy1, fill=COLOUR_SCANNER, width=0.35, dash=(3, 2))
        self._line(vx0, vy0, vx1, vy1, fill=COLOUR_SCANNER, width=0.35, dash=(3, 2))

        label = source_label
        for phrase in list(rendering.get("label_cleanup_phrases", []) or []):
            label = label.replace(str(phrase), "").strip()
        separator = str(rendering.get("label_wrap_separator", " / ") or "")
        if separator:
            label = label.replace(separator, "\n" + separator.strip() + " ")
        if label:
            table_mid = rot(0, table_cy)
            self._draw_text(table_mid[0], table_mid[1], label[:48], anchor="center", fill=COLOUR_TEXT, size=5.3, angle=(rotation + 90) % 360, line_spacing=5.4)

    def _draw_xray_machine_symbol(self, iso_x: float, iso_y: float, rotation: int, source_label: str) -> None:
        size = 0.35 * self._scale
        self._circle(iso_x, iso_y, size, outline=COLOUR_SCANNER, fill=COLOUR_CANVAS_BG, width=0.9)
        if source_label:
            self._draw_text(iso_x, iso_y + size + 8, source_label[:32], anchor="center", fill=COLOUR_TEXT, size=5.3)

    def _draw_radiation_symbol(self, x: float, y: float, radius: float) -> None:
        import math
        bg_r = radius * 1.25
        self._circle(x, y, bg_r, outline="#111111", fill="#facc15", width=0.4)
        inner_r = radius * 0.42
        outer_r = radius * 1.05
        blade_half = math.radians(28)
        for angle_deg in (-90, 30, 150):
            a = math.radians(angle_deg)
            pts: List[Tuple[float, float]] = []
            for i in range(12):
                t = -blade_half + (2 * blade_half) * i / 11
                aa = a + t
                pts.append((x + outer_r * math.cos(aa), y + outer_r * math.sin(aa)))
            for i in range(11, -1, -1):
                t = -blade_half + (2 * blade_half) * i / 11
                aa = a + t
                pts.append((x + inner_r * math.cos(aa), y + inner_r * math.sin(aa)))
            self._polygon(pts, outline="#000000", fill="#000000", width=0.2)
        self._circle(x, y, radius * 0.28, outline="#000000", fill="#000000", width=0.1)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _build_row_map(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for row in list(self.room.get("barriers", []) or []):
            for key in (row.get("name"), row.get("barrier_id"), row.get("display_name")):
                if key not in (None, ""):
                    out[str(key).strip().lower()] = row
        return out

    def _build_risk_map(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for row in list(self.room.get("barriers", []) or []):
            status = str(row.get("status") or row.get("compliance_status") or "PASS").strip().upper()
            for key in (row.get("name"), row.get("barrier_id"), row.get("display_name")):
                if key not in (None, ""):
                    out[str(key).strip().lower()] = status
        return out

    def _risk_colour(self, name: str) -> str:
        state = str(self._risk_by_name.get(str(name).strip().lower(), "PASS")).lower()
        if state == "fail":
            return COLOUR_FAIL
        if state == "review":
            return COLOUR_REVIEW_DARK
        return COLOUR_PASS

    def _material_label(self, row: Dict[str, Any]) -> str:
        if not row:
            return ""
        material = str(row.get("material", "") or "").strip()
        provided = row.get("provided_thickness_mm")
        if provided not in (None, ""):
            try:
                val = float(provided)
                if material.lower() == "concrete":
                    return f"Concrete {val:.0f} mm"
                if "glass" in material.lower():
                    return f"Pb glass {val:g} mm"
                if material:
                    return f"{material} {val:g} mm"
            except Exception:
                pass
        return material

    def _dose_label(self, row: Dict[str, Any]) -> str:
        if not row:
            return ""
        tx = row.get("transmitted_dose_uSv_per_week")
        unsh = row.get("unshielded_weekly_dose_uSv")
        transmission_b = row.get("barrier_transmission_factor_B")
        if transmission_b in (None, ""):
            transmission_b = row.get("required_transmission")
        if transmission_b in (None, ""):
            transmission_b = row.get("transmission_factor_B")
        lines: List[str] = []
        if tx not in (None, ""):
            try:
                lines.append(f"Tx {_compact_float(tx)} µSv/wk")
            except Exception:
                pass
        if unsh not in (None, ""):
            try:
                lines.append(f"Unsh {_compact_float(unsh)} µSv/wk")
            except Exception:
                pass
        if transmission_b not in (None, ""):
            try:
                lines.append(f"B={float(transmission_b):.6f}")
            except Exception:
                pass
        return "\n".join(lines)

    def _opening_id(self, opening: Dict[str, Any], opening_index: int) -> str:
        explicit = str(opening.get("id", "") or "").strip()
        if explicit:
            return explicit
        raw_type = str(opening.get("opening_type", "") or "").strip().lower()
        is_vp = raw_type in {"viewing_panel", "lead_glass", "vp", "pb_glass"}
        return f"{'VP' if is_vp else 'D'}{opening_index}"

    def _patient_source_summary(self) -> Dict[str, Any]:
        route = self.room.get("pet_spect_report_route", {}) or {}
        payload = route.get("payload", {}) or {}
        summary = payload.get("source_summary", {}) or {}
        return summary if isinstance(summary, dict) else {}

    def _patient_source_label(self, rendering: Dict[str, Any]) -> str:
        summary = self._patient_source_summary()
        radionuclide = str(summary.get("radionuclide", "") or "").strip()
        # Match the desktop label convention: Tc99m -> Tc-99m, Ga68 -> Ga-68.
        import re
        match = re.fullmatch(r"([A-Za-z]+)-?(\d+[A-Za-z]*)", radionuclide)
        if match:
            radionuclide = f"{match.group(1)}-{match.group(2)}"
        activity = _layout_float(
            summary.get("administered_activity_mbq", summary.get("injected_activity_mbq_per_patient")),
            None,
        )
        if radionuclide and activity is not None and activity > 0:
            return f"{radionuclide} {activity:g} MBq"
        if radionuclide:
            return radionuclide
        return str(rendering.get("patient_marker_label", "") or "")

    def _patient_weekly_one_m_label(self) -> str:
        for row in list(self.room.get("barriers", []) or []):
            unshielded = _layout_float(row.get("unshielded_weekly_dose_uSv"), None)
            distance = _layout_float(row.get("distance_m"), None)
            if unshielded is not None and distance is not None and unshielded > 0 and distance > 0:
                weekly = unshielded * distance * distance
                return f"{weekly:.2f} µSv/wk @ 1 m"
        return ""

    def _ct_weekly_scatter_label(self) -> str:
        for source in list(self.room.get("sources", []) or []):
            stype = str(source.get("source_type", "") or "")
            if source_contribution_group(stype) != "ct_scatter":
                continue
            params = source.get("params", {}) or {}
            ksec = _layout_float(params.get("ksec_mGy_per_100mAs_at_1m"), None)
            scans = _layout_float(params.get("scans_per_week"), None)
            workload = _layout_float(params.get("workload_mAs_per_scan"), None)
            if ksec is not None and scans is not None and workload is not None and ksec > 0:
                weekly = ksec * (workload / 100.0) * scans * 1000.0
                return f"{weekly:.0f} µSv/wk @ 1 m"
        return ""


def _layout_float(value: Any, default: Optional[float]) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default



def _status_colour(status: str):
    s = _normalise_status(status)
    if s == "FAIL":
        return colors.HexColor("#A32121")
    if s == "REVIEW":
        return colors.HexColor("#9A6A00")
    return colors.HexColor("#1D6B43")


def _pdf_colour(value: Any):
    try:
        if isinstance(value, colors.Color):
            return value
        text = str(value or "").strip()
        if not text:
            return colors.black
        return colors.HexColor(text) if text.startswith("#") else colors.toColor(text)
    except Exception:
        return colors.black


def _compact_float(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return str(value or "")
    if abs(number) >= 100:
        return f"{number:.0f}"
    if abs(number) >= 10:
        return f"{number:.1f}".rstrip("0").rstrip(".")
    if abs(number) >= 1:
        return f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{number:.3f}".rstrip("0").rstrip(".")



class _ShieldingDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        self.addPageTemplates([
            PageTemplate(id="default", frames=[frame], onPage=self._draw_header_footer)
        ])
        self.meta_payload: Dict[str, Any] = {}

    def _draw_header_footer(self, canvas, doc):
        canvas.saveState()
        page_width, page_height = landscape(A4)
        meta = self.meta_payload.get("meta", {})
        project = self.meta_payload.get("project", {})

        header_y = page_height - 12 * mm
        footer_y = 12 * mm

        canvas.setStrokeColor(colors.HexColor("#D0D5DB"))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, header_y, page_width - doc.rightMargin, header_y)
        canvas.line(0, footer_y, page_width, footer_y)

        logo_path = meta.get("logo_path")
        if logo_path:
            try:
                canvas.drawImage(
                    logo_path,
                    doc.leftMargin,
                    page_height - 10.5 * mm,
                    width=8 * mm,
                    height=8 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                header_text_x = doc.leftMargin + 10 * mm
            except Exception:
                header_text_x = doc.leftMargin
        else:
            header_text_x = doc.leftMargin

        canvas.setFont("Helvetica-Bold", 8.8)
        canvas.setFillColor(colors.HexColor("#1F2A38"))
        report_title = _preliminary_display_title(self.meta_payload, str(meta.get("report_title", "")))
        canvas.drawString(header_text_x, page_height - 9 * mm, report_title[:85])

        canvas.setFont("Helvetica", 7.8)
        canvas.setFillColor(colors.HexColor("#5B6573"))
        canvas.drawRightString(
            page_width - doc.rightMargin,
            page_height - 9 * mm,
            str(project.get("project_name", ""))[:70],
        )

        footer_left = "healthphysics.com.au"
        project_type = _human_project_type(project.get("project_type", "new_build"))
        footer_mid = f"{meta.get('report_revision', '')} | {meta.get('report_status', '')} | {project_type}".strip(" |")
        footer_right = f"Page {doc.page}"

        footer_logo = Path(__file__).with_name("healthphysics_logo.jpg")
        footer_text_x = 10 * mm
        if footer_logo.exists():
            try:
                logo_w = 18 * mm
                logo_h = 8.5 * mm
                canvas.drawImage(
                    str(footer_logo),
                    10 * mm,
                    2.9 * mm,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    anchor="w",
                    mask="auto",
                )
                footer_text_x = 31 * mm
            except Exception:
                footer_text_x = 10 * mm

        canvas.drawString(footer_text_x, 8 * mm, footer_left)
        canvas.drawCentredString(page_width / 2, 8 * mm, footer_mid[:60])
        canvas.drawRightString(page_width - 10 * mm, 8 * mm, footer_right)
        canvas.restoreState()


# =====================================================# Sections
# =====================================================
def _section_cover(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    meta = payload["meta"]
    project = payload["project"]

    flow: List[Any] = []

    logo_path = meta.get("logo_path")
    if logo_path:
        try:
            flow.append(Image(logo_path, width=64 * mm, height=32 * mm))
            flow.append(Spacer(1, 14 * mm))
        except Exception:
            pass

    flow.append(Spacer(1, 22 * mm))
    flow.append(Paragraph(meta["report_title"], styles["CoverTitle"]))
    flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph(project["project_name"], styles["CoverProject"]))
    flow.append(Spacer(1, 16 * mm))

    cover_rows = [
        ["Client", project["client"]],
        ["Site", project["site"]],
        ["Assessor", project["assessor"]],
        ["Date", project["date"]],
        ["Revision", meta["report_revision"]],
        ["Status", meta["report_status"]],
    ]
    flow.append(styled_table(cover_rows, [34 * mm, 116 * mm], header=False))
    flow.append(Spacer(1, 8 * mm))
    flow.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D7DBE0")))
    flow.append(Spacer(1, 8 * mm))
    flow.append(Paragraph(
        "This report presents a radiation shielding assessment for the stated rooms, source models and operating assumptions.",
        styles["Body"],
    ))
    flow.append(Spacer(1, 6 * mm))
    flow.append(Paragraph(
        "Prepared in a formal consultancy reporting format suitable for technical review and project decision-making.",
        styles["Muted"],
    ))
    return flow

def _certificate_status_table(status: str) -> Table:
    # Certification labels may be longer than the simple barrier statuses
    # PASS/REVIEW/FAIL, e.g. "FAIL — NOT FOR CERTIFICATION". Do not collapse
    # these labels through _normalise_status(), otherwise they can incorrectly
    # render as green PASS.
    label = str(status or "").strip() or "UNKNOWN"
    status_text = label.upper()

    if any(token in status_text for token in ("FAIL", "INCOMPLETE", "ERROR", "NOT CERTIFIED", "NOT FOR CERTIFICATION")):
        bg = colors.HexColor("#A32121")
    elif any(token in status_text for token in ("REVIEW", "WARNING", "DRAFT")):
        bg = colors.HexColor("#9A6A00")
    elif "PASS" in status_text:
        bg = colors.HexColor("#1D6B43")
    else:
        bg = colors.HexColor("#4B5563")

    table = Table([[label]], colWidths=[170 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 18),
        ("LEADING", (0, 0), (-1, -1), 20),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.8, bg),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table

def _section_certificate(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    meta = payload["meta"]
    project = payload["project"]
    summary = payload["summary"]
    cert = payload.get("certification", {}) or {}

    overall_status = str(cert.get("assessment_status", "") or "PASS")
    if not cert:
        if summary.get("source_ksec_incomplete_count", 0) > 0:
            overall_status = "INCOMPLETE"
        elif summary.get("fail_count", 0) > 0:
            overall_status = "FAIL"
        elif summary.get("review_count", 0) > 0 or summary.get("source_ksec_manual_override_count", 0) > 0:
            overall_status = "REVIEW"

    title = cert.get("certificate_title") or (
        "Certificate of Shielding Compliance" if overall_status == "PASS" else "Shielding Assessment — Not Certified"
    )
    label = cert.get("label") or overall_status
    statement_heading = cert.get("statement_heading") or "Assessment statement"
    statement = cert.get("statement") or "Assessment status has been derived from the generated shielding results."
    statement_style = _certificate_statement_style(overall_status)
    validity_heading = cert.get("validity_heading") or "Conditions of validity"
    validity_points = list(cert.get("validity_points", []) or [])
    certification_allowed = bool(cert.get("certification_allowed", False))
    signature_allowed = bool(cert.get("signature_allowed", False))

    flow: List[Any] = []
    flow.append(Spacer(1, 8 * mm))
    flow.append(Paragraph(title, styles["CertificateTitle"]))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(project["project_name"], styles["CertificateSubtitle"]))
    flow.append(Spacer(1, 4 * mm))
    flow.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#C7CCD3")))
    flow.append(Spacer(1, 6 * mm))
    flow.append(_certificate_status_table(label))
    flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph(
        f"Assessment status: <b>{overall_status}</b>",
        styles["CertificateBody"]
    ))
    flow.append(Spacer(1, 3 * mm))

    if not certification_allowed:
        flow.append(Paragraph(
            (
                "<b>Important:</b> This output is not a final certificate of shielding compliance. "
                "It must remain draft/review-only until all listed issues are resolved and the report is intentionally issued as Final."
            ),
            styles["CertificateBody"],
        ))
        flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph(f"<b>{statement_heading}</b>", styles["Subheading"]))
    flow.append(Paragraph(statement, styles["CertificateBody"]))
    flow.append(Spacer(1, 4 * mm))

    status_label = "Certified status" if certification_allowed else "Report gate status"
    flow.append(Paragraph(f"{status_label}: <b>{label}</b>", styles[statement_style]))
    flow.append(Spacer(1, 6 * mm))

    cert_rows = [
        ["Project", project["project_name"]],
        ["Client", project["client"]],
        ["Site", project["site"]],
        ["Date issued", meta["date_issued"]],
        ["Revision", meta["report_revision"]],
        ["Requested report status", meta["report_status"]],
        ["Effective report status", cert.get("report_status_effective", meta.get("report_status_effective", meta["report_status"]))],
        ["Certification permitted", "Yes" if certification_allowed else "No"],
    ]
    flow.append(styled_table(cert_rows, [44 * mm, 106 * mm], header=False))
    flow.append(Spacer(1, 6 * mm))

    blocking_issues = list(cert.get("blocking_issues", []) or [])
    warnings = list(cert.get("warnings", []) or [])
    if blocking_issues or warnings:
        flow.append(Paragraph("Report gate issues", styles["Subheading"]))
        for item in blocking_issues[:8]:
            flow.append(_bullet_para(f"Blocking: {item}", styles))
        for item in warnings[:8]:
            flow.append(_bullet_para(f"Review: {item}", styles))
        flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph(validity_heading, styles["Subheading"]))
    if not validity_points:
        validity_points = [
            "This report applies only to the documented room layouts, barrier materials, installed shielding thicknesses and source workloads.",
            "Any change in equipment type, room configuration, workload, occupancy, adjacent area use or shielding construction may invalidate this assessment.",
            "Final regulatory acceptance remains subject to jurisdiction-specific installation and verification requirements.",
        ]
    for point in validity_points:
        flow.append(_bullet_para(point, styles))

    flow.append(Spacer(1, 10 * mm))
    if signature_allowed:
        sign_rows = [
            ["Prepared by", meta["prepared_by"]],
            ["Reviewed by", meta["reviewed_by"] or "—"],
            ["Date", meta["date_issued"]],
            ["Signature", ""],
        ]
    else:
        sign_rows = [
            ["Prepared by", meta["prepared_by"]],
            ["Reviewed by", meta["reviewed_by"] or "—"],
            ["Date", meta["date_issued"]],
            ["Signature", "Not available for draft/review/incomplete report"],
        ]
    flow.append(styled_table(sign_rows, [44 * mm, 106 * mm], header=False))
    return flow


def _certificate_statement_style(status: str) -> str:
    status = str(status or "").upper()
    if status in {"FAIL", "INCOMPLETE", "ERROR"}:
        return "StatusFail"
    if status in {"REVIEW", "DRAFT"}:
        return "StatusReview"
    return "StatusPass"


def _section_regulatory_basis(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("2. Regulatory Basis and Design Criteria", styles)]

    flow.append(Paragraph(
        (
            "This shielding assessment is framed against the adopted weekly design goals used within the "
            "project and the governing radiation protection methodology referenced by the assessment workflow."
        ),
        styles["Body"],
    ))
    flow.append(Spacer(1, 3 * mm))

    rows = [
        ["Topic", "Basis"],
        ["Primary methodology", "NCRP 147 broad-beam shielding framework with barrier transmission fitting approach."],
        ["Design objective", "Limit transmitted weekly dose beyond each barrier to the adopted design goal at the stated occupancy."],
        ["Controlled areas", "Use the controlled-area design goal defined in the project barrier schedule and room assumptions."],
        ["Uncontrolled areas", "Use the uncontrolled-area design goal defined in the project barrier schedule and room assumptions."],
        ["Conservatism", "Where applicable, conservative source, occupancy and shielding assumptions are retained."],
    ]
    flow.append(styled_table(rows, [42 * mm, 108 * mm], header=True))
    flow.append(Spacer(1, 5 * mm))

    bullets = [
        "The report should be read together with the room schedule, barrier schedule and per-barrier compliance statements.",
        "Barrier compliance is assessed using values exposed directly by the live physics engine outputs.",
        "The reported governing requirement for each barrier is the requirement controlling compliance under the stated conditions.",
        "This document does not certify undocumented future changes in use, occupancy or equipment configuration.",
    ]
    for text_item in bullets:
        flow.append(_bullet_para(text_item, styles))

    return flow

def _section_document_control(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    meta = payload["meta"]
    project = payload["project"]

    flow: List[Any] = [_section_heading("Document Control", styles)]

    doc_rows = [
        ["Report title", meta["report_title"]],
        ["Project name", project["project_name"]],
        ["Client", project["client"]],
        ["Site", project["site"]],
        ["Prepared by", meta["prepared_by"]],
        ["Reviewed by", meta["reviewed_by"]],
        ["Revision", meta["report_revision"]],
        ["Date issued", meta["date_issued"]],
        ["Status", meta["report_status"]],
    ]
    flow.append(styled_table(doc_rows, [42 * mm, 108 * mm], header=False))
    flow.append(Spacer(1, 6 * mm))

    rev_rows = [
        ["Rev", "Date", "Description", "Author"],
        [meta["report_revision"], meta["date_issued"], "Initial issue", meta["prepared_by"]],
    ]
    flow.append(Paragraph("Revision History", styles["Subheading"]))
    flow.append(styled_table(rev_rows, [18 * mm, 28 * mm, 90 * mm, 30 * mm], header=True))
    return flow

def _section_executive_summary(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    summary = payload["summary"]
    cert = payload.get("certification", {}) or {}

    presentation = report_presentation(payload)
    overall_status = presentation["overall_assessment_status"]

    flow: List[Any] = [_section_heading("1. Executive Summary", styles)]

    flow.append(Paragraph(
        (
            f"This report presents the formal shielding assessment outcome for "
            f"{summary['room_count']} room(s) and {summary['barrier_count']} barrier(s), "
            f"based on the current project geometry, barrier schedule, source models and adopted design goals."
        ),
        styles["Body"],
    ))
    flow.append(Spacer(1, 3 * mm))
    flow.append(_certificate_status_table(overall_status))
    flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph(
        (
            f"Assessment outcome: {summary['pass_count']} PASS, "
            f"{summary['review_count']} REVIEW, and {summary['fail_count']} FAIL."
        ),
        styles["Body"],
    ))
    flow.append(Spacer(1, 5 * mm))

    compliance_risk = presentation["compliance_risk"]

    flow.append(Paragraph(
        f"Compliance risk: <b>{compliance_risk}</b>",
        styles["Body"],
    ))
    flow.append(Spacer(1, 4 * mm))

    rows = [["Room", "Modality", "Barriers", "PASS", "REVIEW", "FAIL", "Overall"]]
    for row in payload["executive_rows"]:
        rows.append([
            row["room_name"],
            row["modality"],
            str(row["barriers_assessed"]),
            str(row["pass_count"]),
            str(row["review_count"]),
            str(row["fail_count"]),
            row["overall_status"],
        ])
    flow.append(styled_table(
        rows,
        [42 * mm, 24 * mm, 18 * mm, 16 * mm, 20 * mm, 16 * mm, 20 * mm],
        header=True,
        status_col=6,
    ))
    flow.append(Spacer(1, 5 * mm))

    top_actions = sorted(
        payload.get("action_rows", []),
        key=lambda x: (0 if x["status"] == "FAIL" else 1, x["room_name"], x["barrier_name"])
    )[:3]

    if top_actions:
        flow.append(Paragraph("Key design actions", styles["Subheading"]))
        for row in top_actions:
            flow.append(_bullet_para(
                f"{row['room_name']} / {row['barrier_name']} — {row['recommended_action']}",
                styles
            ))
        flow.append(Spacer(1, 3 * mm))

    flow.append(Paragraph(report_presentation(payload)["executive_conclusion_text"], styles["Body"]))
    return flow

def _section_scope(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    project = payload["project"]
    room_names = ", ".join(room["name"] for room in payload["rooms"]) or "None"

    flow: List[Any] = [_section_heading("3. Scope of Assessment", styles)]
    bullets = [
        f"Rooms included in this assessment: {room_names}.",
        f"Project-level design energy setting: {project['global_energy'] or 'Not stated'}.",
        f"Project-level solver mode: {project['solver_mode'] or 'Not stated'}.",
        "This report applies only to the room configurations, barrier data, source models and operating assumptions present in the project at the time of issue.",
        "Any change to room use, source workload, shielding material, barrier thickness or adjacent occupancy may require reassessment.",
    ]
    for text in bullets:
        flow.append(_bullet_para(text, styles))
    if project["notes"]:
        flow.append(Spacer(1, 4 * mm))
        flow.append(Paragraph("Project Notes", styles["Subheading"]))
        flow.append(Paragraph(project["notes"], styles["Body"]))
    return flow


def _section_source_data_and_inputs(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    project = payload["project"]
    summary = payload.get("summary", {}) or {}
    flow: List[Any] = [_section_heading("4. Source Data and Design Inputs", styles)]

    project_rows = [
        ["Project name", project["project_name"]],
        ["Global design energy", project["global_energy"]],
        ["Global solver mode", project["solver_mode"]],
        ["Project modality field", project["modality"]],
    ]
    flow.append(styled_table(project_rows, [45 * mm, 105 * mm], header=False))
    flow.append(Spacer(1, 6 * mm))

    rows = [["Room", "Modality", "Source name", "Source type", "Radiation type"]]
    for room in payload["rooms"]:
        for src in room["sources"]:
            rows.append([
                room["name"],
                room["modality"],
                src["name"],
                src["source_type"],
                src["radiation_type"],
            ])
    flow.append(styled_table(
        rows,
        [36 * mm, 24 * mm, 40 * mm, 30 * mm, 26 * mm],
        header=True,
    ))

    supplements = (payload.get("report_content", {}) or {}).get("source_input_supplements", []) or []
    for supplement in supplements:
        rows = [list(supplement.get("headings", []) or [])]
        rows.extend(list(row) for row in (supplement.get("rows", []) or []))
        if len(rows) <= 1:
            continue
        flow.append(Spacer(1, 6 * mm))
        flow.append(Paragraph(str(supplement.get("heading", "Source details") or "Source details"), styles["Subheading"]))
        widths = [float(value) * mm for value in (supplement.get("column_widths_mm", []) or [])]
        flow.append(styled_table(rows, widths or None, header=True))
        flow.append(Spacer(1, 4 * mm))
        for message in supplement.get("blocking_messages", []) or []:
            flow.append(Paragraph(str(message), styles["FailText"]))
            flow.append(Spacer(1, 2 * mm))
        for message in supplement.get("warning_messages", []) or []:
            flow.append(Paragraph(str(message), styles["Muted"]))

    return flow


def _section_methodology(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("5. Methodology", styles)]
    paras = [
        "The shielding assessment is based on weekly source workload, source model, distance, occupancy factor and the adopted design goal for each barrier.",
        "Barrier transmission and required shielding are taken directly from the live room-barrier solver outputs.",
        "Required barrier thicknesses are reported as lead and/or concrete equivalents where available from the live result set.",
    ]
    paras.extend((payload.get("report_content", {}) or {}).get("methodology_paragraphs", []) or [])
    for paragraph in paras:
        flow.append(Paragraph(str(paragraph), styles["Body"]))
        flow.append(Spacer(1, 2 * mm))

    rows = [["Element", "Method"]]
    rows.extend((payload.get("report_content", {}) or {}).get("methodology_rows", []) or [])
    rows.extend([
        ["Material conversion", "Lead and concrete required thickness values from the live result set."],
        ["Compliance basis", "Engine-reported compliance status against the adopted weekly design goal."],
    ])
    flow.append(Spacer(1, 3 * mm))
    flow.append(styled_table(rows, [34 * mm, 116 * mm], header=True))
    return flow


def _section_assumptions(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("6. Assumptions and Limitations", styles)]
    bullets = [
        "The assessment is valid only for the rooms, barriers, source models and workloads represented in the current project.",
        "Barrier performance assumes the stated shielding material and installed thickness are correct.",
        "Adjacent area classification and occupancy assumptions are taken from the project barrier schedule.",
        "The report does not apply to undocumented equipment relocation, changed workloads or altered adjacent occupancy without reassessment.",
        "Final construction should match the assessed design configuration.",
    ]
    bullets.extend((payload.get("report_content", {}) or {}).get("assumption_bullets", []) or [])
    for text in bullets:
        flow.append(_bullet_para(str(text), styles))
    return flow


def _section_room_schedule_summary(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("7. Room Schedule Summary", styles)]
    rows = [["Room", "Modality", "Classification", "Energy basis", "Solver basis", "Overall status"]]
    for room in payload["rooms"]:
        rows.append([
            room["name"],
            room["modality"],
            room["classification"],
            room["default_energy_label"],
            room["default_solver_mode"],
            room["overall_status"],
        ])
    flow.append(styled_table(
        rows,
        [34 * mm, 22 * mm, 42 * mm, 22 * mm, 18 * mm, 20 * mm],
        header=True,
        status_col=5,
    ))
    flow.append(Spacer(1, 4 * mm))
    return flow


def _section_barrier_schedule_for_room(room: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("8. Barrier Schedule", styles)]

    flow.append(Paragraph(f"{room['name']}", styles["RoomHeading"]))
    flow.append(Spacer(1, 1 * mm))
    flow.append(Paragraph(
        (
            f"Basis: Classification: {room['classification']} | "
            f"Energy basis: {room['default_energy_label']} | "
            f"Solver basis: {room['default_solver_mode']} | "
            f"Sources: {', '.join(room['expected_source_types'])}"
        ),
        styles["Muted"],
    ))
    flow.append(Spacer(1, 5 * mm))

    if room["error"]:
        flow.append(Paragraph(f"Room result generation error: {room['error']}", styles["FailText"]))
        return flow

    rows = [[
        "Barrier",
        "Element",
        "Parent",
        "Material",
        "Provided mm",
        "Governing req.",
        "Design goal uSv/wk",
        "Margin mm",
        "Status",
        "Construction / dominant source",
    ]]

    for b in room["barriers"]:
        construction_or_source = str(b.get("construction_note", "") or b.get("dominant_source", "") or "").strip()
        rows.append([
            str(b.get("name", "")).strip(),
            str(b.get("barrier_element_type", "Wall")).strip(),
            str(b.get("parent_barrier", "")).strip(),
            str(b.get("material", "")).strip(),
            str(b.get("provided_mm_display", "")),
            str(b.get("governing_requirement_text", "")).strip(),
            _fmt_float(b.get("design_goal_uSv_per_week"), 3),
            _fmt_float(b.get("margin_mm"), 3),
            str(b.get("status", "")).strip(),
            construction_or_source,
        ])

    flow.append(styled_table(
        rows,
        [18 * mm, 16 * mm, 16 * mm, 20 * mm, 15 * mm, 22 * mm, 17 * mm, 12 * mm, 13 * mm, 36 * mm],
        header=True,
        status_col=8,
    ))
    return flow

def _section_per_barrier_compliance(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("9. Per-Barrier Compliance Statements", styles)]

    for room in payload["rooms"]:
        flow.append(Paragraph(room["name"], styles["RoomHeading"]))
        flow.append(Spacer(1, 2 * mm))

        for b in room["barriers"]:
            summary_text = _barrier_summary_line(b)
            summary_style = _summary_style_name(b["status"])

            block: List[Any] = [
                Spacer(1, 2 * mm),
                Paragraph(
                    f"<b>{b['name']} — {room['name']}"
                    f"{' (' + b['adjacent_area'] + ')' if b.get('adjacent_area') else ''}</b>",
                    styles["RoomHeading"],
                ),
                Spacer(1, 0.5 * mm),
                Paragraph(summary_text, styles[summary_style]),
                Spacer(1, 1.5 * mm),
                Paragraph(f"Dominant source: {b['dominant_source']}", styles["Body"]),
                Paragraph(f"Provided shielding: {str(b.get("provided_statement", ""))}", styles["Body"]),
                Paragraph(f"Required shielding: {str(b.get("required_statement", ""))}", styles["Body"]),
            ]

            if b["margin_mm"] is not None:
                if b["margin_mm"] < 0:
                    block.append(Paragraph(f"Shortfall: {abs(b['margin_mm']):.3f} mm", styles["Body"]))
                else:
                    block.append(Paragraph(f"Margin: {b['margin_mm']:.3f} mm", styles["Body"]))

            if b.get("design_goal_uSv_per_week") is not None:
                block.append(Paragraph(f"Design goal: {b['design_goal_uSv_per_week']:.3f} uSv/week", styles["Body"]))

            if b.get("unshielded_weekly_dose_uSv") is not None:
                block.append(Paragraph(f"Unshielded dose: {b['unshielded_weekly_dose_uSv']:.3f} uSv/week", styles["Body"]))

            transmitted = b.get("transmitted_dose_uSv_per_week")
            if transmitted is not None:
                block.append(Paragraph(f"Transmitted dose: {transmitted:.3f} uSv/week", styles["Body"]))
            else:
                block.append(Paragraph("Transmitted dose: not exposed by physics engine", styles["Muted"]))

            if b.get("governing_requirement_text"):
                block.append(Paragraph(f"Governing requirement: {b['governing_requirement_text']}", styles["Body"]))

            style_name = _status_style_name(b["status"])
            block.append(Paragraph(f"Compliance: <b>{b['status']}</b>", styles[style_name]))
            block.append(Paragraph(f"<b>Compliance statement:</b> {b['compliance_statement']}", styles["Body"]))

            if b["dominant_reason"]:
                block.append(Paragraph(f"Basis: {b['dominant_reason']}", styles["Body"]))
            if b["notes"]:
                block.append(Paragraph(f"Notes: {b['notes']}", styles["Body"]))
            if b["solver_reasoning"]:
                block.append(Paragraph(f"Solver reasoning: {b['solver_reasoning']}", styles["Muted"]))

            block.extend(_construction_spec_flowables(b, room, styles))

            flow.append(Spacer(1, 2 * mm))
            flow.extend(block)
            flow.append(Spacer(1, 2 * mm))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D7DBE0")))
            flow.append(Spacer(1, 3 * mm))

    return flow



def _section_recommended_actions(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("10. Recommended Actions", styles)]

    rows = [["Room", "Barrier", "Status", "Recommended action", "Priority"]]
    if payload["action_rows"]:
        for row in payload["action_rows"]:
            rows.append([
                row["room_name"],
                row["barrier_name"],
                row["status"],
                row["recommended_action"],
                row["priority"],
            ])
    else:
        rows.append(["-", "-", "PASS", "No barrier action items identified from the live results.", "-"])

    flow.append(styled_table(
        rows,
        [30 * mm, 24 * mm, 16 * mm, 88 * mm, 18 * mm],
        header=True,
        status_col=2,
    ))
    flow.append(Spacer(1, 4 * mm))
    return flow

def _section_operational_requirements(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("11. Operational and Safety Requirements", styles)]

    flow.append(Paragraph(
        (
            "The following operational and installation requirements should be read in conjunction "
            "with the barrier-specific construction specifications and the project’s local regulatory obligations."
        ),
        styles["Body"],
    ))
    flow.append(Spacer(1, 4 * mm))

    bullets = [
        "Provide radiation warning signage at all relevant room entry points.",
        "Provide illuminated 'Radiation On / Do Not Enter' signage for rooms enclosing radiation apparatus where required.",
        "Ensure the operator has suitable means to observe and communicate with the patient during exposure.",
        "Ensure shielded barriers are tagged or otherwise documented with their shielding equivalence where required by project or jurisdictional practice.",
        "Final installation should be verified against the approved shielding design before clinical operation.",
    ]
    for text in bullets:
        flow.append(_bullet_para(text, styles))

    return flow

def _section_detailed_source_inputs(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    flow: List[Any] = [_section_heading("13. Detailed Source Input Appendix", styles)]

    for row in payload["detailed_source_rows"]:
        flow.append(Paragraph(
            f"<b>{row['room_name']}</b> — {row['source_name']} ({row['source_type']})",
            styles["Body"],
        ))
        report_content = row.get("report_content", {}) or {}
        for table_spec in report_content.get("detail_tables", []) or []:
            widths = [float(value) * mm for value in (table_spec.get("widths_mm", []) or [])]
            flow.append(styled_table(
                list(table_spec.get("rows", []) or []),
                widths or None,
                header=bool(table_spec.get("header", False)),
            ))
        for note in report_content.get("detail_notes", []) or []:
            text = str(note.get("text", "") if isinstance(note, dict) else note)
            style_name = str(note.get("style", "Muted") if isinstance(note, dict) else "Muted")
            if text:
                flow.append(Paragraph(text, styles.get(style_name, styles["Muted"])))
                flow.append(Spacer(1, 2 * mm))

        kv_rows = [["Parameter", "Value"], ["Radiation type", row["radiation_type"]]]
        kv_rows.extend(report_content.get("parameter_rows", []) or [])
        for key, value in (row["params"] or {}).items():
            kv_rows.append([str(key), _stringify_value(value)])
        flow.append(styled_table(kv_rows, [55 * mm, 95 * mm], header=True))
        flow.append(Spacer(1, 4 * mm))

    return flow


def _section_conclusion_and_signoff(payload: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    project = payload["project"]

    flow: List[Any] = [_section_heading("14. Conclusion and Sign-Off", styles)]
    flow.append(Paragraph(report_presentation(payload)["executive_conclusion_text"], styles["Body"]))
    flow.append(Spacer(1, 6 * mm))

    sign_rows = [
        ["Name", project["assessor"]],
        ["Position", "Radiation Physicist"],
        ["Date", project["date"]],
        ["Signature", ""],
    ]
    flow.append(styled_table(sign_rows, [35 * mm, 115 * mm], header=False))
    return flow


# Shared PDF styles and tables live in reports.pdf_style.

# =====================================================# Small helpers
# =====================================================
def section_divider() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D7DBE0"))

def _construction_rules_for_barrier(barrier: Dict[str, Any], room: Dict[str, Any]) -> Dict[str, Any]:
    material_raw = str(barrier.get("material", "") or "").strip().lower()
    barrier_name = str(barrier.get("name", "") or "").strip().lower()

    def shielding_height_mm() -> int:
        try:
            return int(room.get("construction_shielding_height_mm", 2100) or 2100)
        except (TypeError, ValueError):
            return 2100

    rules = {
        "height_mm": shielding_height_mm(),
        "material_notes": [],
        "penetration_notes": [
            "All penetrations are to be flashed with shielding of at least equivalent attenuation to the barrier.",
            "Particular attention is required for conduits, GPOs, switches, locks, pipe penetrations and duct penetrations.",
        ],
        "door_notes": [],
        "window_notes": [],
        "general_notes": [
            "Shielding must be continuous and free from voids.",
            "Shielding interfaces must overlap sufficiently to eliminate direct lines of sight through any gap.",
        ],
        "qa_checks": [
            "Verify installed shielding matches the specified barrier requirement.",
            "Verify shielding extends to the specified minimum height above finished floor level.",
            "Verify barrier continuity at corners, joints and interfaces.",
            "Verify penetrations are flashed and sealed.",
        ],
    }

    if material_raw in {"pb", "lead"}:
        provided_mm = _safe_float_or_none(barrier.get("provided_thickness_mm"))
        if provided_mm is not None and provided_mm <= 1.32:
            rules["material_notes"].append("Lead sheeting may be fixed to suitable plasterboard substrate where appropriate.")
        else:
            rules["material_notes"].append("For heavier lead gauges, use a robust substrate such as fibrocement sheet or equivalent.")
        rules["material_notes"].append("Provide minimum 12 mm overlap between adjoining lead sheets.")
        rules["material_notes"].append("Bond lead sheeting with adhesive.")
        rules["material_notes"].append("Isolate lead from steel studs using tape or equivalent separator where required.")
    elif material_raw == "concrete":
        rules["material_notes"].append("Concrete density is assumed to be consistent with the assessed design basis; any density shortfall may require thickness adjustment.")
        rules["material_notes"].append("Back-fill formwork holes and seal joints with material of equivalent or higher density.")
    elif material_raw in {"brick", "masonry", "block", "blockwork"}:
        rules["material_notes"].append("Masonry should be constructed with mortar of similar or greater density than the parent units.")
        rules["material_notes"].append("Where masonry is relied upon for shielding, construction quality and continuity must be maintained across all joints.")

    is_door = "door" in barrier_name
    is_viewing = ("view" in barrier_name) or ("panel" in barrier_name) or ("window" in barrier_name)

    if is_door:
        rules["door_notes"].extend([
            "Door and frame must provide at least the same shielding equivalence as the parent barrier.",
            "Provide minimum 12 mm overlap at the rebate / frame interface.",
            "Door hardware must be installed without compromising shielding continuity.",
        ])
        rules["qa_checks"].append("Verify door leaf, frame and hardware maintain shielding continuity.")

    if is_viewing:
        rules["window_notes"].extend([
            "Viewing panel must provide at least the same shielding equivalence as the barrier.",
            "Viewing panel lead equivalence and rated kVp should be visibly and indelibly marked where applicable.",
            "The viewing panel interface must overlap surrounding barrier shielding.",
        ])
        rules["qa_checks"].append("Verify glazing certification and visible lead-equivalence marking.")

    return rules


def _construction_spec_flowables(barrier: Dict[str, Any], room: Dict[str, Any], styles: StyleSheet1) -> List[Any]:
    rules = _construction_rules_for_barrier(barrier, room)
    material = str(barrier.get("material", "") or "-")
    provided_mm = barrier.get("provided_thickness_mm")
    governing_req = str(barrier.get("governing_requirement_text", "") or "Not available")
    height_mm = rules["height_mm"]

    flowables: List[Any] = [
        Spacer(1, 2 * mm),
        Paragraph("<b>Construction specification</b>", styles["Body"]),
        Paragraph(f"Material: {material}", styles["Body"]),
        Paragraph(f"Construction classification: {material} barrier", styles["Body"]),
    ]

    if isinstance(provided_mm, (int, float)):
        if material == "Pb":
            flowables.append(Paragraph(f"Installed shielding: {provided_mm:.2f} mm", styles["Body"]))
        else:
            flowables.append(Paragraph(f"Installed shielding: {provided_mm:.1f} mm", styles["Body"]))
    else:
        flowables.append(Paragraph("Installed shielding: not stated", styles["Body"]))

    flowables.append(Paragraph(f"Required shielding: {governing_req}", styles["Body"]))
    flowables.append(Paragraph(f"Minimum shielding height: {height_mm} mm above finished floor level", styles["Body"]))

    if "glass" in material.lower():
        flowables.append(Paragraph(
            "Note: Lead glass must be certified to the required lead equivalence at the stated kVp and installed with a continuous shielded frame.",
            styles["Body"]
        ))

    def _append_group(title: str, items: List[str]) -> None:
        if not items:
            return
        flowables.append(Spacer(1, 1.2 * mm))
        flowables.append(Paragraph(f"<b>{title}</b>", styles["Body"]))
        for item in items:
            flowables.append(Paragraph(f"• {item}", styles["Body"]))

    _append_group("General installation notes", rules["general_notes"])
    _append_group("Material notes", rules["material_notes"])
    _append_group("Penetrations", rules["penetration_notes"])
    _append_group("Doors and frames", rules["door_notes"])
    _append_group("Viewing panels", rules["window_notes"])
    _append_group("Installer QA checklist", rules["qa_checks"])

    return flowables


def _design_goal_summary_text(barrier: Dict[str, Any]) -> str:
    goal = barrier.get("design_goal_uSv_per_week")
    if goal is None:
        return "the adopted weekly design goal"
    return f"{goal:.3f} uSv/week design goal"


def _barrier_summary_line(barrier: Dict[str, Any]) -> str:
    status = _normalise_status(barrier.get("status", ""))
    goal_text = _design_goal_summary_text(barrier)

    if status == "FAIL":
        return f"FAIL — Exceeds {goal_text}"
    if status == "REVIEW":
        return f"REVIEW — Borderline against {goal_text}"
    return f"PASS — Complies with {goal_text}"


def _status_style_name(status: str) -> str:
    s = _normalise_status(status)
    if s == "FAIL":
        return "StatusFail"
    if s == "REVIEW":
        return "StatusReview"
    return "StatusPass"


def _summary_style_name(status: str) -> str:
    s = _normalise_status(status)
    if s == "FAIL":
        return "SummaryFail"
    if s == "REVIEW":
        return "SummaryReview"
    return "SummaryPass"

def _section_heading(text: str, styles: StyleSheet1):
    return KeepTogether([
        Paragraph(text, styles["SectionHeading"]),
        Spacer(1, 1 * mm),
        section_divider(),
        Spacer(1, 3 * mm),
    ])

def _bullet_para(text: str, styles: StyleSheet1) -> Paragraph:
    return Paragraph(f"• {text}", styles["BulletText"])
