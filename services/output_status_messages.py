from __future__ import annotations

"""
User-facing output generation status messages.

MVP risk protected:
    Prevent the Generate Outputs UI from implying that all outputs were fully
    generated/certified when the central export gate actually produced a Draft,
    Review Required, Incomplete, PDF-only, or cancelled result.

This module is UI-toolkit-free. It formats the structured OutputGenerationResult
shape into clear title/message text for Tk dialogs, status bars and tests.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class OutputStatusMessage:
    title: str
    status_line: str
    lines: List[str]
    severity: str = "info"

    @property
    def body(self) -> str:
        return "\n".join(self.lines)


def build_output_status_message(result: Any) -> OutputStatusMessage:
    """Build a clear user-facing summary for a generated/cancelled result."""
    if bool(getattr(result, "cancelled", False)):
        return OutputStatusMessage(
            title="Generation cancelled",
            status_line="Report generation cancelled.",
            lines=["Output generation cancelled."],
            severity="info",
        )

    pdf_path = getattr(result, "pdf_path", None)
    export_paths = dict(getattr(result, "export_paths", {}) or {})
    blocking_issues = _unique_texts(getattr(result, "blocking_issues", []) or [])
    warnings = _unique_texts(getattr(result, "warnings", []) or [])
    eligibility = dict(getattr(result, "export_eligibility", {}) or {})
    ai_report = getattr(result, "ai_report", None) or {}

    effective_status = str(eligibility.get("report_status_effective", "") or "").strip()
    can_export_csv = eligibility.get("can_export_csv", None)
    can_certify = eligibility.get("can_certify", None)

    if blocking_issues:
        if pdf_path:
            headline = _blocking_pdf_headline(blocking_issues)
            title = "Draft PDF generated — exports blocked"
            status_line = "Draft PDF generated with blocking issue(s)."
        else:
            headline = "Output generation blocked."
            title = "Generation blocked"
            status_line = "Output generation blocked."
        severity = "warning"
    elif warnings or can_certify is False:
        headline = "Output generated — review required."
        title = "Generation complete — review required"
        status_line = "Output generated with review warning(s)."
        severity = "warning"
    else:
        headline = "Outputs generated successfully."
        title = "Generation complete"
        status_line = "Generated report outputs successfully."
        severity = "info"

    lines: List[str] = [headline]

    if pdf_path:
        lines.append("")
        lines.append("PDF report:")
        lines.append(str(pdf_path))

    if export_paths:
        lines.append("")
        lines.append("Machine-readable exports:")
        for key, path in sorted(export_paths.items()):
            lines.append(f"- {key}: {path}")
    elif pdf_path and (blocking_issues or can_export_csv is False):
        lines.append("")
        lines.append("Machine-readable exports were not generated.")

    if effective_status:
        lines.append("")
        lines.append("Effective report status:")
        lines.append(effective_status)

    if can_certify is not None:
        lines.append("")
        lines.append("Certification permitted:")
        lines.append("Yes" if bool(can_certify) else "No")

    if blocking_issues:
        lines.append("")
        lines.append("Blocking issue(s):")
        lines.extend(f"- {item}" for item in blocking_issues)

    if warnings:
        lines.append("")
        lines.append("Warning(s):")
        lines.extend(f"- {item}" for item in warnings)

    return OutputStatusMessage(
        title=title,
        status_line=status_line,
        lines=lines,
        severity=severity,
    )


def output_result_summary_lines(result: Any) -> List[str]:
    """Compatibility helper for OutputGenerationResult.summary_lines()."""
    return build_output_status_message(result).lines


def _blocking_pdf_headline(blocking_issues: List[str]) -> str:
    joined = " ".join(blocking_issues).lower()
    if "barrier result count" in joined or "calculation" in joined or "opening" in joined:
        return "Draft PDF generated with calculation-integrity issue(s)."
    if "ksec" in joined or "source" in joined:
        return "Draft PDF generated with source-data blocking issue(s)."
    return "Draft PDF generated with blocking issue(s)."


def _unique_texts(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
