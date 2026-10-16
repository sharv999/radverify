from __future__ import annotations

from math import exp, log
from pathlib import Path

import pytest

from engine.isotropic_barrier_solver import TvlAttenuationInput
from modalities.spect import (
    SPECT_PHYSICS_CONTRACT_VERSION,
    SPECT_RADIONUCLIDE_DATASET_METADATA,
    SPECT_SOURCE_TYPE,
    SpectContractError,
    SpectSourceDomain,
    calculate_spect_weekly_dose_at_1m,
    spect_source_domain_from_params,
)
from services.spect_calculation_service import (
    SpectBarrierCalculationRequest,
    run_spect_calculation_service,
)
from serialization.spect_headless_replay import replay_spect_project_snapshot


def _source(**overrides) -> SpectSourceDomain:
    values = dict(
        radionuclide="Tc99m",
        administered_activity_mbq=740.0,
        patients_per_week=20.0,
        imaging_duration_h=0.5,
    )
    values.update(overrides)
    return SpectSourceDomain(**values)


def test_spect_step1_source_contract_is_single_imaging_interval_with_no_uptake_phase():
    source = spect_source_domain_from_params(
        {
            "radionuclide": "Tc99m",
            "administered_activity_mbq": 740,
            "patients_per_week": 20,
            "imaging_duration_h": 0.5,
        }
    )

    assert source == _source()
    assert not hasattr(source, "uptake_time_h")
    assert not hasattr(source, "exposure_phases")
    assert not hasattr(source, "voiding_factor")
    assert not hasattr(source, "activity_retention_factor")


def test_spect_step1_tc99m_known_answer_decay_integrates_imaging_interval_only():
    source = _source()
    result = calculate_spect_weekly_dose_at_1m(source)

    half_life_h = 6.0067
    decay_constant = log(2.0) / half_life_h
    expected_integrated_h = (1.0 - exp(-decay_constant * 0.5)) / decay_constant
    expected_weekly_dose = 0.0206 * 740.0 * 20.0 * expected_integrated_h

    assert result.contract_version == SPECT_PHYSICS_CONTRACT_VERSION
    assert result.radionuclide == "Tc99m"
    assert result.radiation_type == "tc99m_140kev"
    assert result.tvl_key == "tc99m_140kev"
    assert result.decay_integrated_hours == pytest.approx(0.4858490051751217)
    assert result.decay_integrated_hours == pytest.approx(expected_integrated_h)
    assert result.weekly_dose_uSv_at_1m == pytest.approx(148.1256446977911)
    assert result.weekly_dose_uSv_at_1m == pytest.approx(expected_weekly_dose)


def test_spect_step1_headless_service_uses_generic_isotropic_solver_and_replays():
    attenuation = TvlAttenuationInput(
        material_key="synthetic_test_material",
        tvl_key="tc99m_140kev",
        tvl1_mm=60.0,
        tvle_mm=60.0,
        attenuation_record_id="spect-step1-synthetic-kat",
        attenuation_provenance="Synthetic test-only TVL; not a clinical attenuation record.",
    )
    request = SpectBarrierCalculationRequest(
        attenuation=attenuation,
        distance_m=2.0,
        occupancy_factor=0.5,
        design_goal_uSv_per_week=10.0,
        provided_thickness_mm=60.0,
    )

    service = run_spect_calculation_service(_source(), (request,))
    solved = service.snapshot.barrier_results[0].result.solver_result

    assert service.source_type == SPECT_SOURCE_TYPE
    assert service.replay_verified is True
    assert solved.unshielded_weekly_dose_uSv_at_barrier == pytest.approx(
        148.1256446977911 / 4.0
    )
    assert solved.occupied_unshielded_weekly_dose_uSv == pytest.approx(
        148.1256446977911 / 8.0
    )
    assert solved.provided_transmission == pytest.approx(0.1)
    assert replay_spect_project_snapshot(service.payload).deterministic is True


def test_spect_step1_radionuclide_dataset_is_frozen_but_spect_remains_nonproduction():
    assert (
        SPECT_RADIONUCLIDE_DATASET_METADATA.dataset_id
        == "spect-radionuclide-physics-tc99m-source-model"
    )
    assert (
        SPECT_RADIONUCLIDE_DATASET_METADATA.approval_status
        == "physics_approved_frozen_nonproduction"
    )


def test_spect_step1_rejects_unsupported_or_invalid_source_values():
    with pytest.raises(SpectContractError, match="Unsupported SPECT radionuclide"):
        _source(radionuclide="I131")
    with pytest.raises(SpectContractError, match="administered_activity_mbq must be greater"):
        _source(administered_activity_mbq=0.0)
    with pytest.raises(SpectContractError, match="imaging_duration_h must be greater"):
        _source(imaging_duration_h=0.0)


def test_spect_step1_remains_outside_ui_reports_and_production_project_dispatch():
    forbidden = (
        "run_spect_calculation_service",
        "calculate_spect_weekly_dose_at_1m",
        "SpectSourceDomain",
    )
    paths = [Path("app.py"), Path("engine/shielding_engine.py")]
    paths.extend(Path("reports").glob("*.py"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production path {path}"
