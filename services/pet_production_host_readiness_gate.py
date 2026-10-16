"""PET production-host readiness audit gate.

This Step 26 boundary audits whether the already-frozen PET physics, persisted
working state, dispatch, Results, and report-preview contracts are ready for a
controlled promotion into the normal desktop production host.

It does not enable PET in the production registry and it does not open issued
PDF, machine export, certification, or signature paths.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from modalities.pet import PET_MODALITY
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
    PetWorkingProjectState,
    pet_working_project_state_to_dict,
)
from services.pet_report_readiness_contract import PET_REPORT_INTEGRATION_OPEN
from modalities.pet import pet_source_readiness_result
from services.source_readiness import PET_WORKING_STATE_OUTPUT_BLOCK_REASON

PET_PRODUCTION_HOST_READINESS_CONTRACT_VERSION = 1
PET_PRODUCTION_HOST_READINESS_BASELINE = "pet-production-host-readiness-step26-v1"
PET_PRODUCTION_HOST_INTEGRATION_ENABLED = True


def _check(name: str, passed: bool, detail: str, *, blocker: bool = False) -> Dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "blocker": bool(blocker and not passed),
        "detail": detail,
    }


def audit_pet_production_host_readiness(*, sample_state: PetWorkingProjectState | None = None) -> Dict[str, Any]:
    """Return the explicit PET parity blockers without changing runtime state."""
    checks: List[Dict[str, Any]] = []

    approved_physics = Path("data/pet/pet_radionuclide_physics_approved.json").exists()
    approved_attenuation = Path("data/pet/pet_511kev_attenuation_production_approved.json").exists()
    checks.append(_check(
        "approved_physics_foundation",
        approved_physics and approved_attenuation,
        "Approved PET radionuclide and 511 keV attenuation datasets are present.",
        blocker=True,
    ))

    dispatch_present = Path("engine/pet_project_dispatch.py").exists()
    checks.append(_check(
        "persisted_working_state_dispatch",
        dispatch_present,
        "Persisted PET working state has an isolated replay-verified dispatch boundary.",
        blocker=True,
    ))

    results_present = Path("services/pet_results_model.py").exists()
    checks.append(_check(
        "canonical_results_model",
        results_present,
        "Canonical in-app PET Results adapter is present.",
        blocker=True,
    ))

    report_preview_present = Path("services/pet_report_plain_text_preview.py").exists()
    checks.append(_check(
        "non_issueable_report_preview",
        report_preview_present and PET_REPORT_INTEGRATION_OPEN is False,
        "Frozen PET report boundary is present and remains non-issueable.",
        blocker=True,
    ))

    registry_open = "PET" in production_modality_names() and bool(PET_MODALITY.production_enabled)
    checks.append(_check(
        "production_registry",
        registry_open,
        "PET must be promoted through the modality registry for normal host room admission.",
        blocker=True,
    ))

    pet_source_type = PET_MODALITY.expected_sources[0].source_type
    generic_dispatch_open = source_calculation_blocked_reason(pet_source_type) == ""
    checks.append(_check(
        "legacy_generic_source_dispatch",
        not generic_dispatch_open,
        "The legacy generic PET source shielding-engine route must remain blocked; production PET uses the dedicated dispatch boundary.",
        blocker=True,
    ))

    schema_current = PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3" and PET_WORKING_PROJECT_STATE_VERSION == 3
    schema_host_eligible = schema_current
    if sample_state is not None:
        payload = pet_working_project_state_to_dict(sample_state)
        schema_host_eligible = (
            payload.get("production_host_enabled") is True
            and payload.get("production_calculation_enabled") is True
            and payload.get("issued_output_enabled") is False
        )
    checks.append(_check(
        "working_state_host_semantics",
        schema_current and schema_host_eligible,
        "Durable PET working-state schema must evolve from historical production_eligible=False to current host/calculation semantics with backward-compatible loading.",
        blocker=True,
    ))

    readiness = pet_source_readiness_result(
        PET_MODALITY.expected_sources[0].source_type,
        {},
        {"room_name": "PET host audit", "source_name": "PET Patient Source"},
    )
    readiness_promoted = (
        readiness.get("blocking") is False
        and readiness.get("output_blocking") is True
        and readiness.get("overall_status") == "REVIEW"
    )
    checks.append(_check(
        "source_readiness_host_semantics",
        readiness_promoted,
        f"PET source readiness is calculation/Results-nonblocking while issued output remains blocked: {PET_WORKING_STATE_OUTPUT_BLOCK_REASON}",
        blocker=True,
    ))

    issued_output_closed = PET_REPORT_INTEGRATION_OPEN is False
    checks.append(_check(
        "issued_output_boundary_closed",
        issued_output_closed,
        "Issued PET PDF/export/certification remains closed and is not part of host promotion.",
        blocker=True,
    ))

    blockers = [row["name"] for row in checks if row["blocker"]]
    foundations = [
        "approved_physics_foundation",
        "persisted_working_state_dispatch",
        "canonical_results_model",
        "non_issueable_report_preview",
        "legacy_generic_source_dispatch",
        "issued_output_boundary_closed",
    ]
    foundation_ok = all(next(row for row in checks if row["name"] == name)["passed"] for name in foundations)

    return {
        "contract_version": PET_PRODUCTION_HOST_READINESS_CONTRACT_VERSION,
        "baseline": PET_PRODUCTION_HOST_READINESS_BASELINE,
        "validated_foundations": foundation_ok,
        "production_host_integration_enabled": PET_PRODUCTION_HOST_INTEGRATION_ENABLED,
        "production_host_ready": foundation_ok and not blockers and PET_PRODUCTION_HOST_INTEGRATION_ENABLED,
        "issued_output_enabled": False,
        "checks": checks,
        "blocking_checks": blockers,
        "recommended_next_step": (
            "PET host parity next step: add the isolated non-issueable PDF readiness/preview boundary while keeping issued output closed."
        ),
    }
