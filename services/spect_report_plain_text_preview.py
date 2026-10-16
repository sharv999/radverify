"""Non-issueable plain-text SPECT report preview renderer for Step 31.

This module renders only the frozen Step 30 section view-model.  It performs
no file I/O and remains disconnected from PDF/report output, machine export,
and certification.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from services.spect_report_section_view_model import (
    SPECT_BARRIER_TABLE_FIELDS,
    SPECT_PROVENANCE_DISPLAY_FIELDS,
    SPECT_REPORT_SECTION_HEADINGS,
    SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE,
    SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    SPECT_REPORT_SECTION_WARNINGS,
    SPECT_SOURCE_DISPLAY_FIELDS,
)

SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION = 1
SPECT_PLAIN_TEXT_PREVIEW_BASELINE = "spect-plain-text-report-preview-v1-non-issueable"
SPECT_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN = False
SPECT_PLAIN_TEXT_PREVIEW_HEADER = "SPECT SHIELDING ASSESSMENT — NON-ISSUEABLE PREVIEW"
SPECT_PLAIN_TEXT_PREVIEW_FOOTER = "END NON-ISSUEABLE SPECT PREVIEW"


class SpectPlainTextPreviewError(ValueError):
    pass


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpectPlainTextPreviewError(f"{label} must be a mapping.")
    return value


def _require_sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SpectPlainTextPreviewError(f"{label} must be a sequence.")
    return value


def _single_line(value: Any, label: str) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise SpectPlainTextPreviewError(f"{label} must be single-line text.")
    return text


def _validate_view_model(view_model: Mapping[str, Any]) -> None:
    if SPECT_PLAIN_TEXT_PREVIEW_INTEGRATION_OPEN:
        raise SpectPlainTextPreviewError("SPECT plain-text preview integration must remain closed.")
    if view_model.get("view_model_contract_version") != SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION:
        raise SpectPlainTextPreviewError("Unsupported SPECT report section view-model contract version.")
    if view_model.get("view_model_baseline") != SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE:
        raise SpectPlainTextPreviewError("Unsupported SPECT report section view-model baseline.")
    if view_model.get("non_issueable") is not True or view_model.get("report_integration_open") is not False:
        raise SpectPlainTextPreviewError("SPECT report section view-model must remain closed and non-issueable.")

    headings = _require_mapping(view_model.get("headings"), "SPECT headings")
    if headings != dict(SPECT_REPORT_SECTION_HEADINGS):
        raise SpectPlainTextPreviewError("SPECT report headings drifted from the frozen Step 30 contract.")
    warnings = list(_require_sequence(view_model.get("warnings"), "SPECT warnings"))
    if warnings != list(SPECT_REPORT_SECTION_WARNINGS):
        raise SpectPlainTextPreviewError("SPECT report warnings drifted from the frozen Step 30 contract.")

    source = _require_mapping(view_model.get("source_summary"), "SPECT source summary")
    if list(source.get("field_order", ())) != list(SPECT_SOURCE_DISPLAY_FIELDS):
        raise SpectPlainTextPreviewError("SPECT source field order drifted.")
    source_rows = list(_require_sequence(source.get("rows"), "SPECT source rows"))
    if [row.get("field") for row in source_rows if isinstance(row, Mapping)] != list(SPECT_SOURCE_DISPLAY_FIELDS):
        raise SpectPlainTextPreviewError("SPECT source rows do not match the frozen field order.")
    if len(source_rows) != len(SPECT_SOURCE_DISPLAY_FIELDS):
        raise SpectPlainTextPreviewError("SPECT source row count drifted.")

    table = _require_mapping(view_model.get("barrier_table"), "SPECT barrier table")
    if list(table.get("field_order", ())) != list(SPECT_BARRIER_TABLE_FIELDS):
        raise SpectPlainTextPreviewError("SPECT barrier field order drifted.")
    columns = list(_require_sequence(table.get("columns"), "SPECT barrier columns"))
    if [col.get("field") for col in columns if isinstance(col, Mapping)] != list(SPECT_BARRIER_TABLE_FIELDS):
        raise SpectPlainTextPreviewError("SPECT barrier columns do not match the frozen field order.")
    rows = list(_require_sequence(table.get("rows"), "SPECT barrier rows"))
    if not rows:
        raise SpectPlainTextPreviewError("SPECT plain-text preview requires at least one barrier row.")
    for index, row in enumerate(rows):
        row = _require_mapping(row, f"SPECT barrier row {index}")
        if tuple(row) != SPECT_BARRIER_TABLE_FIELDS:
            raise SpectPlainTextPreviewError(f"SPECT barrier row {index} field order drifted.")

    provenance = _require_mapping(view_model.get("provenance"), "SPECT provenance")
    if list(provenance.get("field_order", ())) != list(SPECT_PROVENANCE_DISPLAY_FIELDS):
        raise SpectPlainTextPreviewError("SPECT provenance field order drifted.")
    provenance_rows = list(_require_sequence(provenance.get("rows"), "SPECT provenance rows"))
    if [row.get("field") for row in provenance_rows if isinstance(row, Mapping)] != list(SPECT_PROVENANCE_DISPLAY_FIELDS):
        raise SpectPlainTextPreviewError("SPECT provenance rows do not match the frozen field order.")


def _display_value(value: Any, unit: Any = "") -> str:
    text = _single_line(value, "SPECT preview value")
    unit_text = _single_line(unit, "SPECT preview unit") if unit else ""
    return f"{text} {unit_text}" if unit_text else text


def render_non_issueable_spect_plain_text_preview(view_model: Mapping[str, Any]) -> str:
    """Render a deterministic, non-issueable text preview from the Step 30 view-model."""
    _validate_view_model(view_model)

    headings = view_model["headings"]
    lines: list[str] = [
        SPECT_PLAIN_TEXT_PREVIEW_HEADER,
        "=" * len(SPECT_PLAIN_TEXT_PREVIEW_HEADER),
        "",
        headings["section"],
        "",
        "WARNINGS",
        "--------",
    ]
    lines.extend(f"- {_single_line(warning, 'SPECT warning')}" for warning in view_model["warnings"])

    lines.extend(["", headings["source_summary"], "-" * len(headings["source_summary"])])
    for row in view_model["source_summary"]["rows"]:
        label = _single_line(row["label"], "SPECT source label")
        lines.append(f"{label}: {_display_value(row['value'], row.get('unit', ''))}")

    lines.extend(["", headings["barrier_results"], "-" * len(headings["barrier_results"])])
    columns = {column["field"]: column for column in view_model["barrier_table"]["columns"]}
    for index, row in enumerate(view_model["barrier_table"]["rows"], 1):
        barrier_name = _single_line(row["barrier_name"], "SPECT barrier name")
        lines.extend([f"Barrier {index}: {barrier_name}", "~" * (11 + len(str(index)) + len(barrier_name))])
        for field in SPECT_BARRIER_TABLE_FIELDS:
            if field == "barrier_name":
                continue
            column = columns[field]
            label = _single_line(column["label"], "SPECT barrier column label")
            lines.append(f"{label}: {_display_value(row[field], column.get('unit', ''))}")
        if index != len(view_model["barrier_table"]["rows"]):
            lines.append("")

    lines.extend(["", headings["provenance"], "-" * len(headings["provenance"])])
    for row in view_model["provenance"]["rows"]:
        field = _single_line(row["field"], "SPECT provenance field")
        value = _single_line(row["value"], "SPECT provenance value")
        lines.append(f"{field}: {value}")

    lines.extend([
        "",
        f"Preview contract: v{SPECT_PLAIN_TEXT_PREVIEW_CONTRACT_VERSION} — {SPECT_PLAIN_TEXT_PREVIEW_BASELINE}",
        SPECT_PLAIN_TEXT_PREVIEW_FOOTER,
    ])
    return "\n".join(lines) + "\n"
