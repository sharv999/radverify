"""Step 40 readiness gate for normal PET/SPECT report-payload integration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.pet_spect_production_output_readiness import assess_pet_spect_production_output_readiness
from services.pet_spect_report_payload_readiness import assess_step39_report_payload_readiness
from services.pet_spect_normal_report_route import (
    PET_SPECT_NORMAL_REPORT_ROUTE_CERTIFICATION_ENABLED,
    PET_SPECT_NORMAL_REPORT_ROUTE_EXPORT_ENABLED,
    PET_SPECT_NORMAL_REPORT_ROUTE_ISSUEABLE,
)

STEP40_CONTRACT_VERSION = 1
STEP40_BASELINE = "pet-spect-normal-report-integration-v1-non-issueable"
STEP40_ISSUED_OUTPUT_ENABLEMENT = False


@dataclass(frozen=True)
class Step40Check:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_step40_normal_report_integration() -> dict[str, Any]:
    step38 = assess_pet_spect_production_output_readiness()
    step39 = assess_step39_report_payload_readiness()
    checks = (
        Step40Check(
            "pet_spect_results_source_of_truth_integrated",
            step38.get("normal_report_payload_ready") is True,
            "Normal report payload consumes validated PET/SPECT Results through the Step 39 adapter.",
        ),
        Step40Check(
            "pet_spect_generic_recalculation_disabled",
            step38.get("report_pipeline_state", {}).get("pet_spect_fail_closed_schedule") is True,
            "PET/SPECT canonical barrier schedule disables generic calculation and opening fallback.",
        ),
        Step40Check(
            "step39_policy_and_adapter_foundations_ready",
            step39.get("pet_ultralow_policy_ready") is True
            and step39.get("common_non_issueable_payload_adapter_ready") is True,
            "Step 39 PET policy and common adapter foundations remain ready.",
        ),
        Step40Check(
            "normal_route_non_issueable",
            PET_SPECT_NORMAL_REPORT_ROUTE_ISSUEABLE is False
            and PET_SPECT_NORMAL_REPORT_ROUTE_EXPORT_ENABLED is False
            and PET_SPECT_NORMAL_REPORT_ROUTE_CERTIFICATION_ENABLED is False,
            "Step 40 route remains non-issueable with machine export and certification disabled.",
        ),
        Step40Check(
            "issued_output_gates_closed",
            step38.get("issued_pdf_ready") is False
            and step38.get("machine_export_ready") is False
            and step38.get("certification_ready") is False,
            "Issued PDF, machine export, certification and signatures remain closed.",
        ),
    )
    integration_ready = all(check.passed for check in checks)
    return {
        "contract_version": STEP40_CONTRACT_VERSION,
        "baseline": STEP40_BASELINE,
        "issued_output_enablement": STEP40_ISSUED_OUTPUT_ENABLEMENT,
        "normal_report_payload_integration_ready": integration_ready,
        "pet_spect_generic_recalculation_disabled": checks[1].passed,
        "issued_pdf_ready": False,
        "machine_export_ready": False,
        "certification_ready": False,
        "checks": [check.as_dict() for check in checks],
        "recommended_next_boundary": (
            "Run representative PET/SPECT save-reopen-replay, payload-equivalence, and visual report validation. Only then consider a separately gated Preliminary/issued PDF enablement step; keep machine export and certification closed unless independently qualified."
        ),
    }


def require_step40_normal_report_integration_ready() -> dict[str, Any]:
    result = assess_step40_normal_report_integration()
    failed = [check["detail"] for check in result["checks"] if not check["passed"]]
    if failed:
        raise RuntimeError("Step 40 normal report integration failed: " + " | ".join(failed))
    return result
