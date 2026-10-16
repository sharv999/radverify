"""Normal Results-model adapter for persisted PET calculations.

This module opens PET to the ordinary in-app Results presentation only. It does
not participate in report payloads, exports, certification, or the legacy
SourceSpec calculation path.
"""
from __future__ import annotations

from typing import Any, Dict, List

from engine.pet_project_dispatch import dispatch_persisted_pet_working_state
from services.source_readiness import room_has_persisted_pet_working_state
from engine.pet_calculation_input_provenance import load_pet_calculation_input_provenance_manifest
from modalities.pet import PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
from services.pet_results_presentation_contract import (
    PET_RESULTS_PRESENTATION_CONTRACT_VERSION,
    PET_RESULTS_PRESENTATION_BASELINE,
)

PET_RESULTS_MODEL_CONTRACT_VERSION = 2


def _live_result(barrier: Any, dispatched: Any, *, room_dispatch: Any, manifest: Any) -> Dict[str, Any]:
    solver = dispatched.solver_result
    required = float(solver.required_thickness_mm)
    provided = float(dispatched.provided_thickness_mm)
    material = str(getattr(barrier, "material", "") or "")
    material_key = str(dispatched.material_key)
    required_lead = required if material_key == "lead" else None
    required_concrete = required if material_key == "concrete_2350kg_m3" else None
    transmitted = solver.transmitted_weekly_dose_uSv
    return {
        "results_model_contract_version": PET_RESULTS_MODEL_CONTRACT_VERSION,
        "results_presentation_contract_version": PET_RESULTS_PRESENTATION_CONTRACT_VERSION,
        "results_presentation_baseline": PET_RESULTS_PRESENTATION_BASELINE,
        "barrier_name": str(getattr(barrier, "name", "") or "Barrier"),
        "results_source": "persisted_pet_single_source",
        "source_type": "pet_patient",
        "solver_mode": solver.solver_mode,
        "material": material,
        "distance_m": float(dispatched.distance_m),
        "occupancy_factor": float(dispatched.occupancy_factor),
        "design_goal_uSv_per_week": float(dispatched.design_goal_uSv_per_week),
        "unshielded_weekly_dose_uSv": float(solver.unshielded_weekly_dose_uSv_at_barrier),
        "occupied_unshielded_weekly_dose_uSv": float(solver.occupied_unshielded_weekly_dose_uSv),
        "barrier_transmission_factor_B": float(solver.required_transmission),
        "required_tvl_count": float(solver.required_tvl_count),
        "required_thickness_mm": required,
        "required_lead_mm": required_lead,
        "required_concrete_mm": required_concrete,
        "provided_thickness_mm": provided,
        "provided_transmission": solver.provided_transmission,
        "transmitted_dose_uSv_per_week": transmitted,
        "compliance_status": str(solver.compliance_status),
        "margin_mm": provided - required,
        "source_contributions": "PET patient source",
        "dominant_source": "PET patient source",
        "notes": (
            "In-app PET Results model only. Normal report/export generation remains blocked."
        ),
        "calculation_reasoning": (
            f"Decay-integrated PET workload was scaled to {float(dispatched.distance_m):.3f} m "
            f"by inverse square, occupancy T={float(dispatched.occupancy_factor):.3f} was applied, "
            f"and approved 511 keV attenuation was compared with the provided barrier."
        ),
        "provenance_manifest_id": manifest.manifest_id,
        "provenance_manifest_revision": manifest.revision,
        "radionuclide_dataset_id": manifest.radionuclide_dataset.dataset_id,
        "radionuclide_dataset_revision": manifest.radionuclide_dataset.revision,
        "radionuclide_records_sha256": manifest.radionuclide_dataset.records_sha256,
        "attenuation_records_sha256": manifest.attenuation_dataset.records_sha256,
        "physics_contract_version": manifest.physics_contract_version,
        "solver_contract_version": manifest.solver_contract_version,
        "replay_verified": bool(room_dispatch.replay_verified),
        "attenuation_dataset_id": dispatched.attenuation_dataset_id,
        "attenuation_dataset_revision": dispatched.attenuation_dataset_revision,
    }


def build_room_results_model(project: Any, room: Any, *, fallback_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return ordinary Results rows, using PET dispatch when PET state is present."""
    if not room_has_persisted_pet_working_state(room):
        return list(fallback_results or [])
    dispatched = dispatch_persisted_pet_working_state(project, str(getattr(room, "name", "") or ""))
    if dispatched is None:
        return list(fallback_results or [])
    barriers = list(getattr(room, "barriers", []) or [])
    if len(dispatched.barrier_results) != len(barriers):
        raise ValueError("PET Results model barrier count does not match the room barrier schedule.")
    manifest = load_pet_calculation_input_provenance_manifest(
        PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
    )
    return [
        _live_result(barrier, result, room_dispatch=dispatched, manifest=manifest)
        for barrier, result in zip(barriers, dispatched.barrier_results)
    ]
