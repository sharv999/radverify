"""Modality-neutral dispatch for the desktop's canonical in-app Results model."""
from __future__ import annotations

from typing import Any, Callable


def build_active_room_results_model(
    project: Any,
    room: Any,
    *,
    pet_builder: Callable[..., list[dict]],
    spect_builder: Callable[..., list[dict]],
    xray_builder: Callable[..., list[dict]],
    generic_builder: Callable[[Any], list[dict]],
) -> list[dict]:
    """Select the Results adapter from the room's active modality.

    Durable PET/SPECT envelopes can survive in legacy/in-memory objects after a
    modality switch.  Envelope presence must therefore never select an adapter;
    only the room's active modality may do so.
    """
    modality = str(getattr(room, "modality", "") or "").strip().upper()
    if modality == "PET":
        return list(pet_builder(project, room, fallback_results=[]) or [])
    if modality == "SPECT":
        return list(spect_builder(project, room, fallback_results=[]) or [])
    if modality == "X-RAY":
        return list(xray_builder(project, room) or [])
    return list(generic_builder(room) or [])
