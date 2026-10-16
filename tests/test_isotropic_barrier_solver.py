from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from engine.barrier_input_contract import BarrierSourceInput
from engine.isotropic_barrier_solver import (
    ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
    ISOTROPIC_NON_BEAM_SOLVER_MODE,
    IsotropicBarrierDesign,
    IsotropicBarrierGeometry,
    IsotropicBarrierSolverError,
    IsotropicBarrierSolverInput,
    TvlAttenuationInput,
    solve_isotropic_non_beam_barrier,
)


def _source(**overrides) -> BarrierSourceInput:
    values = dict(
        source_name="PET uptake patient",
        source_type="pet_patient",
        radiation_type="f18_511kev",
        tvl_key="f18_511kev",
        weekly_dose_uSv_at_1m=4000.0,
        contribution_group="pet_patient",
        solver_mode=ISOTROPIC_NON_BEAM_SOLVER_MODE,
        distance_exponent=2.0,
        use_factor=1.0,
    )
    values.update(overrides)
    return BarrierSourceInput(**values)


def _input(**overrides) -> IsotropicBarrierSolverInput:
    values = dict(
        source=_source(),
        geometry=IsotropicBarrierGeometry(distance_m=2.0),
        design=IsotropicBarrierDesign(
            design_goal_uSv_per_week=10.0,
            occupancy_factor=0.5,
        ),
        attenuation=TvlAttenuationInput(
            material_key="concrete",
            tvl_key="f18_511kev",
            tvl1_mm=176.0,
            tvle_mm=154.0,
        ),
    )
    values.update(overrides)
    return IsotropicBarrierSolverInput(**values)


def test_isotropic_solver_applies_distance_occupancy_and_tvl_interpolation():
    result = solve_isotropic_non_beam_barrier(_input())

    # 4000 uSv/week at 1 m -> 1000 at 2 m -> 500 after T=0.5.
    # B = 10 / 500 = 0.02, requiring log10(50) = 1.69897 TVLs.
    expected_tvl_count = 1.6989700043360187
    expected_thickness = 176.0 + (expected_tvl_count - 1.0) * 154.0

    assert result.contract_version == ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION
    assert result.solver_mode == ISOTROPIC_NON_BEAM_SOLVER_MODE
    assert result.unshielded_weekly_dose_uSv_at_barrier == pytest.approx(1000.0)
    assert result.occupied_unshielded_weekly_dose_uSv == pytest.approx(500.0)
    assert result.required_transmission == pytest.approx(0.02)
    assert result.required_tvl_count == pytest.approx(expected_tvl_count)
    assert result.required_thickness_mm == pytest.approx(expected_thickness)
    assert result.compliance_status == "NOT_ASSESSED"


def test_isotropic_solver_returns_zero_required_thickness_when_goal_is_already_met():
    result = solve_isotropic_non_beam_barrier(
        _input(
            source=_source(weekly_dose_uSv_at_1m=10.0),
            design=IsotropicBarrierDesign(10.0, 1.0),
        )
    )

    assert result.required_transmission == 1.0
    assert result.required_tvl_count == 0.0
    assert result.required_thickness_mm == 0.0


def test_isotropic_solver_assesses_provided_thickness_with_same_tvl_contract():
    base = _input(provided_thickness_mm=176.0)
    one_tvl = solve_isotropic_non_beam_barrier(base)
    assert one_tvl.provided_transmission == pytest.approx(0.1)
    assert one_tvl.transmitted_weekly_dose_uSv == pytest.approx(50.0)
    assert one_tvl.compliance_status == "FAIL"

    sufficient = solve_isotropic_non_beam_barrier(
        replace(base, provided_thickness_mm=base.attenuation.tvl1_mm + base.attenuation.tvle_mm)
    )
    assert sufficient.provided_transmission == pytest.approx(0.01)
    assert sufficient.transmitted_weekly_dose_uSv == pytest.approx(5.0)
    assert sufficient.compliance_status == "PASS"


def test_isotropic_solver_accepts_a_future_spect_patient_source_without_pet_dependency():
    spect_source = _source(
        source_name="SPECT patient",
        source_type="spect_patient",
        radiation_type="tc99m_140kev",
        tvl_key="tc99m_140kev",
        contribution_group="spect_patient",
        weekly_dose_uSv_at_1m=200.0,
    )
    solver_input = _input(
        source=spect_source,
        attenuation=TvlAttenuationInput(
            material_key="concrete",
            tvl_key="tc99m_140kev",
            tvl1_mm=60.0,
            tvle_mm=60.0,
        ),
    )

    result = solve_isotropic_non_beam_barrier(solver_input)

    assert result.source_type == "spect_patient"
    assert result.radiation_type == "tc99m_140kev"
    assert result.tvl_key == "tc99m_140kev"


def test_isotropic_solver_rejects_wrong_mode_or_mismatched_tvl_data():
    with pytest.raises(IsotropicBarrierSolverError, match="source.solver_mode"):
        _input(source=_source(solver_mode="ncrp_ct_secondary"))

    with pytest.raises(IsotropicBarrierSolverError, match="attenuation.tvl_key must match"):
        _input(
            attenuation=TvlAttenuationInput(
                material_key="lead",
                tvl_key="wrong_key",
                tvl1_mm=16.0,
                tvle_mm=16.0,
            )
        )


def test_isotropic_solver_contract_rejects_invalid_geometry_design_and_material_values():
    with pytest.raises(IsotropicBarrierSolverError, match="distance_m must be greater than zero"):
        IsotropicBarrierGeometry(0.0)
    with pytest.raises(IsotropicBarrierSolverError, match="design_goal_uSv_per_week must be greater"):
        IsotropicBarrierDesign(0.0, 1.0)
    with pytest.raises(IsotropicBarrierSolverError, match="occupancy_factor must be between"):
        IsotropicBarrierDesign(10.0, 1.1)
    with pytest.raises(IsotropicBarrierSolverError, match="tvl1_mm must be greater than zero"):
        TvlAttenuationInput("lead", "f18_511kev", 0.0, 16.0)
    with pytest.raises(IsotropicBarrierSolverError, match="provided_thickness_mm must be greater"):
        _input(provided_thickness_mm=-0.1)


def test_isotropic_solver_remains_separate_from_ct_xray_ui_reports_and_production_dispatch():
    forbidden = "solve_isotropic_non_beam_barrier"

    assert forbidden not in Path("engine/shielding_engine.py").read_text(encoding="utf-8")
    assert forbidden not in Path("modalities/ct.py").read_text(encoding="utf-8")
    assert forbidden not in Path("modalities/xray.py").read_text(encoding="utf-8")
    assert forbidden not in Path("app.py").read_text(encoding="utf-8")
    assert forbidden not in "\n".join(
        path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")
    )
