from __future__ import annotations

"""
Shared ReportLab PDF styling helpers.

This module deliberately contains presentation-only helpers. It should not know
about shielding physics, source state, ksec basis, or report payload generation.
"""

from typing import Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Table, TableStyle


def build_styles() -> StyleSheet1:
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#152238"),
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="CoverProject",
        parent=styles["Heading2"],
        fontName="Helvetica",
        fontSize=15,
        leading=19,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#3A4656"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="CertificateTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#152238"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="CertificateSubtitle",
        parent=styles["Heading2"],
        fontName="Helvetica",
        fontSize=12.5,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="CertificateBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=13.4,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111111"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=17,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#152238"),
        spaceAfter=6,
        spaceBefore=2,
        borderWidth=0,
        borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        name="Subheading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#253245"),
        spaceAfter=5,
        spaceBefore=3,
    ))
    styles.add(ParagraphStyle(
        name="RoomHeading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#152238"),
        spaceBefore=5,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=12.6,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111111"),
        spaceAfter=1.5,
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=11,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#5B6573"),
    ))
    styles.add(ParagraphStyle(
        name="BulletText",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.2,
        leftIndent=10,
        bulletIndent=0,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111111"),
    ))
    styles.add(ParagraphStyle(
        name="FailText",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#A32121"),
    ))
    styles.add(ParagraphStyle(
        name="StatusPass",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1D6B43"),
    ))
    styles.add(ParagraphStyle(
        name="StatusFail",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#A32121"),
    ))
    styles.add(ParagraphStyle(
        name="StatusReview",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#9A6A00"),
    ))
    styles.add(ParagraphStyle(
        name="SummaryPass",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=12.8,
        textColor=colors.HexColor("#1D6B43"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="SummaryReview",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=12.8,
        textColor=colors.HexColor("#9A6A00"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="SummaryFail",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=12.8,
        textColor=colors.HexColor("#A32121"),
        backColor=colors.HexColor("#FBEAEA"),
        borderPadding=(4, 4, 4),
        spaceAfter=2,
    ))

    return styles


def styled_table(
    rows: Sequence[Sequence[str]],
    col_widths: Sequence[float],
    header: bool,
    status_col: Optional[int] = None,
) -> Table:
    table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)

    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CCD3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE0")),
    ]

    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182230")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.6),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ]
        for row_idx in range(1, len(rows)):
            if row_idx % 2 == 0:
                style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#F7F8FA")))
    else:
        for row_idx in range(len(rows)):
            if row_idx % 2 == 1:
                style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FAFBFC")))

    if status_col is not None:
        start_row = 1 if header else 0
        for row_idx in range(start_row, len(rows)):
            status = str(rows[row_idx][status_col] or "")
            style.append(("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), status_colour(status)))
            style.append(("FONTNAME", (status_col, row_idx), (status_col, row_idx), "Helvetica-Bold"))
            style.append(("ALIGN", (status_col, row_idx), (status_col, row_idx), "CENTER"))

    for col_idx in range(len(rows[0])):
        numeric_like = True
        for row_idx in range(1 if header else 0, min(len(rows), 8)):
            text = str(rows[row_idx][col_idx] or "").strip()
            if not text:
                continue
            allowed = set("0123456789.-/ ")
            if not set(text) <= allowed:
                numeric_like = False
                break
        if numeric_like:
            style.append(("ALIGN", (col_idx, 0), (col_idx, -1), "RIGHT"))

    table.setStyle(TableStyle(style))
    return table


def section_divider() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D7DBE0"))


def status_colour(status: str):
    s = str(status or "").strip().upper()
    if s in {"FAIL", "ERROR", "NON-COMPLIANT"}:
        return colors.HexColor("#A32121")
    if s in {"REVIEW", "WARN", "WARNING"}:
        return colors.HexColor("#9A6A00")
    return colors.HexColor("#1D6B43")
