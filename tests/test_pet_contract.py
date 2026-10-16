from math import exp, log

import pytest

from modalities.pet import (
    PET_CALCULATION_BLOCK_REASON,
    PET_PHYSICS_CONTRACT_VERSION,
    PetContractError,
    PetExposurePhase,
    PetSourceDomain,
    calculate_pet_weekly_dose_at_1m,
    pet_source_domain_from_params,
)


def test_pet_source_domain_accepts_valid_f18_multiphase_input():
    source = pet_source_domain_from_params(
        {
            "radionuclide": "F18",
            "injected_activity_mbq": 250.0,
            "patients_per_week": 40,
            "residual_activity_factor": 0.9,
            "exposure_phases": [
                {"name": "Uptake", "start_time_h": 0.0, "duration_h": 1.0},
                {
                    "name": "Imaging",
                    "start_time_h": 1.0,
                    "duration_h": 0.5,
                    "activity_retention_factor": 0.75,
                },
            ],
        }
    )

    assert source.radionuclide == "F18"
    assert source.injected_activity_mbq == 250.0
    assert source.patients_per_week == 40.0
    assert source.residual_activity_factor == 0.9
    assert tuple(phase.name for phase in source.exposure_phases) == ("Uptake", "Imaging")


def test_pet_physics_contract_integrates_physical_decay_for_each_phase():
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=200.0,
        patients_per_week=25.0,
        residual_activity_factor=0.8,
        exposure_phases=(
            PetExposurePhase("Uptake", start_time_h=0.0, duration_h=1.0),
            PetExposurePhase("Imaging", start_time_h=1.0, duration_h=0.5, activity_retention_factor=0.5),
        ),
    )

    result = calculate_pet_weekly_dose_at_1m(source)

    decay_constant = log(2.0) / 1.8295
    uptake_integrated_h = (1.0 - exp(-decay_constant * 1.0)) / decay_constant
    imaging_integrated_h = (exp(-decay_constant * 1.0) - exp(-decay_constant * 1.5)) / decay_constant
    expected = 0.092 * 200.0 * 0.8 * 25.0 * (
        uptake_integrated_h + 0.5 * imaging_integrated_h
    )

    assert result.contract_version == PET_PHYSICS_CONTRACT_VERSION
    assert result.radionuclide == "F18"
    assert result.radiation_type == "annihilation_511kev"
    assert result.tvl_key == "pet_511kev"
    assert result.calculation_basis == "decay_integrated_point_source_at_1m"
    assert result.weekly_dose_uSv_at_1m == pytest.approx(expected)
    assert sum(item.weekly_dose_uSv_at_1m for item in result.phase_results) == pytest.approx(expected)



def test_pet_exposure_phase_contract_has_no_legacy_presence_field():
    phase = PetExposurePhase("Imaging", 1.0, 0.5, activity_retention_factor=0.85)
    assert not hasattr(phase, "presence_factor")
    assert phase.activity_retention_factor == pytest.approx(0.85)

def test_pet_physics_contract_scales_linearly_with_activity_patients_and_residual_factor():
    phase = (PetExposurePhase("Uptake", start_time_h=0.0, duration_h=1.0),)
    baseline = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain("Ga68", 100.0, 10.0, phase, residual_activity_factor=1.0)
    )
    scaled = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain("Ga68", 200.0, 20.0, phase, residual_activity_factor=0.5)
    )

    assert scaled.weekly_dose_uSv_at_1m == pytest.approx(2.0 * baseline.weekly_dose_uSv_at_1m)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"radionuclide": "Cu64"}, "Unsupported PET radionuclide"),
        ({"injected_activity_mbq": 0.0}, "injected_activity_mbq must be greater than zero"),
        ({"patients_per_week": -1.0}, "patients_per_week must be greater than zero"),
        ({"exposure_phases": ()}, "At least one PET exposure phase is required"),
        ({"residual_activity_factor": 1.1}, "residual_activity_factor must be greater than 0"),
    ],
)
def test_pet_source_domain_rejects_invalid_inputs(kwargs, message):
    values = {
        "radionuclide": "F18",
        "injected_activity_mbq": 200.0,
        "patients_per_week": 20.0,
        "exposure_phases": (PetExposurePhase("Uptake", 0.0, 1.0),),
        "residual_activity_factor": 1.0,
    }
    values.update(kwargs)

    with pytest.raises(PetContractError, match=message):
        PetSourceDomain(**values)


