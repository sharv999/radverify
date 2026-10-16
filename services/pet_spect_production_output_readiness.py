"""Combined PET/SPECT production-output readiness audit for Step 38.

This module is audit-only.  It deliberately does not open report, PDF, export,
certification, or signature routing.  It compares the completed PET and SPECT
production-host architectures against the ordinary report/output pipeline and
records the remaining blockers before any issueable output integration begins.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engine.pet_ultralow_transmission_policy import (
    PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED,
    PET_ULTRALOW_TRANSMISSION_POLICY_STATUS,
)
from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
    SPECT_LOW_TRANSMISSION_POLICY_STATUS,
    SPECT_LOW_TRANSMISSION_THRESHOLD,
)
from services.pet_architecture_completion import assess_pet_architecture_completion
from services.pet_pdf_integration_readiness_gate import assess_pet_pdf_integration_readiness
from services.pet_release_gate import assess_pet_release_gate
from services.spect_architecture_completion import assess_spect_architecture_completion
from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness
from services.spect_release_gate import assess_spect_release_gate

STEP38_CONTRACT_VERSION = 1
STEP38_BASELINE = "pet-spect-production-output-readiness-audit-v1"
STEP38_AUDIT_ONLY = True
STEP38_ISSUED_OUTPUT_ENABLEMENT = False

# Step 39 resolves the PET ultralow-transmission blocker identified by this
# Step 38 audit. Keep this compatibility alias so the audit now reports that
# policy blocker as resolved while the normal report-routing blockers remain.
PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT = (
    PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED is True
    and PET_ULTRALOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
)


class PetSpectProductionOutputReadinessError(RuntimeError):
    """Raised only if the Step 38 audit foundations themselves are invalid."""


@dataclass(frozen=True)
class OutputReadinessCheck:
    check_id: str
    passed: bool
    blocking_for_issued_output: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _report_pipeline_state() -> dict[str, bool]:
    root = Path(__file__).resolve().parents[1]
    builder_text = (root / "reports" / "results_payload_builder.py").read_text(encoding="utf-8")
    barrier_text = (root / "reports" / "barrier_schedule.py").read_text(encoding="utf-8")

    # CT retains its established generic shielding-engine path.  Step 40 adds a
    # separate PET/SPECT route that consumes canonical modality Results and must
    # never fall back to the generic engine.
    generic_builder_dispatch = (
        "from engine.shielding_engine import compute_room_barrier_table" in builder_text
        and "room_results = compute_room_barrier_table(" in builder_text
    )
    closed_modal_route = (
        "build_non_issueable_pet_spect_room_report_payload" in builder_text
        and "canonical_result_rows_from_room_report_payload" in builder_text
        and "is_pet_spect_report_modality" in builder_text
    )
    consumes_modal_results = closed_modal_route
    schedule_fail_closed = (
        "allow_generic_fallback: bool = True" in barrier_text
        and "if not allow_generic_fallback" in barrier_text
        and "generic recalculation is disabled" in barrier_text
        and "allow_generic_fallback=not pet_spect_room" in builder_text
    )
    generic_schedule_fallback = not schedule_fail_closed
    return {
        "generic_builder_dispatch": generic_builder_dispatch,
        "consumes_modal_results": consumes_modal_results,
        "generic_schedule_fallback": generic_schedule_fallback,
        "pet_spect_fail_closed_schedule": schedule_fail_closed,
        "pet_spect_results_source_of_truth_integrated": closed_modal_route and schedule_fail_closed,
    }


def assess_pet_spect_production_output_readiness() -> dict[str, Any]:
    """Return the combined Step 38 audit without enabling any output surface."""
    pet_arch = assess_pet_architecture_completion()
    spect_arch = assess_spect_architecture_completion()
    pet_release = assess_pet_release_gate()
    spect_release = assess_spect_release_gate()
    pet_pdf = assess_pet_pdf_integration_readiness()
    spect_pdf = assess_spect_pdf_integration_readiness()
    pipeline = _report_pipeline_state()

    checks = (
        OutputReadinessCheck(
            "pet_production_host_complete",
            pet_arch.get("architecture_complete_current_scope") is True
            and pet_release.get("controlled_host_release_ready") is True,
            True,
            "PET production-host persistence, gated calculation, and in-app Results are complete.",
        ),
        OutputReadinessCheck(
            "spect_production_host_complete",
            spect_arch.get("architecture_complete_current_scope") is True
            and spect_release.get("controlled_host_release_ready") is True,
            True,
            "SPECT production-host persistence, gated calculation, and in-app Results are complete.",
        ),
        OutputReadinessCheck(
            "pet_report_preview_foundations_validated",
            pet_pdf.get("validated_foundations") is True,
            True,
            "PET frozen report contracts and non-issueable preview foundations are validated.",
        ),
        OutputReadinessCheck(
            "spect_report_preview_foundations_validated",
            spect_pdf.get("validated_foundations") is True,
            True,
            "SPECT frozen report contracts and non-issueable preview foundations are validated.",
        ),
        OutputReadinessCheck(
            "normal_report_uses_pet_spect_results_source_of_truth",
            pipeline["pet_spect_results_source_of_truth_integrated"],
            True,
            (
                "Normal report payload consumes the validated PET/SPECT Results boundary."
                if pipeline["pet_spect_results_source_of_truth_integrated"]
                else "BLOCKER: normal report payload does not consume the validated PET/SPECT Results boundary through the closed Step 40 route."
            ),
        ),
        OutputReadinessCheck(
            "canonical_schedule_has_no_pet_spect_generic_recalculation_fallback",
            not pipeline["generic_schedule_fallback"],
            True,
            (
                "Canonical report schedule cannot silently recalculate PET/SPECT through the generic engine."
                if not pipeline["generic_schedule_fallback"]
                else "BLOCKER: canonical barrier schedule does not fail closed against generic PET/SPECT recalculation fallback."
            ),
        ),
        OutputReadinessCheck(
            "spect_low_transmission_policy_locked",
            SPECT_LOW_TRANSMISSION_POLICY_APPROVED is True
            and SPECT_LOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
            and SPECT_LOW_TRANSMISSION_THRESHOLD == 0.01,
            True,
            "SPECT <=1% low-transmission production policy remains approved, locked, and fail-closed.",
        ),
        OutputReadinessCheck(
            "pet_ultralow_transmission_policy_explicit",
            PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT is True,
            True,
            (
                "PET has an explicit production policy for interpretation of ultralow transmission results."
                if PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT
                else "BLOCKER: PET has no explicit production policy equivalent to SPECT Step 25 for interpretation of ultralow transmission results; resolve and freeze whether such results may support issueable acceptance."
            ),
        ),
        OutputReadinessCheck(
            "issued_pdf_gates_closed",
            pet_pdf.get("issued_pdf_enabled") is False
            and spect_pdf.get("issued_pdf_enabled") is False
            and pet_pdf.get("pdf_integration_switch_enabled") is False
            and spect_pdf.get("pdf_integration_switch_enabled") is False,
            True,
            "PET and SPECT issued-PDF integration switches remain deliberately closed.",
        ),
        OutputReadinessCheck(
            "machine_export_and_certification_closed",
            pet_release.get("machine_export_enabled") is False
            and pet_release.get("certification_enabled") is False
            and spect_release.get("machine_export_enabled") is False
            and spect_release.get("certification_enabled") is False,
            True,
            "Machine export and certification remain closed for both PET and SPECT.",
        ),
    )

    blockers = [check.detail for check in checks if check.blocking_for_issued_output and not check.passed]
    foundations_ready = all(
        check.passed
        for check in checks
        if check.check_id
        in {
            "pet_production_host_complete",
            "spect_production_host_complete",
            "pet_report_preview_foundations_validated",
            "spect_report_preview_foundations_validated",
            "spect_low_transmission_policy_locked",
        }
    )

    return {
        "contract_version": STEP38_CONTRACT_VERSION,
        "baseline": STEP38_BASELINE,
        "audit_only": STEP38_AUDIT_ONLY,
        "issued_output_enablement": STEP38_ISSUED_OUTPUT_ENABLEMENT,
        "pet_calculation_production_ready": pet_arch.get("architecture_complete_current_scope") is True,
        "spect_calculation_production_ready": spect_arch.get("architecture_complete_current_scope") is True,
        "pet_report_preview_foundations_ready": pet_pdf.get("validated_foundations") is True,
        "spect_report_preview_foundations_ready": spect_pdf.get("validated_foundations") is True,
        "common_output_foundations_ready": foundations_ready,
        "normal_report_payload_ready": pipeline["pet_spect_results_source_of_truth_integrated"]
        and not pipeline["generic_schedule_fallback"],
        "pet_ultralow_transmission_policy_ready": PET_ULTRALOW_TRANSMISSION_POLICY_EXPLICIT,
        "spect_low_transmission_policy_ready": SPECT_LOW_TRANSMISSION_POLICY_APPROVED is True,
        "issued_pdf_ready": False,
        "machine_export_ready": False,
        "certification_ready": False,
        "production_output_enablement_ready": False,
        "checks": [check.as_dict() for check in checks],
        "blocking_reasons": blockers,
        "report_pipeline_state": pipeline,
        "recommended_next_boundary": (
            "Validate Step 40 payload-equivalence and report rendering against representative PET/SPECT cases; keep issued PDF/export/certification switches closed until a separate production-output enablement gate is approved."
        ),
    }


def require_step38_audit_foundations_valid() -> dict[str, Any]:
    """Fail closed only if already-completed production-host foundations regress."""
    result = assess_pet_spect_production_output_readiness()
    foundation_ids = {
        "pet_production_host_complete",
        "spect_production_host_complete",
        "pet_report_preview_foundations_validated",
        "spect_report_preview_foundations_validated",
        "spect_low_transmission_policy_locked",
    }
    failed = [
        check["detail"]
        for check in result["checks"]
        if check["check_id"] in foundation_ids and not check["passed"]
    ]
    if failed:
        raise PetSpectProductionOutputReadinessError("; ".join(failed))
    return result
