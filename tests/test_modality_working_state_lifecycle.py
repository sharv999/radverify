from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from modalities.spect import SpectSourceDomain
from geometry.pet_preview_position import PetPreviewPosition
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_KEY,
    PetWorkingProjectState,
    get_room_pet_working_state,
    set_room_pet_working_state,
)
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_KEY,
    get_room_spect_working_state,
    new_spect_working_project_state,
    set_room_spect_working_state,
)
from services.modality_working_state import initialise_active_modality_working_state


def _room(modality="PET"):
    return Room(name=f"{modality} Room 1", modality=modality, barriers=default_barriers(), geometry=RoomGeometry())


def _pet_state():
    return PetWorkingProjectState(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            residual_activity_factor=1.0,
            exposure_phases=(PetExposurePhase("Imaging", 0.0, 1.0, 1.0),),
        ),
        position=PetPreviewPosition(2.0, 2.0, 1.0),
    )


def _spect_state():
    return new_spect_working_project_state(
        SpectSourceDomain(
            radionuclide="Tc99m",
            administered_activity_mbq=600.0,
            patients_per_week=20.0,
            imaging_duration_h=0.5,
        )
    )


def test_switch_to_pet_clears_stale_spect_state_and_creates_pet_defaults():
    room = _room("SPECT")
    set_room_spect_working_state(room, _spect_state())
    room.modality = "PET"

    initialise_active_modality_working_state(room)

    assert PET_WORKING_PROJECT_STATE_KEY in room.modality_state
    assert SPECT_WORKING_PROJECT_STATE_KEY not in room.modality_state
    assert get_room_pet_working_state(room) is not None
    assert get_room_spect_working_state(room) is None


def test_switch_to_spect_clears_stale_pet_state_and_creates_spect_defaults():
    room = _room("PET")
    set_room_pet_working_state(room, _pet_state())
    room.modality = "SPECT"

    initialise_active_modality_working_state(room)

    assert SPECT_WORKING_PROJECT_STATE_KEY in room.modality_state
    assert PET_WORKING_PROJECT_STATE_KEY not in room.modality_state
    assert get_room_spect_working_state(room) is not None
    assert get_room_pet_working_state(room) is None



def test_app_results_dispatch_ignores_stale_spect_envelope_in_pet_room():
    from app import ShieldingDesktopApp

    room = _room("PET")
    set_room_pet_working_state(room, _pet_state())
    spect_room = _room("SPECT")
    set_room_spect_working_state(spect_room, _spect_state())
    room.modality_state[SPECT_WORKING_PROJECT_STATE_KEY] = spect_room.modality_state[SPECT_WORKING_PROJECT_STATE_KEY]

    class FakeApp:
        project = Project(project_name="mixed-state", rooms=[room])
        def get_room_barrier_results(self, _room):
            raise AssertionError("PET must not fall back through generic calculation")

    rows = ShieldingDesktopApp.get_room_results_model(FakeApp(), room)
    assert rows
    assert {row["results_source"] for row in rows} == {"persisted_pet_single_source"}


def test_app_results_dispatch_ignores_stale_pet_envelope_in_spect_room():
    from app import ShieldingDesktopApp

    room = _room("SPECT")
    set_room_spect_working_state(room, _spect_state())
    pet_room = _room("PET")
    set_room_pet_working_state(pet_room, _pet_state())
    room.modality_state[PET_WORKING_PROJECT_STATE_KEY] = pet_room.modality_state[PET_WORKING_PROJECT_STATE_KEY]

    class FakeApp:
        project = Project(project_name="mixed-state", rooms=[room])
        def get_room_barrier_results(self, _room):
            raise AssertionError("SPECT must not fall back through generic calculation")

    rows = ShieldingDesktopApp.get_room_results_model(FakeApp(), room)
    assert rows
    assert {row["results_source"] for row in rows} == {"spect_step26_production_dispatch"}
