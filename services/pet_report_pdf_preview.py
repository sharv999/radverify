"""Isolated non-issueable PET PDF preview renderer for Step 28.

Consumes only the frozen PET report-section view model, validates it through the
existing plain-text preview boundary, and returns deterministic PDF bytes in
memory. It is intentionally disconnected from issued report routing, export,
certification, signatures, and project output.
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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.pet_pdf_integration_readiness_gate import assess_pet_pdf_integration_readiness
from services.pet_report_plain_text_preview import render_non_issueable_pet_plain_text_preview
from services.pet_report_section_view_model import (
    PET_BARRIER_TABLE_FIELDS,
    PET_EXPOSURE_TABLE_FIELDS,
    PET_REPORT_SECTION_VIEW_MODEL_BASELINE,
    PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
)

PET_PDF_PREVIEW_CONTRACT_VERSION = 1
PET_PDF_PREVIEW_BASELINE = "pet-pdf-preview-step28-v1-non-issueable-isolated"
PET_PDF_PREVIEW_INTEGRATION_OPEN = False
PET_PDF_PREVIEW_ISSUEABLE = False
PET_PDF_PREVIEW_OUTPUT_ELIGIBLE = False
PET_PDF_PREVIEW_HEADER = "PET SHIELDING ASSESSMENT - NON-ISSUEABLE PDF PREVIEW"
PET_PDF_PREVIEW_FOOTER = "NON-ISSUEABLE PREVIEW - NOT FOR REGULATORY, CONSTRUCTION OR CERTIFICATION USE"


class PetPdfPreviewError(ValueError):
    """Raised when the isolated PET PDF preview cannot be rendered safely."""


@dataclass(frozen=True)
class PetNonIssueablePdfPreview:
    pdf_bytes: bytes
    contract_version: int = PET_PDF_PREVIEW_CONTRACT_VERSION
    baseline: str = PET_PDF_PREVIEW_BASELINE
    non_issueable: bool = True
    output_eligible: bool = False
    issued_pdf_enabled: bool = False
    certification_enabled: bool = False


class _InvariantCanvas(canvas.Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)


def _single_line(value: Any, label: str) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise PetPdfPreviewError(f"{label} must remain single-line in the frozen PET PDF preview boundary.")
    return text


def _validate_preview_boundary(view_model: Mapping[str, Any]) -> None:
    if PET_PDF_PREVIEW_INTEGRATION_OPEN or PET_PDF_PREVIEW_ISSUEABLE or PET_PDF_PREVIEW_OUTPUT_ELIGIBLE:
        raise PetPdfPreviewError("PET Step 28 PDF preview boundary must remain closed and non-issueable.")
    readiness = assess_pet_pdf_integration_readiness()
    if readiness.get("validated_foundations") is not True:
        raise PetPdfPreviewError("PET Step 28 PDF foundations are not validated.")
    if readiness.get("issued_pdf_enabled") is not False or readiness.get("certification_enabled") is not False:
        raise PetPdfPreviewError("Issued PET PDF/certification must remain disabled.")
    if view_model.get("view_model_contract_version") != PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION:
        raise PetPdfPreviewError("PET report view-model contract version drifted.")
    if view_model.get("view_model_baseline") != PET_REPORT_SECTION_VIEW_MODEL_BASELINE:
        raise PetPdfPreviewError("PET report view-model baseline drifted.")
    if view_model.get("non_issueable") is not True or view_model.get("report_integration_open") is not False:
        raise PetPdfPreviewError("PET report view-model is not closed and non-issueable.")
    render_non_issueable_pet_plain_text_preview(view_model)


def _page_decorator(pdf: canvas.Canvas, doc: SimpleDocTemplate) -> None:
    width, height = A4
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#B42318"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(18 * mm, height - 12 * mm, "NON-ISSUEABLE PET PDF PREVIEW")
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(18 * mm, 9 * mm, PET_PDF_PREVIEW_FOOTER)
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
        "title": ParagraphStyle("PetPreviewTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#7A271A"), spaceAfter=6 * mm),
        "h1": ParagraphStyle("PetPreviewH1", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=colors.HexColor("#333333"), spaceBefore=4 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("PetPreviewBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#222222")),
        "warning": ParagraphStyle("PetPreviewWarning", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=colors.HexColor("#7A271A"), leftIndent=3 * mm, rightIndent=3 * mm),
        "small": ParagraphStyle("PetPreviewSmall", parent=base["BodyText"], fontName="Helvetica", fontSize=6.5, leading=8, textColor=colors.HexColor("#555555")),
    }


def _kv_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(_single_line(label, "PET PDF label"), styles["body"]), Paragraph(_single_line(value, "PET PDF value"), styles["body"])] for label, value in rows]
    table = Table(data, colWidths=[58 * mm, 112 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _compact_table(columns: list[Mapping[str, Any]], rows: list[Mapping[str, Any]], fields: tuple[str, ...], styles: dict[str, ParagraphStyle]) -> Table:
    by_field = {column["field"]: column for column in columns}
    header = [Paragraph(_single_line(by_field[field]["heading"], "PET table heading"), styles["small"]) for field in fields]
    data: list[list[Any]] = [header]
    for row in rows:
        data.append([Paragraph(_single_line(row[field], "PET table value"), styles["small"]) for field in fields])
    available = 170 * mm
    widths = [available / len(fields)] * len(fields)
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def render_non_issueable_pet_pdf_preview(view_model: Mapping[str, Any]) -> PetNonIssueablePdfPreview:
    """Render the frozen PET report view-model to deterministic in-memory PDF bytes."""
    _validate_preview_boundary(view_model)
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=16 * mm,
        title="PET Shielding Assessment - Non-Issueable PDF Preview",
        author="RadShield", subject=PET_PDF_PREVIEW_BASELINE,
    )
    headings = view_model["headings"]
    story: list[Any] = [
        Paragraph(PET_PDF_PREVIEW_HEADER, styles["title"]),
        Paragraph(_single_line(headings["section"], "PET section heading"), styles["h1"]),
    ]
    warning_data = [[Paragraph("NON-ISSUEABLE", styles["warning"])]]
    warning_data.extend([[Paragraph(_single_line(warning, "PET warning"), styles["warning"])] for warning in view_model["warnings"]])
    warning_table = Table(warning_data, colWidths=[170 * mm], hAlign="LEFT")
    warning_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3F2")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FDA29B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([warning_table, Spacer(1, 4 * mm)])

    story.append(Paragraph(_single_line(headings["source_summary"], "PET source heading"), styles["h1"]))
    source_rows: list[tuple[str, str]] = []
    for row in view_model["source_summary"]["rows"]:
        unit = _single_line(row.get("unit", ""), "PET source unit") if row.get("unit") else ""
        source_rows.append((_single_line(row["label"], "PET source label"), f"{_single_line(row['value'], 'PET source value')} {unit}".strip()))
    story.extend([_kv_table(source_rows, styles), Spacer(1, 4 * mm)])

    exposure = view_model["exposure_period_table"]
    story.append(Paragraph(_single_line(headings["exposure_periods"], "PET exposure heading"), styles["h1"]))
    story.extend([_compact_table(exposure["columns"], exposure["rows"], PET_EXPOSURE_TABLE_FIELDS, styles), Spacer(1, 4 * mm)])

    story.append(Paragraph(_single_line(headings["barrier_results"], "PET barrier heading"), styles["h1"]))
    columns = {column["field"]: column for column in view_model["barrier_table"]["columns"]}
    for index, row in enumerate(view_model["barrier_table"]["rows"], 1):
        details: list[tuple[str, str]] = []
        for field in PET_BARRIER_TABLE_FIELDS:
            if field == "barrier_name":
                continue
            column = columns[field]
            unit = _single_line(column.get("unit", ""), "PET barrier unit") if column.get("unit") else ""
            details.append((_single_line(column["heading"], "PET barrier heading"), f"{_single_line(row[field], 'PET barrier value')} {unit}".strip()))
        story.append(KeepTogether([
            Paragraph(f"Barrier {index}: {_single_line(row['barrier_name'], 'PET barrier name')}", styles["h1"]),
            _kv_table(details, styles), Spacer(1, 3 * mm),
        ]))

    story.append(Paragraph(_single_line(headings["provenance"], "PET provenance heading"), styles["h1"]))
    provenance_rows = [(_single_line(row["label"], "PET provenance label"), _single_line(row["value"], "PET provenance value")) for row in view_model["provenance"]["rows"]]
    story.extend([
        _kv_table(provenance_rows, styles), Spacer(1, 4 * mm),
        Paragraph(f"Preview contract v{PET_PDF_PREVIEW_CONTRACT_VERSION} - {PET_PDF_PREVIEW_BASELINE}", styles["small"]),
        Paragraph(PET_PDF_PREVIEW_FOOTER, styles["warning"]),
    ])
    doc.build(story, onFirstPage=_page_decorator, onLaterPages=_page_decorator, canvasmaker=_InvariantCanvas)
    pdf_bytes = buffer.getvalue()
    if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-64:]:
        raise PetPdfPreviewError("PET Step 28 renderer did not produce a valid PDF byte stream.")
    return PetNonIssueablePdfPreview(pdf_bytes=pdf_bytes)
