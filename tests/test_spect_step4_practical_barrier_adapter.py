from __future__ import annotations

from pathlib import Path

import pytest

from engine.spect_barrier_calculation import (
    SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION,
    SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS,
    SpectPracticalBarrierError,
    SpectPracticalBarrierRequest,
    calculate_spect_tc99m_practical_barrier,
)
from engine.spect_practical_transmission import (
    calculate_tc99m_required_thickness,
    calculate_tc99m_transmission,
    load_spect_tc99m_practical_dataset,
)
from modalities.spect import SpectSourceDomain


DATASET = Path("data/spect/spect_tc99m_practical_transmission_development.json")


def _source(**overrides) -> SpectSourceDomain:
    values = {
        "radionuclide": "Tc99m",
        "administered_activity_mbq": 600.0,
        "patients_per_week": 20.0,
        "imaging_duration_h": 0.5,
    }
    values.update(overrides)
    return SpectSourceDomain(**values)


def _request(**overrides) -> SpectPracticalBarrierRequest:
    values = {
        "material_key": "lead",
        "distance_m": 2.0,
        "occupancy_factor": 0.5,
        "design_goal_uSv_per_week": 1.0,
    }
    values.update(overrides)
    return SpectPracticalBarrierRequest(**values)


def test_spect_step4_combines_step1_source_with_step3_practical_model():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    result = calculate_spect_tc99m_practical_barrier(
        _source(), _request(), dataset=dataset
    )

    assert result.adapter_contract_version == SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION
    assert result.adapter_status == SPECT_PRACTICAL_BARRIER_ADAPTER_STATUS
    assert result.source_physics.radionuclide == "Tc99m"
    assert result.source_physics.weekly_dose_uSv_at_1m == pytest.approx(120.10187407929008)
    assert result.unshielded_weekly_dose_uSv_at_barrier == pytest.approx(30.02546851982252)
    assert result.occupied_unshielded_weekly_dose_uSv == pytest.approx(15.01273425991126)
    assert result.required_transmission == pytest.approx(0.0666101179630093)

    expected = calculate_tc99m_required_thickness(
        dataset, material_key="lead", target_transmission=result.required_transmission
    )
    assert result.required_thickness_mm == pytest.approx(expected.required_thickness_mm)
    assert result.practical_record_id == expected.record_id
    assert result.practical_provenance == expected.provenance


def test_spect_step4_no_shielding_is_required_when_design_goal_exceeds_occupied_dose():
    result = calculate_spect_tc99m_practical_barrier(
        _source(), _request(design_goal_uSv_per_week=100.0)
    )

    assert result.required_transmission == 1.0
    assert result.required_thickness_mm == pytest.approx(0.0)
    assert result.required_room_scatter_caution is False
    assert result.required_source_model_extrapolation is False


def test_spect_step4_provided_thickness_is_evaluated_by_step3_forward_model():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    provided = calculate_tc99m_transmission(
        dataset, material_key="lead", thickness_mm=1.1
    )
    result = calculate_spect_tc99m_practical_barrier(
        _source(), _request(provided_thickness_mm=1.1), dataset=dataset
    )

    assert result.provided_thickness_mm == pytest.approx(1.1)
    assert result.provided_transmission == pytest.approx(provided.transmission)
    assert result.transmitted_weekly_dose_uSv == pytest.approx(
        result.occupied_unshielded_weekly_dose_uSv * provided.transmission
    )
    assert result.compliance_status == "PASS"


def test_spect_step4_insufficient_provided_barrier_fails_and_zero_thickness_is_valid():
    result = calculate_spect_tc99m_practical_barrier(
        _source(), _request(provided_thickness_mm=0.0)
    )

    assert result.provided_transmission == pytest.approx(1.0)
    assert result.transmitted_weekly_dose_uSv == pytest.approx(
        result.occupied_unshielded_weekly_dose_uSv
    )
    assert result.compliance_status == "FAIL"


def test_spect_step4_without_provided_thickness_is_not_assessed():
    result = calculate_spect_tc99m_practical_barrier(_source(), _request())

    assert result.provided_thickness_mm is None
    assert result.provided_transmission is None
    assert result.transmitted_weekly_dose_uSv is None
    assert result.provided_room_scatter_caution is None
    assert result.provided_scope_note is None
    assert result.compliance_status == "NOT_ASSESSED"


def test_spect_step4_propagates_low_transmission_caution_and_extrapolation():
    caution = calculate_spect_tc99m_practical_barrier(
        _source(), _request(design_goal_uSv_per_week=0.1)
    )
    extrapolated = calculate_spect_tc99m_practical_barrier(
        _source(), _request(design_goal_uSv_per_week=0.005)
    )

    assert caution.required_transmission < 0.01
    assert caution.required_room_scatter_caution is True
    assert "room-scatter" in caution.required_scope_note
    assert extrapolated.required_transmission < 0.001
    assert extrapolated.required_room_scatter_caution is True
    assert extrapolated.required_source_model_extrapolation is True
    assert "extrapolation" in extrapolated.required_scope_note


def test_spect_step4_provided_low_transmission_caution_is_propagated():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    lead = dataset.records["lead"]
    from engine.spect_practical_transmission import archer_required_thickness
    cvl_mm = archer_required_thickness(lead, 0.01)

    result = calculate_spect_tc99m_practical_barrier(
        _source(), _request(provided_thickness_mm=cvl_mm), dataset=dataset
    )

    assert result.provided_transmission == pytest.approx(0.01, rel=0.02)
    assert result.provided_room_scatter_caution is True
    assert "room-scatter" in result.provided_scope_note


def test_spect_step4_rejects_invalid_request_and_unsupported_material():
    with pytest.raises(SpectPracticalBarrierError, match="distance_m must be greater"):
        _request(distance_m=0.0)
    with pytest.raises(SpectPracticalBarrierError, match="occupancy_factor must be between"):
        _request(occupancy_factor=1.1)
    with pytest.raises(SpectPracticalBarrierError, match="provided_thickness_mm must be greater"):
        _request(provided_thickness_mm=-1.0)

    with pytest.raises(SpectPracticalBarrierError, match="Unsupported"):
        calculate_spect_tc99m_practical_barrier(
            _source(), _request(material_key="unobtainium")
        )


def test_spect_step4_remains_headless_and_outside_application_report_dispatch():
    forbidden = (
        "spect_barrier_calculation",
        "calculate_spect_tc99m_practical_barrier",
        "SpectPracticalBarrierRequest",
        "SpectPracticalBarrierResult",
    )
    paths = [Path("app.py"), Path("engine/shielding_engine.py"), Path("modalities/spect.py")]
    for directory in ("reports", "tabs", "ui", "serialization", "services"):
        paths.extend(Path(directory).glob("*.py"))
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production/application path {path}"
