from models.shielding_models import Room, Source
from services.barriers_modality_context import barriers_modality_context


def test_barriers_context_uses_spect_energy_and_solver_not_ct_ksec():
    room = Room(
        name="SPECT Room 1",
        modality="SPECT",
        sources=[Source(name="SPECT Patient Source", source_type="spect_patient")],
    )
    context = barriers_modality_context(room, current_solver_mode="auto")
    assert context.energy_basis_display == "Tc-99m / radionuclide dependent"
    assert context.solver_display == "spect_tc99m_practical_archer"
    assert context.solver_editable is False
    assert "ksec" not in context.energy_basis_display.lower()


def test_barriers_context_uses_pet_energy_and_solver_not_ct_ksec():
    room = Room(
        name="PET Room 1",
        modality="PET",
        sources=[Source(name="PET Patient Source", source_type="pet_patient")],
    )
    context = barriers_modality_context(room, current_solver_mode="auto")
    assert context.energy_basis_display == "511 keV annihilation photons"
    assert context.solver_display == "pet_replay_verified_dispatch"
    assert context.solver_editable is False


def test_barriers_context_retains_ct_ksec_basis_and_editable_solver():
    room = Room(
        name="CT Room 1",
        modality="CT",
        sources=[Source(
            name="CT Source",
            source_type="ct_scatter",
            params={"ksec_energy_kvp": 120, "scanner_kvp": 120},
        )],
    )
    context = barriers_modality_context(room, current_solver_mode="auto")
    assert context.energy_basis_display == "CT ksec energy basis: 120 kVp"
    assert context.solver_display == "auto"
    assert context.solver_editable is True
