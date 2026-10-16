from __future__ import annotations

from typing import Any, Dict

from modalities.registry import get_modality_plugin


def solver_reasoning_text(room: Room, barrier: Barrier, live: Dict[str, Any]) -> str:
    solver_used = str(live.get("solver_used", "") or "").strip()
    ct_solver = str(live.get("ct_solver_used", "") or "").strip()
    dominant = str(live.get("dominant_component", "") or "").strip()
    role = str(getattr(barrier, "barrier_role", "") or "").strip()
    modality = str(getattr(room, "modality", "") or "").strip()
    plugin = get_modality_plugin(modality)
    source_specs = plugin.source_specs() if plugin is not None else ()

    reasons = []

    if solver_used:
        reasons.append(f"Primary solver path: {solver_used}")

    uses_primary_solver = any(source.ncrp_solver_mode == "ncrp_primary" for source in source_specs)
    if uses_primary_solver:
        if role.startswith("primary_"):
            reasons.append("Barrier role is primary, so the primary X-ray pathway is used")
        elif role.startswith("secondary_"):
            reasons.append("Barrier role is secondary, so leakage / scatter pathway is used")

    has_ct_component = any(source.role == "ct_ksec_scatter" for source in source_specs)
    if has_ct_component and ct_solver:
        reasons.append(f"CT component used: {ct_solver}")

    has_patient_component = bool(plugin and plugin.spec.patient_radioactivity_present)
    if has_patient_component and dominant.lower() in {"nm", "nm_patient", "spect", "spect patient"}:
        reasons.append("NM patient component contributes to the governing barrier result")

    if dominant:
        reasons.append(f"Dominant component: {dominant}")

    if not reasons:
        reasons.append("Default solver pathway applied from room modality and barrier role")

    return " | ".join(reasons)