def test_pet_phase_rejects_blank_negative_or_out_of_range_values():
    with pytest.raises(PetContractError, match="name must not be blank"):
        PetExposurePhase("", 0.0, 1.0)
    with pytest.raises(PetContractError, match="start_time_h must be greater than or equal to zero"):
        PetExposurePhase("Uptake", -0.1, 1.0)
    with pytest.raises(PetContractError, match="duration_h must be greater than zero"):
        PetExposurePhase("Uptake", 0.0, -0.1)
    with pytest.raises(PetContractError, match="activity_retention_factor must be greater than 0"):
        PetExposurePhase("Uptake", 0.0, 1.0, 1.1)


def test_pet_contract_does_not_enable_ui_or_production_dispatch():
    from engine.shielding_engine import compute_source_weekly_dose_at_1m
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_dose_model_for_type,
        source_type_options,
    )
    from models.shielding_models import Source

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_dose_model_for_type("pet_patient") == "pet_patient_production_dispatch"
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    source = Source(
        name="PET Patient Source",
        source_type="pet_patient",
        radiation_type="f18_511kev",
        params={
            "radionuclide": "F18",
            "injected_activity_mbq": 200.0,
            "patients_per_week": 20.0,
            "exposure_phases": [{"name": "Uptake", "start_time_h": 0.0, "duration_h": 1.0}],
        },
    )
    with pytest.raises(ValueError, match=PET_CALCULATION_BLOCK_REASON):
        compute_source_weekly_dose_at_1m(source, {})


def test_pet_physics_result_maps_to_generic_barrier_source_input():
    from engine.barrier_input_contract import BARRIER_SOURCE_INPUT_CONTRACT_VERSION
    from modalities.pet import pet_physics_result_to_barrier_source_input

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=250.0,
            patients_per_week=30.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0),),
            residual_activity_factor=0.9,
        )
    )

    barrier_input = pet_physics_result_to_barrier_source_input(
        physics,
        source_name="PET uptake patient",
    )

    assert barrier_input.contract_version == BARRIER_SOURCE_INPUT_CONTRACT_VERSION
    assert barrier_input.source_name == "PET uptake patient"
    assert barrier_input.source_type == "pet_patient"
    assert barrier_input.radiation_type == "annihilation_511kev"
    assert barrier_input.tvl_key == "pet_511kev"
    assert barrier_input.weekly_dose_uSv_at_1m == pytest.approx(
        physics.weekly_dose_uSv_at_1m
    )
    assert barrier_input.contribution_group == "pet_patient"
    assert barrier_input.solver_mode == "isotropic_non_beam_tvl"
    assert barrier_input.distance_exponent == 2.0
    assert barrier_input.use_factor == 1.0


def test_pet_barrier_source_input_applies_inverse_square_distance_only_once():
    from modalities.pet import pet_physics_result_to_barrier_source_input

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="Ga68",
            injected_activity_mbq=150.0,
            patients_per_week=12.0,
            exposure_phases=(PetExposurePhase("Imaging", 0.5, 0.5),),
        )
    )
    barrier_input = pet_physics_result_to_barrier_source_input(physics)

    assert barrier_input.weekly_dose_uSv_at_distance(1.0) == pytest.approx(
        physics.weekly_dose_uSv_at_1m
    )
    assert barrier_input.weekly_dose_uSv_at_distance(2.0) == pytest.approx(
        physics.weekly_dose_uSv_at_1m / 4.0
    )
    assert barrier_input.weekly_dose_uSv_at_distance(3.0) == pytest.approx(
        physics.weekly_dose_uSv_at_1m / 9.0
    )


