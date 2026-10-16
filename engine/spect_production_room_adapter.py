"""Production room-to-request adapter for SPECT Step 26/27.

This engine-layer adapter owns conversion of durable room barrier fields into
the frozen Step 5 request type. Production-facing services therefore do not
import the historical Step 5 contract directly.
"""
from __future__ import annotations

from typing import Any

from engine.spect_barrier_schedule import SpectBarrierScheduleRequest


class SpectProductionRoomAdapterError(ValueError):
    """Raised when a room cannot be adapted to production SPECT requests."""


def _material_key(barrier: Any) -> str:
    material = str(getattr(barrier, "material", "") or "").strip().lower()
    legacy = str(getattr(barrier, "material_legacy", "") or "").strip().lower()
    detail = f"{material} {legacy}"
    if material in {"pb", "lead"} or "lead" in material:
        return "lead"
    if "gypsum" in material or "plasterboard" in material or "drywall" in material:
        return "gypsum"
    if "concrete" in material:
        return "concrete_1600kg_m3" if ("light" in detail or "1600" in detail) else "concrete_2300kg_m3"
    if "glass" in material:
        return "glass"
    if "steel" in material or "a514" in material:
        return "steel_a514"
    if not material:
        if "lead" in legacy or " pb" in f" {legacy}":
            return "lead"
        if "gypsum" in legacy or "plasterboard" in legacy or "drywall" in legacy:
            return "gypsum"
        if "concrete" in legacy:
            return "concrete_1600kg_m3" if ("light" in legacy or "1600" in legacy) else "concrete_2300kg_m3"
        if "glass" in legacy:
            return "glass"
        if "steel" in legacy or "a514" in legacy:
            return "steel_a514"
    raise SpectProductionRoomAdapterError(
        f"Barrier {getattr(barrier, 'name', '')!r} uses unsupported SPECT production material "
        f"{getattr(barrier, 'material', '')!r}."
    )


def build_spect_production_room_requests(room: Any) -> tuple[SpectBarrierScheduleRequest, ...]:
    if room is None or str(getattr(room, "modality", "") or "").strip().upper() != "SPECT":
        raise SpectProductionRoomAdapterError("Production SPECT calculation requires a SPECT room.")
    barriers = tuple(getattr(room, "barriers", ()) or ())
    if not barriers:
        raise SpectProductionRoomAdapterError("SPECT room has no barriers to calculate.")
    requests = []
    for index, barrier in enumerate(barriers):
        name = str(getattr(barrier, "name", "") or f"Barrier {index + 1}").strip()
        try:
            requests.append(
                SpectBarrierScheduleRequest(
                    barrier_id=f"room-barrier-{index + 1}",
                    barrier_name=name,
                    material_key=_material_key(barrier),
                    distance_m=float(getattr(barrier, "distance_m", 0.0)),
                    occupancy_factor=float(getattr(barrier, "occupancy_factor", 0.0)),
                    design_goal_uSv_per_week=float(getattr(barrier, "design_goal_uSv_per_week", 0.0)),
                    provided_thickness_mm=float(getattr(barrier, "thickness_mm", 0.0)),
                    source_name="SPECT Patient Source",
                )
            )
        except Exception as exc:
            raise SpectProductionRoomAdapterError(f"Barrier {name!r}: {exc}") from exc
    return tuple(requests)
