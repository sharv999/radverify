"""Known-answer tests for the isolated PET shielding calculation path.

The numerical expectations in this module are fixed reference values.  They
exercise the PET source workload, approved 511 keV attenuation lookup, and the
generic isotropic/non-beam solver without making PET available to the UI,
production calculation dispatch, or reports.
"""

from pathlib import Path

import pytest

from modalities.pet import (
    PET_ATTENUATION_RADIATION_TYPE,
    PET_ATTENUATION_TVL_KEY,
    PET_CALCULATION_BLOCK_REASON,
    PetExposurePhase,
    PetSourceDomain,
    calculate_pet_weekly_dose_at_1m,
    calculate_pet_decay_factor_at_time,
    solve_pet_isotropic_barrier,
)


def test_kat_pet_f18_lead_workload_distance_occupancy_and_thickness():
    """F-18 patient workload with a lead barrier has fixed reference outputs.

    Inputs:
        200 MBq F-18, 20 patients/week
        one 1 h phase beginning at administration
        barrier distance 2 m, occupancy 0.5
        design goal 10 uSv/week, 32 mm lead provided

    Approved lead data:
        TVL1 = 16.0 mm, TVLe = 14.8 mm
    """

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=200.0,
            patients_per_week=20.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0),),
        )
    )

    assert physics.weekly_dose_uSv_at_1m == pytest.approx(
        306.31702047624486, rel=1e-12
    )
    assert physics.phase_results[0].decay_integrated_hours == pytest.approx(
        0.8323832078158827, rel=1e-12
    )

    result = solve_pet_isotropic_barrier(
        physics,
        material_key="lead",
        distance_m=2.0,
        occupancy_factor=0.5,
        design_goal_uSv_per_week=10.0,
        provided_thickness_mm=32.0,
    )
    solved = result.solver_result

    assert solved.radiation_type == PET_ATTENUATION_RADIATION_TYPE
    assert solved.tvl_key == PET_ATTENUATION_TVL_KEY
    assert solved.material_key == "lead"
    assert solved.unshielded_weekly_dose_uSv_at_barrier == pytest.approx(
        76.57925511906122, rel=1e-12
    )
    assert solved.occupied_unshielded_weekly_dose_uSv == pytest.approx(
        38.28962755953061, rel=1e-12
    )
    assert solved.required_transmission == pytest.approx(
        0.2611673353169223, rel=1e-12
    )
    assert solved.required_tvl_count == pytest.approx(
        0.5830811420168609, rel=1e-12
    )
    assert solved.required_thickness_mm == pytest.approx(
        9.329298272269774, rel=1e-12
    )
    assert solved.provided_transmission == pytest.approx(
        0.008296958520834915, rel=1e-12
    )
    assert solved.transmitted_weekly_dose_uSv == pytest.approx(
        0.3176874516396429, rel=1e-12
    )
    assert solved.compliance_status == "PASS"

    assert solved.attenuation_record_id == "tg108-511kev-lead-provisional"
    assert "AAPM Task Group 108" in solved.attenuation_provenance
    assert result.dataset_id == "pet-511kev-aapm-tg108-review-fixture"
    assert result.dataset_revision == "2026-07-19-review-1"
    assert result.approved_by == "Steve H"
    assert result.approved_date == "2026-07-19"





def test_kat_pet_f18_decay_factor_at_one_hour_matches_exact_exponential():
    """Read-only imaging-start decay factor is exact physical decay from administration."""

    factor = calculate_pet_decay_factor_at_time(1.8295, 1.0)
    assert factor == pytest.approx(0.6846329195720021, rel=1e-12)

def test_kat_pet_f18_tg108_post_uptake_imaging_decay_and_voiding():
    """TG-108 imaging phase uses absolute start-time decay plus 0.85 post-void retention."""

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=555.0,
            patients_per_week=40.0,
            exposure_phases=(
                PetExposurePhase(
                    "Imaging",
                    start_time_h=1.0,
                    duration_h=0.5,
                    activity_retention_factor=0.85,
                ),
            ),
        )
    )

    phase = physics.phase_results[0]
    assert phase.decay_integrated_hours == pytest.approx(0.3118468867927555, rel=1e-12)
    assert phase.activity_retention_factor == pytest.approx(0.85)
    assert physics.weekly_dose_uSv_at_1m == pytest.approx(541.3786693476952, rel=1e-12)
    assert physics.weekly_dose_uSv_at_1m / 9.0 == pytest.approx(60.153185483077245, rel=1e-12)