def test_generic_barrier_source_contract_rejects_invalid_values():
    from engine.barrier_input_contract import BarrierInputContractError, BarrierSourceInput

    valid = dict(
        source_name="PET Patient Source",
        source_type="pet_patient",
        radiation_type="f18_511kev",
        tvl_key="f18_511kev",
        weekly_dose_uSv_at_1m=100.0,
        contribution_group="pet_patient",
        solver_mode="isotropic_non_beam_tvl",
    )

    with pytest.raises(BarrierInputContractError, match="source_name must not be blank"):
        BarrierSourceInput(**{**valid, "source_name": ""})
    with pytest.raises(BarrierInputContractError, match="weekly_dose_uSv_at_1m must be greater"):
        BarrierSourceInput(**{**valid, "weekly_dose_uSv_at_1m": -1.0})
    with pytest.raises(BarrierInputContractError, match="distance_exponent must be greater"):
        BarrierSourceInput(**{**valid, "distance_exponent": 0.0})
    with pytest.raises(BarrierInputContractError, match="use_factor must be between"):
        BarrierSourceInput(**{**valid, "use_factor": 1.1})

    item = BarrierSourceInput(**valid)
    with pytest.raises(BarrierInputContractError, match="distance_m must be greater than zero"):
        item.weekly_dose_uSv_at_distance(0.0)


def test_pet_barrier_adapter_rejects_unknown_pet_physics_contract_version():
    from dataclasses import replace
    from modalities.pet import pet_physics_result_to_barrier_source_input

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=100.0,
            patients_per_week=1.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0),),
        )
    )

    with pytest.raises(PetContractError, match="Unsupported PET physics contract version"):
        pet_physics_result_to_barrier_source_input(replace(physics, contract_version=999))


def test_pet_barrier_boundary_remains_disconnected_from_production_and_reports():
    from pathlib import Path
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_dose_model_for_type,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_dose_model_for_type("pet_patient") == "pet_patient_production_dispatch"
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    engine_text = Path("engine/shielding_engine.py").read_text(encoding="utf-8")
    report_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("reports").glob("*.py")
    )
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "pet_physics_result_to_barrier_source_input" not in engine_text
    assert "pet_physics_result_to_barrier_source_input" not in report_text
    assert "pet_physics_result_to_barrier_source_input" not in app_text
    assert "BarrierSourceInput" not in report_text


def _approved_pet_physics(radionuclide="F18"):
    return calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide=radionuclide,
            injected_activity_mbq=200.0,
            patients_per_week=20.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0),),
        )
    )


def test_pet_boundary_loads_only_the_approved_511kev_dataset():
    from modalities.pet import (
        PET_ATTENUATION_DATASET_PATH,
        load_pet_approved_attenuation_dataset,
    )

    dataset = load_pet_approved_attenuation_dataset()

    assert PET_ATTENUATION_DATASET_PATH.name == "pet_511kev_attenuation_production_approved.json"
    assert dataset.metadata.production_approved is True
    assert dataset.metadata.approved_by == "Steve H"
    assert dataset.metadata.approved_date == "2026-07-19"
    assert len(dataset.library.records) == 3


def test_pet_boundary_resolves_approved_material_for_f18_and_ga68():
    from modalities.pet import resolve_pet_attenuation_record

    for radionuclide in ("F18", "Ga68"):
        dataset, record = resolve_pet_attenuation_record(
            _approved_pet_physics(radionuclide), material_key="lead"
        )
        assert dataset.metadata.production_approved is True
        assert record.tvl_key == "pet_511kev"
        assert record.radiation_type == "annihilation_511kev"
        assert radionuclide in record.radionuclides
        assert "AAPM" in record.provenance.summary


