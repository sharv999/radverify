from __future__ import annotations

"""
Output generation pipeline.

This is the single orchestration layer for the Generate Outputs action:

    app state
        -> sync latest UI state
        -> source readiness preflight
        -> canonical payload
        -> PDF render
        -> JSON/CSV exports
        -> structured result

The canonical payload remains owned by reports.results_payload_builder.
PDF rendering remains owned by reports.report_generator.
Machine-readable export writing remains owned by reports.results_exporter.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from reports.results_payload_builder import build_results_payload
from reports.results_exporter import write_results_exports_from_payload
from reports.report_generator import pdf_payload_with_project_context, render_pdf_from_payload
from services.project_state_sync import sync_project_state_for_outputs
from services.export_eligibility import (
    apply_export_eligibility_to_payload,
    assess_export_eligibility,
    build_export_prompt_message,
)
from services.output_status_messages import output_result_summary_lines
from services.pet_spect_preliminary_pdf_issuance import (
    authorize_issueable_preliminary_pet_spect_pdf,
    is_pet_spect_preliminary_pdf_candidate,
)


ConfirmCallback = Callable[[str, bool], bool]


@dataclass(frozen=True)
class OutputGenerationResult:
    pdf_path: Optional[Path]
    export_paths: Dict[str, Path] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    preflight: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    export_eligibility: Optional[Dict[str, Any]] = None
    cancelled: bool = False

    @property
    def generated(self) -> bool:
        return self.pdf_path is not None and not self.cancelled

    def summary_lines(self) -> List[str]:
        return output_result_summary_lines(self)


def generate_outputs_from_app(
    *,
    app: Any,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    report_revision: str = "Rev 0",
    report_status: str = "Draft",
    reviewer_name: str = "",
    company_name: str = "healthphysics.ai",
    confirm_callback: ConfirmCallback | None = None,
) -> OutputGenerationResult:
    """
    Generate the PDF report and machine-readable exports from one canonical payload.

    confirm_callback(message, blocking) should return True to proceed and False to
    cancel when preflight warnings or blocking issues are present.
    """
    output_path = Path(output_path)

    _sync_app_state_before_outputs(app)

    preflight = _run_source_readiness_preflight(app)
    pet_spect_preliminary_candidate = is_pet_spect_preliminary_pdf_candidate(app, report_status)
    preliminary_eligibility = assess_export_eligibility(
        preflight=preflight,
        requested_report_status=report_status,
    )
    blocking_issues = list(preliminary_eligibility.blocking_reasons)
    warnings = list(preliminary_eligibility.warnings)
    blocking = bool(blocking_issues)

    if (
        preliminary_eligibility.requires_acknowledgement
        and confirm_callback is not None
        and not pet_spect_preliminary_candidate
    ):
        message = build_export_prompt_message(preliminary_eligibility)
        if not confirm_callback(message, blocking):
            return OutputGenerationResult(
                pdf_path=None,
                export_paths={},
                payload={},
                preflight=preflight,
                warnings=warnings,
                blocking_issues=blocking_issues,
                export_eligibility=preliminary_eligibility.to_dict(),
                cancelled=True,
            )

    payload = build_results_payload(
        app=app,
        logo_path=Path(logo_path) if logo_path else None,
        report_revision=report_revision,
        report_status=report_status,
        reviewer_name=reviewer_name,
        company_name=company_name,
    )
    final_eligibility = apply_export_eligibility_to_payload(
        payload,
        preflight=preflight,
        requested_report_status=report_status,
    )

    if pet_spect_preliminary_candidate:
        authorize_issueable_preliminary_pet_spect_pdf(payload)
        final_eligibility_dict = dict(payload.get("export_eligibility", {}) or {})
        can_export_pdf = bool(final_eligibility_dict.get("can_export_pdf", False))
        can_export_csv = bool(final_eligibility_dict.get("can_export_csv", False))
        blocking_reasons = list(final_eligibility_dict.get("blocking_reasons", []) or [])
    else:
        final_eligibility_dict = final_eligibility.to_dict()
        can_export_pdf = final_eligibility.can_export_pdf
        can_export_csv = final_eligibility.can_export_csv
        blocking_reasons = list(final_eligibility.blocking_reasons)

    if not can_export_pdf:
        raise ValueError("PDF export blocked by report gate: " + "; ".join(blocking_reasons))

    # Enrich only the PDF renderer input with presentation-only project context.
    # The canonical payload remains unchanged for JSON/CSV exports and physics results.
    pdf_payload = pdf_payload_with_project_context(payload, app)
    render_pdf_from_payload(pdf_payload, output_path)
    can_export_barrier_results_json = can_export_csv or pet_spect_preliminary_candidate
    export_paths = (
        write_results_exports_from_payload(
            payload,
            output_path,
            include_csv=False,
        )
        if can_export_barrier_results_json
        else {}
    )

    _refresh_app_after_outputs(app)

    return OutputGenerationResult(
        pdf_path=output_path,
        export_paths=export_paths,
        payload=payload,
        preflight=preflight,
        warnings=list(final_eligibility_dict.get("warnings", []) or []),
        blocking_issues=list(final_eligibility_dict.get("blocking_reasons", []) or []),
        export_eligibility=final_eligibility_dict,
        cancelled=False,
    )


def _sync_app_state_before_outputs(app: Any) -> None:
    sync_project_state_for_outputs(app)



def _run_source_readiness_preflight(app: Any) -> Dict[str, Any]:
    if not hasattr(app, "validate_project_source_readiness"):
        return {
            "blocking": False,
            "overall_status": "UNKNOWN",
            "errors": [],
            "warnings": [],
        }

    try:
        preflight = app.validate_project_source_readiness()
    except Exception as exc:
        return {
            "blocking": True,
            "overall_status": "FAIL",
            "errors": [f"Source validation failed: {exc}"],
            "warnings": [],
        }

    if not isinstance(preflight, dict):
        return {
            "blocking": False,
            "overall_status": "UNKNOWN",
            "errors": [],
            "warnings": [],
        }

    return preflight


def _preflight_prompt_message(
    blocking_issues: List[str],
    warnings: List[str],
    blocking: bool,
) -> str:
    lines: List[str] = []

    if blocking_issues:
        lines.append("Critical source validation issue(s):")
        lines.extend(f"• {item}" for item in blocking_issues[:8])

    if warnings:
        if lines:
            lines.append("")
        lines.append("Source validation warning(s):")
        lines.extend(f"• {item}" for item in warnings[:8])

    lines.append("")
    if blocking:
        lines.append(
            "A Draft report can still be generated, but it will be flagged as incomplete/review-required."
        )
    lines.append("Generate Draft report anyway?")

    return "\n".join(lines)


def _refresh_app_after_outputs(app: Any) -> None:
    try:
        app.refresh_results_tab()
    except Exception:
        pass

    try:
        app._safe_refresh_barrier_schedule()
    except Exception:
        pass