def test_kat_pet_f18_tg108_example5_uptake_room_floor_dose():
    """TG-108 Example 5 uptake-room floor dose is reproduced with exact decay.

    Reference inputs: 555 MBq F-18, 40 patients/week, 1 h uptake, 3.6 m
    source-to-target distance. TG-108 uses rounded RtU=0.83 and reports
    approximately 131 uSv/week. Radshield integrates the exponential exactly.
    """

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=555.0,
            patients_per_week=40.0,
            exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0),),
        )
    )
    phase = physics.phase_results[0]
    assert phase.decay_integrated_hours == pytest.approx(0.8323832078158827, rel=1e-12)
    assert phase.activity_retention_factor == pytest.approx(1.0)
    assert physics.weekly_dose_uSv_at_1m / (3.6 ** 2) == pytest.approx(
        131.17742775024374, rel=1e-12
    )


def test_kat_pet_ga68_concrete_workload_distance_occupancy_and_thickness():
    """Ga-68 delayed phase with concrete has fixed reference outputs.

    Inputs:
        150 MBq Ga-68, 12 patients/week, residual factor 0.9
        one 0.5 h phase beginning 0.5 h after administration
        barrier distance 3 m, occupancy 0.25
        design goal 1 uSv/week, 200 mm concrete provided

    Approved concrete data:
        TVL1 = 195.0 mm, TVLe = 153.0 mm
    """

    physics = calculate_pet_weekly_dose_at_1m(
        PetSourceDomain(
            radionuclide="Ga68",
            injected_activity_mbq=150.0,
            patients_per_week=12.0,
            residual_activity_factor=0.9,
            exposure_phases=(PetExposurePhase("Imaging", 0.5, 0.5),),
        )
    )

    assert physics.weekly_dose_uSv_at_1m == pytest.approx(
        43.605882274306815, rel=1e-12
    )
    assert physics.phase_results[0].decay_integrated_hours == pytest.approx(
        0.3166730738874859, rel=1e-12
    )

    result = solve_pet_isotropic_barrier(
        physics,
        material_key="concrete_2350kg_m3",
        distance_m=3.0,
        occupancy_factor=0.25,
        design_goal_uSv_per_week=1.0,
        provided_thickness_mm=200.0,
    )
    solved = result.solver_result

    assert solved.radiation_type == PET_ATTENUATION_RADIATION_TYPE
    assert solved.tvl_key == PET_ATTENUATION_TVL_KEY
    assert solved.material_key == "concrete_2350kg_m3"
    assert solved.unshielded_weekly_dose_uSv_at_barrier == pytest.approx(
        4.845098030478535, rel=1e-12
    )
    assert solved.occupied_unshielded_weekly_dose_uSv == pytest.approx(
        1.2112745076196338, rel=1e-12
    )
    assert solved.required_transmission == pytest.approx(
        0.8255766910881125, rel=1e-12
    )
    assert solved.required_tvl_count == pytest.approx(
        0.08324257719301868, rel=1e-12
    )
    assert solved.required_thickness_mm == pytest.approx(
        16.232302552638643, rel=1e-12
    )
    assert solved.provided_transmission == pytest.approx(
        0.09275135468342334, rel=1e-12
    )
    assert solved.transmitted_weekly_dose_uSv == pytest.approx(
        0.11234735147521763, rel=1e-12
    )
    assert solved.compliance_status == "PASS"

    assert solved.attenuation_record_id == "tg108-511kev-concrete-2350-provisional"
    assert "concrete column (density 2.35 g/cm3)" in solved.attenuation_provenance
    assert result.dataset_id == "pet-511kev-aapm-tg108-review-fixture"
    assert result.approved_by == "Steve H"
    assert result.approved_date == "2026-07-19"


def test_pet_known_answer_path_remains_non_production_and_non_reportable():
    """Known-answer coverage must not make PET selectable or reportable."""

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

    app_text = Path("app.py").read_text(encoding="utf-8")
    report_text = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")
    )
    production_engine_text = Path("engine/shielding_engine.py").read_text(
        encoding="utf-8"
    )

    for boundary_name in (
        "solve_pet_isotropic_barrier",
        "load_pet_approved_attenuation_dataset",
        "PET_ATTENUATION_DATASET_PATH",
    ):
        assert boundary_name not in app_text
        assert boundary_name not in report_text
        assert boundary_name not in production_engine_text