def test_pet_boundary_builds_generic_solver_input_from_approved_record():
    from modalities.pet import build_pet_isotropic_barrier_solver_input

    solver_input = build_pet_isotropic_barrier_solver_input(
        _approved_pet_physics(),
        material_key="concrete_2350kg_m3",
        distance_m=3.0,
        occupancy_factor=0.5,
        design_goal_uSv_per_week=10.0,
        provided_thickness_mm=200.0,
    )

    assert solver_input.source.tvl_key == "pet_511kev"
    assert solver_input.attenuation.tvl_key == solver_input.source.tvl_key
    assert solver_input.attenuation.material_key == "concrete_2350kg_m3"
    assert solver_input.attenuation.attenuation_record_id == "tg108-511kev-concrete-2350-provisional"
    assert "AAPM" in solver_input.attenuation.attenuation_provenance
    assert solver_input.geometry.distance_m == 3.0
    assert solver_input.design.occupancy_factor == 0.5
    assert solver_input.provided_thickness_mm == 200.0


def test_pet_boundary_solves_with_approved_dataset_and_preserves_audit_metadata():
    from modalities.pet import solve_pet_isotropic_barrier

    result = solve_pet_isotropic_barrier(
        _approved_pet_physics(),
        material_key="lead",
        distance_m=2.0,
        occupancy_factor=1.0,
        design_goal_uSv_per_week=10.0,
        provided_thickness_mm=32.0,
    )

    assert result.dataset_id == "pet-511kev-aapm-tg108-review-fixture"
    assert result.dataset_revision == "2026-07-19-review-1"
    assert result.approved_by == "Steve H"
    assert result.approved_date == "2026-07-19"
    assert result.solver_result.material_key == "lead"
    assert result.solver_result.attenuation_record_id == "tg108-511kev-lead-provisional"
    assert "AAPM" in result.solver_result.attenuation_provenance
    assert result.solver_result.required_thickness_mm >= 0.0


def test_pet_approved_dataset_path_remains_isolated_from_ui_dispatch_and_reports():
    from pathlib import Path

    pet_only_names = (
        "load_pet_approved_attenuation_dataset",
        "resolve_pet_attenuation_record",
        "build_pet_isotropic_barrier_solver_input",
        "solve_pet_isotropic_barrier",
        "pet_511kev_attenuation_production_approved.json",
    )
    outside_pet = [
        Path("app.py").read_text(encoding="utf-8"),
        Path("engine/shielding_engine.py").read_text(encoding="utf-8"),
        Path("modalities/ct.py").read_text(encoding="utf-8"),
        Path("modalities/xray.py").read_text(encoding="utf-8"),
        Path("modalities/spect.py").read_text(encoding="utf-8"),
        "\n".join(path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")),
    ]
    assert all(name not in text for name in pet_only_names for text in outside_pet)


def test_pet_single_source_contract_rejects_nonfinite_zero_and_ambiguous_phase_inputs():
    with pytest.raises(PetContractError, match="injected_activity_mbq must be finite"):
        PetSourceDomain("F18", float("nan"), 10.0, (PetExposurePhase("Uptake", 0.0, 1.0),))
    with pytest.raises(PetContractError, match="patients_per_week must be greater than zero"):
        PetSourceDomain("F18", 100.0, 0.0, (PetExposurePhase("Uptake", 0.0, 1.0),))
    with pytest.raises(PetContractError, match="duration_h must be greater than zero"):
        PetExposurePhase("Uptake", 0.0, 0.0)
    with pytest.raises(PetContractError, match="activity_retention_factor must be greater than 0"):
        PetExposurePhase("Uptake", 0.0, 1.0, 0.0)
    with pytest.raises(PetContractError, match="names must be unique"):
        PetSourceDomain(
            "F18", 100.0, 10.0,
            (PetExposurePhase("Room", 0.0, 0.5), PetExposurePhase("room", 0.5, 0.5)),
        )
    with pytest.raises(PetContractError, match="must not overlap"):
        PetSourceDomain(
            "F18", 100.0, 10.0,
            (PetExposurePhase("First", 0.0, 1.0), PetExposurePhase("Second", 0.5, 1.0)),
        )
    with pytest.raises(PetContractError, match="ordered by start time"):
        PetSourceDomain(
            "F18", 100.0, 10.0,
            (PetExposurePhase("Later", 1.0, 0.5), PetExposurePhase("Earlier", 0.0, 0.5)),
        )
