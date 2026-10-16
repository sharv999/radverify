"""Active-modality working-state lifecycle for PET/SPECT rooms.

PET and SPECT keep validated source inputs under ``Room.modality_state``.  A
room may be switched between modalities during normal desktop editing, so stale
working-state envelopes from the previous modality must never participate in
calculation dispatch.  This module owns that lifecycle independently of the Tk
source panels.
"""
from __future__ import annotations

from typing import Any

from geometry.pet_preview_position import PetPreviewPosition
from modalities.pet import PetExposurePhase, PetSourceDomain
from modalities.spect import SpectSourceDomain
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_KEY,
    PetWorkingProjectState,
    get_room_pet_working_state,
    set_room_pet_working_state,
)
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_KEY,
    new_spect_working_project_state,
    set_room_spect_working_state,
)


def _geometry_position(room: Any) -> PetPreviewPosition:
    geometry = getattr(room, "geometry", None)
    source = getattr(geometry, "source", None)
    if source is not None:
        return PetPreviewPosition(
            x_from_west_m=float(getattr(source, "x_m", 0.0) or 0.0),
            y_from_south_m=float(getattr(source, "y_m", 0.0) or 0.0),
            height_above_ffl_m=float(getattr(source, "z_m", 1.0) or 1.0),
        )

    width_m = float(getattr(geometry, "width_m", 4.0) or 4.0) if geometry is not None else 4.0
    length_m = float(getattr(geometry, "length_m", 6.0) or 6.0) if geometry is not None else 6.0
    return PetPreviewPosition(width_m / 2.0, length_m / 2.0, 1.0)


def sync_pet_working_position_from_geometry(room: Any) -> bool:
    """Synchronise PET working-state position from canonical RoomGeometry.

    Geometry is the source of truth for patient/source position in the unified
    PET workflow. Preserve the last validated PET source inputs while replacing
    only the persisted position used by canonical PET calculation dispatch.
    """
    if str(getattr(room, "modality", "") or "").strip().upper() != "PET":
        return False
    try:
        state = get_room_pet_working_state(room)
        if state is None:
            return False
        position = _geometry_position(room).validate_for_room(room.geometry)
        set_room_pet_working_state(
            room,
            PetWorkingProjectState(source=state.source, position=position),
        )
    except Exception:
        return False
    return True


def initialise_active_modality_working_state(room: Any) -> None:
    """Keep only the active PET/SPECT envelope and create a valid default if needed.

    This is intended for an explicit room-modality transition.  It is not run as
    a project-load migration, so opening an old/incomplete project remains
    fail-closed rather than silently inventing source inputs.
    """
    modality = str(getattr(room, "modality", "") or "").strip().upper()
    state = dict(getattr(room, "modality_state", {}) or {})

    if modality != "PET":
        state.pop(PET_WORKING_PROJECT_STATE_KEY, None)
    if modality != "SPECT":
        state.pop(SPECT_WORKING_PROJECT_STATE_KEY, None)
    room.modality_state = state

    if modality == "PET" and PET_WORKING_PROJECT_STATE_KEY not in state:
        source = PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            residual_activity_factor=1.0,
            exposure_phases=(
                PetExposurePhase(
                    name="Imaging",
                    start_time_h=0.0,
                    duration_h=1.0,
                    activity_retention_factor=1.0,
                ),
            ),
        )
        set_room_pet_working_state(
            room,
            PetWorkingProjectState(source=source, position=_geometry_position(room)),
        )
    elif modality == "SPECT" and SPECT_WORKING_PROJECT_STATE_KEY not in state:
        source = SpectSourceDomain(
            radionuclide="Tc99m",
            administered_activity_mbq=600.0,
            patients_per_week=20.0,
            imaging_duration_h=0.5,
        )
        set_room_spect_working_state(room, new_spect_working_project_state(source))
