"""Step 39 readiness summary for the common PET/SPECT report payload boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from engine.pet_ultralow_transmission_policy import (
    PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED,
    PET_ULTRALOW_TRANSMISSION_POLICY_STATUS,
    PET_ULTRALOW_TRANSMISSION_THRESHOLD,
)
from services.pet_spect_production_output_readiness import assess_pet_spect_production_output_readiness
from services.pet_spect_report_payload_adapter import (
    PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE,
    PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN,
)

STEP39_CONTRACT_VERSION = 1
STEP39_BASELINE = "pet-spect-common-report-payload-readiness-v1"
STEP39_ISSUED_OUTPUT_ENABLEMENT = False


@dataclass(frozen=True)
class Step39Check:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_step39_report_payload_readiness() -> dict[str, Any]:
    step38 = assess_pet_spect_production_output_readiness()
    checks = (
        Step39Check(
            "pet_ultralow_policy_locked",
            PET_ULTRALOW_TRANSMISSION_POLICY_APPROVED is True
            and PET_ULTRALOW_TRANSMISSION_POLICY_STATUS == "approved_locked"
            and PET_ULTRALOW_TRANSMISSION_THRESHOLD == 0.01,
            "PET ultralow-transmission report-acceptance policy is approved, locked, and set to the 0.01 validation boundary.",
        ),
        Step39Check(
            "common_adapter_non_issueable",
            PET_SPECT_REPORT_PAYLOAD_ADAPTER_ISSUEABLE is False
            and PET_SPECT_REPORT_PAYLOAD_ADAPTER_REPORT_INTEGRATION_OPEN is False,
            "Common PET/SPECT payload adapter remains non-issueable and disconnected from normal report routing.",
        ),
        Step39Check(
            "production_host_foundations_ready",
            step38.get("pet_calculation_production_ready") is True
            and step38.get("spect_calculation_production_ready") is True,
            "PET and SPECT production-host calculation/Results foundations remain ready.",
        ),
        Step39Check(
            "issued_output_still_closed",
            step38.get("issued_pdf_ready") is False
            and step38.get("machine_export_ready") is False
            and step38.get("certification_ready") is False,
            "Issued PDF, machine export, and certification remain closed.",
        ),
        Step39Check(
            "normal_report_integration_fail_closed",
            step38.get("normal_report_payload_ready") is True,
            "Step 40 normal report builder consumes the Step 39 PET/SPECT payload through a fail-closed modality route.",
        ),
    )
    return {
        "contract_version": STEP39_CONTRACT_VERSION,
        "baseline": STEP39_BASELINE,
        "issued_output_enablement": STEP39_ISSUED_OUTPUT_ENABLEMENT,
        "pet_ultralow_policy_ready": checks[0].passed,
        "common_non_issueable_payload_adapter_ready": checks[1].passed,
        "normal_report_integration_ready": checks[4].passed,
        "issued_pdf_ready": False,
        "machine_export_ready": False,
        "certification_ready": False,
        "checks": [check.as_dict() for check in checks],
        "recommended_next_boundary": (
            "Step 40 integration is present. Validate replay/payload equivalence and PET/SPECT report rendering before a separate issued-output enablement decision; PDF/export/certification remain closed."
        ),
    }


def require_step39_foundations_ready() -> dict[str, Any]:
    result = assess_step39_report_payload_readiness()
    failed = [check["detail"] for check in result["checks"] if not check["passed"]]
    if failed:
        raise RuntimeError("Step 39 readiness foundations failed: " + " | ".join(failed))
    return result
