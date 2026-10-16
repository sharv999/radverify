"""SPECT Step 24 production-dispatch readiness audit and explicit gate.

Step 24 introduced the fail-closed gate after verifying the Step 20--23
foundations.  Step 25 resolved the low-transmission production policy.  Step 26
now explicitly opens the *headless production calculation entry point* while
keeping desktop modality registration, Results, reports, export and
certification integration closed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest
from engine.spect_calculation_request_contract import (
    current_spect_calculation_physics_freeze,
)
from engine.spect_practical_transmission import (
    load_frozen_spect_tc99m_practical_dataset,
)
from engine.spect_radionuclide_data import load_frozen_spect_radionuclide_dataset
from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
    SPECT_LOW_TRANSMISSION_POLICY_BASIS,
    SPECT_LOW_TRANSMISSION_POLICY_VERSION,
    SPECT_LOW_TRANSMISSION_THRESHOLD,
)
from engine.spect_working_project_request import build_spect_working_calculation_request
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, spect_source_readiness_result
from serialization.spect_working_project_state import SpectWorkingProjectState
from services.spect_regression_verification import load_manifest, run_manifest


ROOT = Path(__file__).resolve().parents[1]
SPECT_STEP20_MANIFEST = ROOT / "data" / "spect" / "spect_physics_approval_manifest.json"
SPECT_STEP21_REPLAY_MANIFEST = (
    ROOT / "tests" / "fixtures" / "spect_requests" / "spect_cli_regression_manifest.json"
)

SPECT_PRODUCTION_DISPATCH_GATE_VERSION = 2
SPECT_PRODUCTION_DISPATCH_ENABLED = True
SPECT_LOW_TRANSMISSION_PRODUCTION_POLICY_APPROVED = SPECT_LOW_TRANSMISSION_POLICY_APPROVED
SPECT_LOW_TRANSMISSION_BLOCK_REASON = (
    "SPECT production policy for the room-scatter caution region (target transmission <= 1%) "
    "is not approved."
)
SPECT_DISPATCH_DISABLED_REASON = (
    "SPECT production calculation dispatch has not been explicitly enabled."
)
SPECT_DISPATCH_ENABLED_BASIS = (
    "Step 26 explicitly enables the isolated headless production calculation entry point only; "
    "desktop registry, Results, reports, export and certification remain closed."
)


class SpectProductionDispatchBlockedError(RuntimeError):
    """Raised when a caller attempts to cross the Step 24 production gate."""


@dataclass(frozen=True)
class SpectProductionReadinessCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class SpectProductionDispatchReadiness:
    gate_version: int
    production_ready: bool
    dispatch_enabled: bool
    validated_foundations: bool
    checks: tuple[SpectProductionReadinessCheck, ...]
    blocking_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_version": self.gate_version,
            "production_ready": self.production_ready,
            "dispatch_enabled": self.dispatch_enabled,
            "validated_foundations": self.validated_foundations,
            "checks": [asdict(check) for check in self.checks],
            "blocking_reasons": list(self.blocking_reasons),
        }


def _check_step20_physics() -> SpectProductionReadinessCheck:
    freeze = current_spect_calculation_physics_freeze()
    source_path = ROOT / "data" / "spect" / "spect_radionuclide_physics_approved_frozen.json"
    practical_path = ROOT / "data" / "spect" / "spect_tc99m_practical_transmission_approved_frozen.json"
    source = load_frozen_spect_radionuclide_dataset(source_path)
    practical = load_frozen_spect_tc99m_practical_dataset(practical_path)
    if not freeze.get("freeze_id"):
        raise SpectProductionDispatchBlockedError("Step 20 SPECT physics freeze ID is missing.")
    if not source.records or not practical.records:
        raise SpectProductionDispatchBlockedError("Step 20 frozen SPECT physics datasets are empty.")
    return SpectProductionReadinessCheck(
        "Step 20 physics freeze",
        "PASS",
        f"Approved/frozen Tc-99m source and practical-transmission datasets verified ({freeze['freeze_id']}).",
    )


def _check_step21_replay() -> SpectProductionReadinessCheck:
    manifest = load_manifest(SPECT_STEP21_REPLAY_MANIFEST)
    freeze_id = current_spect_calculation_physics_freeze()["freeze_id"]
    if manifest.get("physics_freeze_id") != freeze_id:
        raise SpectProductionDispatchBlockedError(
            "Step 21 replay manifest physics freeze does not match Step 20."
        )
    _, cases = run_manifest(SPECT_STEP21_REPLAY_MANIFEST)
    if not cases or not all(bool(case[1]) for case in cases):
        raise SpectProductionDispatchBlockedError("Step 21 deterministic SPECT replay verification failed.")
    return SpectProductionReadinessCheck(
        "Step 21 deterministic replay",
        "PASS",
        f"{len(cases)} pinned canonical calculation fixture(s) replay verified.",
    )


def _check_step22_blocker() -> SpectProductionReadinessCheck:
    readiness = spect_source_readiness_result(
        "spect_patient",
        {},
        {"room_name": "SPECT readiness audit", "source_name": "SPECT patient"},
    )
    if (
        readiness.get("output_blocking") is not True
        or source_calculation_blocked_reason("spect_patient") != SPECT_CALCULATION_BLOCK_REASON
    ):
        raise SpectProductionDispatchBlockedError(
            "Step 22/34 SPECT generic-calculation or issued-output blocker is not active."
        )
    return SpectProductionReadinessCheck(
        "Step 22 source/output blocker",
        "PASS",
        "The legacy generic SPECT source calculator and all issued-output paths remain fail-closed; "
        "Step 34 host calculation/Results use only the gated production dispatch boundary.",
    )


def _check_step23_working_state(
    state: SpectWorkingProjectState | None,
    barrier_requests: Sequence[SpectBarrierScheduleRequest] | None,
) -> SpectProductionReadinessCheck:
    if state is None and barrier_requests is None:
        return SpectProductionReadinessCheck(
            "Step 23 working-project boundary",
            "PASS",
            "Durable SPECT working-state contract is installed; no concrete dispatch request was supplied to this audit.",
        )
    if state is None or barrier_requests is None:
        raise SpectProductionDispatchBlockedError(
            "A production-dispatch audit requires both SPECT working state and barrier requests when either is supplied."
        )
    # Construction validates Step 20 freeze + Step 21 canonical request identity.
    build_spect_working_calculation_request(state, tuple(barrier_requests))
    return SpectProductionReadinessCheck(
        "Step 23 working-project boundary",
        "PASS",
        "Working source state reconstructs a valid Step 21 canonical request without opening production dispatch.",
    )


def assess_spect_production_dispatch_readiness(
    *,
    state: SpectWorkingProjectState | None = None,
    barrier_requests: Sequence[SpectBarrierScheduleRequest] | None = None,
) -> SpectProductionDispatchReadiness:
    """Audit the current SPECT production-dispatch boundary.

    Step 26 permits readiness only after the Step 20--23 foundations, approved
    Step 25 low-transmission policy, and the explicit isolated dispatch switch
    all pass.  Registry/report/output integration remains a separate boundary.
    """

    checks = [
        _check_step20_physics(),
        _check_step21_replay(),
        _check_step22_blocker(),
        _check_step23_working_state(state, barrier_requests),
    ]
    blocking: list[str] = []

    if SPECT_LOW_TRANSMISSION_PRODUCTION_POLICY_APPROVED:
        checks.append(
            SpectProductionReadinessCheck(
                "Low-transmission production policy",
                "PASS",
                f"Approved Step 25 policy v{SPECT_LOW_TRANSMISSION_POLICY_VERSION}: required transmission "
                f"<= {SPECT_LOW_TRANSMISSION_THRESHOLD:.2f} requires geometry-specific review; automatic "
                "production assessment above that boundary uses thickness comparison and does not rely on "
                "ultralow modeled transmitted-dose values. " + SPECT_LOW_TRANSMISSION_POLICY_BASIS,
            )
        )
    else:
        checks.append(
            SpectProductionReadinessCheck(
                "Low-transmission production policy",
                "FAIL",
                SPECT_LOW_TRANSMISSION_BLOCK_REASON,
            )
        )
        blocking.append(SPECT_LOW_TRANSMISSION_BLOCK_REASON)

    if SPECT_PRODUCTION_DISPATCH_ENABLED:
        checks.append(
            SpectProductionReadinessCheck(
                "Explicit production dispatch switch",
                "PASS",
                SPECT_DISPATCH_ENABLED_BASIS,
            )
        )
    else:
        checks.append(
            SpectProductionReadinessCheck(
                "Explicit production dispatch switch",
                "FAIL",
                SPECT_DISPATCH_DISABLED_REASON,
            )
        )
        blocking.append(SPECT_DISPATCH_DISABLED_REASON)

    # Step 34 promotes SPECT into the registry-driven production host after
    # Steps 20-33 have frozen calculation, Results, and non-issueable report
    # boundaries. Issued output remains independently gated.
    if "SPECT" in production_modality_names():
        checks.append(
            SpectProductionReadinessCheck(
                "Production modality registry",
                "PASS",
                "SPECT is enabled in the controlled production host registry; issued output remains separately gated.",
            )
        )
    else:
        blocking.append("SPECT is not enabled in the production host registry.")
        checks.append(
            SpectProductionReadinessCheck(
                "Production modality registry",
                "FAIL",
                blocking[-1],
            )
        )

    validated_foundations = all(check.status == "PASS" for check in checks[:4])
    production_ready = validated_foundations and not blocking
    dispatch_enabled = production_ready and SPECT_PRODUCTION_DISPATCH_ENABLED
    return SpectProductionDispatchReadiness(
        gate_version=SPECT_PRODUCTION_DISPATCH_GATE_VERSION,
        production_ready=production_ready,
        dispatch_enabled=dispatch_enabled,
        validated_foundations=validated_foundations,
        checks=tuple(checks),
        blocking_reasons=tuple(blocking),
    )


def require_spect_production_dispatch_enabled(
    state: SpectWorkingProjectState,
    barrier_requests: Sequence[SpectBarrierScheduleRequest],
):
    """Fail closed unless the Step 26 isolated production entry may execute.

    This gate authorises only the dedicated headless Step 26 dispatcher.  It
    does not authorise desktop registry promotion, Results/report integration,
    export, certification, or any other SPECT production surface.
    """
    readiness = assess_spect_production_dispatch_readiness(
        state=state,
        barrier_requests=barrier_requests,
    )
    if not readiness.dispatch_enabled:
        detail = "; ".join(readiness.blocking_reasons) or "SPECT production dispatch is blocked."
        raise SpectProductionDispatchBlockedError(detail)
    return readiness
