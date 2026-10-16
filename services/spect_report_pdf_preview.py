"""Isolated non-issueable SPECT PDF preview renderer for Step 33.

This module renders only the frozen Step 30/31 SPECT report-preview boundary.
It returns PDF bytes in memory and is intentionally disconnected from issued
report routing, machine export, certification, signatures, and project output.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness
from services.spect_report_plain_text_preview import render_non_issueable_spect_plain_text_preview
from services.spect_report_section_view_model import (
    SPECT_BARRIER_TABLE_FIELDS,
    SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE,
    SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
)

SPECT_PDF_PREVIEW_CONTRACT_VERSION = 1
SPECT_PDF_PREVIEW_BASELINE = "spect-pdf-preview-v1-non-issueable-isolated"
SPECT_PDF_PREVIEW_INTEGRATION_OPEN = False
SPECT_PDF_PREVIEW_ISSUEABLE = False
SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE = False
SPECT_PDF_PREVIEW_HEADER = "SPECT SHIELDING ASSESSMENT - NON-ISSUEABLE PDF PREVIEW"
SPECT_PDF_PREVIEW_FOOTER = "NON-ISSUEABLE PREVIEW - NOT FOR REGULATORY, CONSTRUCTION OR CERTIFICATION USE"


class SpectPdfPreviewError(ValueError):
    """Raised when a Step 33 preview cannot be safely rendered."""


@dataclass(frozen=True)
class SpectNonIssueablePdfPreview:
    pdf_bytes: bytes
    contract_version: int = SPECT_PDF_PREVIEW_CONTRACT_VERSION
    baseline: str = SPECT_PDF_PREVIEW_BASELINE
    non_issueable: bool = True
    output_eligible: bool = False
    issued_pdf_enabled: bool = False
    certification_enabled: bool = False


class _InvariantCanvas(canvas.Canvas):
    """Deterministic ReportLab canvas for regression-stable preview bytes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)


def _single_line(value: Any, label: str) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise SpectPdfPreviewError(f"{label} must remain single-line in the frozen PDF preview boundary.")
    return text


def _validate_preview_boundary(view_model: Mapping[str, Any]) -> None:
    if SPECT_PDF_PREVIEW_INTEGRATION_OPEN or SPECT_PDF_PREVIEW_ISSUEABLE or SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE:
        raise SpectPdfPreviewError("Step 33 PDF preview boundary must remain closed and non-issueable.")

    readiness = assess_spect_pdf_integration_readiness()
    if readiness.get("validated_foundations") is not True:
        raise SpectPdfPreviewError("Step 32 PDF foundations are not validated.")
    if readiness.get("issued_pdf_enabled") is not False or readiness.get("certification_enabled") is not False:
        raise SpectPdfPreviewError("Issued PDF/certification state must remain disabled for Step 33.")

    if view_model.get("view_model_contract_version") != SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION:
        raise SpectPdfPreviewError("SPECT report view-model contract version drifted.")
    if view_model.get("view_model_baseline") != SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE:
        raise SpectPdfPreviewError("SPECT report view-model baseline drifted.")
    if view_model.get("non_issueable") is not True or view_model.get("report_integration_open") is not False:
        raise SpectPdfPreviewError("SPECT report view-model is not closed and non-issueable.")

    # Step 31 is the frozen textual validator for the same Step 30 view-model.
    # Rendering it here (without using its output) ensures Step 33 cannot accept
    # content that the already-frozen preview boundary would reject.
    render_non_issueable_spect_plain_text_preview(view_model)


def _page_decorator(pdf: canvas.Canvas, doc: SimpleDocTemplate) -> None:
    width, height = A4
    pdf.saveState()

    pdf.setFillColor(colors.HexColor("#B42318"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(18 * mm, height - 12 * mm, "NON-ISSUEABLE SPECT PDF PREVIEW")

    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(18 * mm, 9 * mm, SPECT_PDF_PREVIEW_FOOTER)
    pdf.drawRightString(width - 18 * mm, 9 * mm, f"Page {doc.page}")

    pdf.setFillColor(colors.Color(0.86, 0.86, 0.86, alpha=0.34))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.translate(width / 2, height / 2)
    pdf.rotate(35)
    pdf.drawCentredString(0, 0, "NON-ISSUEABLE PREVIEW")
    pdf.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SpectPreviewTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#7A271A"),
            spaceAfter=6 * mm,
        ),
        "h1": ParagraphStyle(
            "SpectPreviewH1",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#333333"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "SpectPreviewBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#222222"),
        ),
        "warning": ParagraphStyle(
            "SpectPreviewWarning",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#7A271A"),
            leftIndent=3 * mm,
            rightIndent=3 * mm,
        ),
        "small": ParagraphStyle(
            "SpectPreviewSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=colors.HexColor("#555555"),
        ),
    }


