from types import SimpleNamespace

from geometry.pet_preview_position import PetPreviewPosition
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import (
    PetWorkingProjectState,
    get_room_pet_working_state,
    set_room_pet_working_state,
)
from services.modality_working_state import sync_pet_working_position_from_geometry


def _source():
    return PetSourceDomain(
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


def test_pet_geometry_move_updates_persisted_dispatch_position_without_revalidating_source_form():
    room = SimpleNamespace(
        modality="PET",
        modality_state={},
        geometry=SimpleNamespace(
            width_m=4.0,
            length_m=6.0,
            height_m=3.6,
            source=SimpleNamespace(x_m=3.0, y_m=1.5, z_m=1.0),
        ),
    )
    original_source = _source()
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(
            source=original_source,
            position=PetPreviewPosition(2.0, 3.0, 1.0),
        ),
    )

    assert sync_pet_working_position_from_geometry(room) is True

    state = get_room_pet_working_state(room)
    assert state is not None
    assert state.source == original_source
    assert state.position == PetPreviewPosition(3.0, 1.5, 1.0)


def test_pet_geometry_position_sync_is_noop_for_non_pet_room():
    room = SimpleNamespace(modality="SPECT", modality_state={}, geometry=None)
    assert sync_pet_working_position_from_geometry(room) is False
