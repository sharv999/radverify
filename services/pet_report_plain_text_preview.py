"""Isolated plain-text PET report preview renderer.

This module consumes only the frozen Step 26 PET report-section view model and
returns deterministic in-memory text lines.  It does not write files or connect
PET data to PDF, CSV/JSON, certification, signature, or the normal output
pipeline.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from services.pet_report_section_view_model import (
    PET_BARRIER_TABLE_FIELDS,
    PET_EXPOSURE_TABLE_FIELDS,
    PET_PROVENANCE_DISPLAY_FIELDS,
    PET_REPORT_SECTION_HEADINGS,
    PET_REPORT_SECTION_VIEW_MODEL_BASELINE,
    PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    PET_REPORT_SECTION_WARNINGS,
    PET_SOURCE_DISPLAY_FIELDS,
)

PET_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION = 1
PET_PLAIN_TEXT_PREVIEW_BASELINE = "pet-plain-text-preview-v1-non-issueable"
PET_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN = False
PET_PLAIN_TEXT_PREVIEW_STATUS = (
    "PLAIN-TEXT PREVIEW ONLY — in-memory, non-issueable, and disconnected from "
    "PDF, CSV/JSON, certification, signature, file writing, and the normal output pipeline."
)

PET_PLAIN_TEXT_SECTION_DIVIDER = "=" * 72
PET_PLAIN_TEXT_TABLE_SEPARATOR = " | "


class PetPlainTextPreviewError(ValueError):
    """Raised when a Step 26 view model cannot be rendered safely."""


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PetPlainTextPreviewError(f"{field} must be a mapping.")
    return value


def _list(value: object, field: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise PetPlainTextPreviewError(f"{field} must be a list.")
    return value


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PetPlainTextPreviewError(f"{field} must not be blank.")
    if "\n" in text or "\r" in text:
        raise PetPlainTextPreviewError(f"{field} must be a single line.")
    return text


def _labelled_value(row: Mapping[str, Any], field: str) -> str:
    label = _text(row.get("label"), f"{field}.label")
    value = _text(row.get("value"), f"{field}.value")
    unit = str(row.get("unit") or "").strip()
    suffix = f" {unit}" if unit else ""
    return f"{label}: {value}{suffix}"


def _table_header(columns: Sequence[Any], expected_fields: Sequence[str], field: str) -> str:
    headings: List[str] = []
    if len(columns) != len(expected_fields):
        raise PetPlainTextPreviewError(f"{field} column count has drifted.")
    for index, expected in enumerate(expected_fields):
        column = _mapping(columns[index], f"{field}.columns[{index}]")
        if column.get("field") != expected:
            raise PetPlainTextPreviewError(f"{field} column ordering has drifted.")
        heading = _text(column.get("heading"), f"{field}.columns[{index}].heading")
        unit = str(column.get("unit") or "").strip()
        headings.append(f"{heading} [{unit}]" if unit else heading)
    return PET_PLAIN_TEXT_TABLE_SEPARATOR.join(headings)


def _table_row(row: Mapping[str, Any], expected_fields: Sequence[str], field: str) -> str:
    if tuple(row.keys()) != tuple(expected_fields):
        raise PetPlainTextPreviewError(f"{field} field ordering has drifted.")
    return PET_PLAIN_TEXT_TABLE_SEPARATOR.join(
        _text(row[name], f"{field}.{name}") for name in expected_fields
    )


def render_non_issueable_pet_plain_text_preview(
    view_model: Mapping[str, Any],
) -> List[str]:
    """Render deterministic in-memory lines from the frozen Step 26 view model."""
    if PET_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN:
        raise PetPlainTextPreviewError(
            "The PET plain-text preview cannot run after integration is opened."
        )
    if view_model.get("view_model_contract_version") != PET_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION:
        raise PetPlainTextPreviewError("Unsupported PET report-section view-model contract version.")
    if view_model.get("view_model_baseline") != PET_REPORT_SECTION_VIEW_MODEL_BASELINE:
        raise PetPlainTextPreviewError("Unsupported PET report-section view-model baseline.")
    if view_model.get("non_issueable") is not True or view_model.get("report_integration_open") is not False:
        raise PetPlainTextPreviewError("PET report-section view model is not closed and non-issueable.")
    if view_model.get("replay_verified") is not True:
        raise PetPlainTextPreviewError("PET report-section view-model replay is not verified.")

    headings = _mapping(view_model.get("headings"), "headings")
    if tuple(headings.items()) != PET_REPORT_SECTION_HEADINGS:
        raise PetPlainTextPreviewError("PET report-section headings have drifted.")
    warnings = _list(view_model.get("warnings"), "warnings")
    if tuple(warnings) != PET_REPORT_SECTION_WARNINGS:
        raise PetPlainTextPreviewError("PET report-section warnings have drifted.")

    source = _mapping(view_model.get("source_summary"), "source_summary")
    if tuple(source.get("field_order") or ()) != PET_SOURCE_DISPLAY_FIELDS:
        raise PetPlainTextPreviewError("PET source-summary field ordering has drifted.")
    source_rows = _list(source.get("rows"), "source_summary.rows")
    if len(source_rows) != len(PET_SOURCE_DISPLAY_FIELDS):
        raise PetPlainTextPreviewError("PET source-summary row count has drifted.")

    exposure = _mapping(view_model.get("exposure_period_table"), "exposure_period_table")
    if tuple(exposure.get("field_order") or ()) != PET_EXPOSURE_TABLE_FIELDS:
        raise PetPlainTextPreviewError("PET exposure-table field ordering has drifted.")
    exposure_columns = _list(exposure.get("columns"), "exposure_period_table.columns")
    exposure_rows = _list(exposure.get("rows"), "exposure_period_table.rows")
    if not exposure_rows:
        raise PetPlainTextPreviewError("PET exposure table must contain at least one row.")

    barriers = _mapping(view_model.get("barrier_table"), "barrier_table")
    if tuple(barriers.get("field_order") or ()) != PET_BARRIER_TABLE_FIELDS:
        raise PetPlainTextPreviewError("PET barrier-table field ordering has drifted.")
    barrier_columns = _list(barriers.get("columns"), "barrier_table.columns")
    barrier_rows = _list(barriers.get("rows"), "barrier_table.rows")
    if not barrier_rows:
        raise PetPlainTextPreviewError("PET barrier table must contain at least one row.")

    provenance = _mapping(view_model.get("provenance"), "provenance")
    if tuple(provenance.get("field_order") or ()) != PET_PROVENANCE_DISPLAY_FIELDS:
        raise PetPlainTextPreviewError("PET provenance field ordering has drifted.")
    provenance_rows = _list(provenance.get("rows"), "provenance.rows")
    if len(provenance_rows) != len(PET_PROVENANCE_DISPLAY_FIELDS):
        raise PetPlainTextPreviewError("PET provenance row count has drifted.")

    lines: List[str] = [
        headings["section"],
        PET_PLAIN_TEXT_SECTION_DIVIDER,
        PET_PLAIN_TEXT_PREVIEW_STATUS,
        "",
        "Warnings",
    ]
    lines.extend(f"WARNING: {_text(item, 'warnings[]')}" for item in warnings)

    lines.extend(["", headings["source_summary"]])
    for index, expected in enumerate(PET_SOURCE_DISPLAY_FIELDS):
        row = _mapping(source_rows[index], f"source_summary.rows[{index}]")
        if row.get("field") != expected:
            raise PetPlainTextPreviewError("PET source-summary row ordering has drifted.")
        lines.append(_labelled_value(row, f"source_summary.rows[{index}]"))

    lines.extend([
        "",
        headings["exposure_periods"],
        _table_header(exposure_columns, PET_EXPOSURE_TABLE_FIELDS, "exposure_period_table"),
    ])
    for index, row in enumerate(exposure_rows):
        lines.append(_table_row(_mapping(row, f"exposure_period_table.rows[{index}]"), PET_EXPOSURE_TABLE_FIELDS, f"exposure_period_table.rows[{index}]"))

    lines.extend([
        "",
        headings["barrier_results"],
        _table_header(barrier_columns, PET_BARRIER_TABLE_FIELDS, "barrier_table"),
    ])
    for index, row in enumerate(barrier_rows):
        lines.append(_table_row(_mapping(row, f"barrier_table.rows[{index}]"), PET_BARRIER_TABLE_FIELDS, f"barrier_table.rows[{index}]"))

    lines.extend(["", headings["provenance"]])
    for index, expected in enumerate(PET_PROVENANCE_DISPLAY_FIELDS):
        row = _mapping(provenance_rows[index], f"provenance.rows[{index}]")
        if row.get("field") != expected:
            raise PetPlainTextPreviewError("PET provenance row ordering has drifted.")
        lines.append(_labelled_value(row, f"provenance.rows[{index}]"))

    lines.extend(["", PET_PLAIN_TEXT_SECTION_DIVIDER, "END OF NON-ISSUEABLE PET PREVIEW"])
    return lines