def _kv_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [Paragraph(_single_line(label, "SPECT PDF label"), styles["body"]), Paragraph(_single_line(value, "SPECT PDF value"), styles["body"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[58 * mm, 112 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F7")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def render_non_issueable_spect_pdf_preview(view_model: Mapping[str, Any]) -> SpectNonIssueablePdfPreview:
    """Render the frozen SPECT report view-model to deterministic in-memory PDF bytes."""
    _validate_preview_boundary(view_model)
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="SPECT Shielding Assessment - Non-Issueable PDF Preview",
        author="RadShield",
        subject=SPECT_PDF_PREVIEW_BASELINE,
    )

    headings = view_model["headings"]
    story: list[Any] = [
        Paragraph(SPECT_PDF_PREVIEW_HEADER, styles["title"]),
        Paragraph(_single_line(headings["section"], "SPECT section heading"), styles["h1"]),
    ]

    warning_data = [[Paragraph("NON-ISSUEABLE", styles["warning"])]]
    warning_data.extend([
        [Paragraph(_single_line(warning, "SPECT warning"), styles["warning"])]
        for warning in view_model["warnings"]
    ])
    warning_table = Table(warning_data, colWidths=[170 * mm], hAlign="LEFT")
    warning_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3F2")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FDA29B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([warning_table, Spacer(1, 4 * mm)])

    story.append(Paragraph(_single_line(headings["source_summary"], "SPECT source heading"), styles["h1"]))
    source_rows: list[tuple[str, str]] = []
    for row in view_model["source_summary"]["rows"]:
        label = _single_line(row["label"], "SPECT source label")
        value = _single_line(row["value"], "SPECT source value")
        unit = _single_line(row.get("unit", ""), "SPECT source unit") if row.get("unit") else ""
        source_rows.append((label, f"{value} {unit}".strip()))
    story.extend([_kv_table(source_rows, styles), Spacer(1, 4 * mm)])

    story.append(Paragraph(_single_line(headings["barrier_results"], "SPECT barrier heading"), styles["h1"]))
    columns = {column["field"]: column for column in view_model["barrier_table"]["columns"]}
    for index, row in enumerate(view_model["barrier_table"]["rows"], 1):
        barrier_name = _single_line(row["barrier_name"], "SPECT barrier name")
        details: list[tuple[str, str]] = []
        for field in SPECT_BARRIER_TABLE_FIELDS:
            if field == "barrier_name":
                continue
            column = columns[field]
            label = _single_line(column["label"], "SPECT barrier label")
            value = _single_line(row[field], "SPECT barrier value")
            unit = _single_line(column.get("unit", ""), "SPECT barrier unit") if column.get("unit") else ""
            details.append((label, f"{value} {unit}".strip()))
        story.append(KeepTogether([
            Paragraph(f"Barrier {index}: {barrier_name}", styles["h1"]),
            _kv_table(details, styles),
            Spacer(1, 3 * mm),
        ]))

    story.append(Paragraph(_single_line(headings["provenance"], "SPECT provenance heading"), styles["h1"]))
    provenance_rows = [
        (_single_line(row["field"], "SPECT provenance field"), _single_line(row["value"], "SPECT provenance value"))
        for row in view_model["provenance"]["rows"]
    ]
    story.extend([
        _kv_table(provenance_rows, styles),
        Spacer(1, 4 * mm),
        Paragraph(
            f"Preview contract v{SPECT_PDF_PREVIEW_CONTRACT_VERSION} - {SPECT_PDF_PREVIEW_BASELINE}",
            styles["small"],
        ),
        Paragraph(SPECT_PDF_PREVIEW_FOOTER, styles["warning"]),
    ])

    doc.build(story, onFirstPage=_page_decorator, onLaterPages=_page_decorator, canvasmaker=_InvariantCanvas)
    pdf_bytes = buffer.getvalue()
    if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-64:]:
        raise SpectPdfPreviewError("Step 33 renderer did not produce a valid PDF byte stream.")

    return SpectNonIssueablePdfPreview(pdf_bytes=pdf_bytes)
