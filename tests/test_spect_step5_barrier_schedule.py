"""Tests for the headless SPECT Step 5 multi-barrier schedule boundary."""
from pathlib import Path

import pytest

from engine.spect_barrier_schedule import (
    SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION,
    SPECT_BARRIER_SCHEDULE_STATUS,
    SpectBarrierScheduleError,
    SpectBarrierScheduleRequest,
    calculate_spect_tc99m_barrier_schedule,
)
from engine.spect_practical_transmission import load_spect_tc99m_practical_dataset
from modalities.spect import SpectSourceDomain


DATASET = Path("data/spect/spect_tc99m_practical_transmission_development.json")


def _source() -> SpectSourceDomain:
    return SpectSourceDomain(
        radionuclide="Tc99m",
        administered_activity_mbq=600.0,
        patients_per_week=20.0,
        imaging_duration_h=0.5,
    )


def _request(barrier_id: str, barrier_name: str, **overrides) -> SpectBarrierScheduleRequest:
    values = {
        "barrier_id": barrier_id,
        "barrier_name": barrier_name,
        "material_key": "lead",
        "distance_m": 2.0,
        "occupancy_factor": 0.5,
        "design_goal_uSv_per_week": 1.0,
    }
    values.update(overrides)
    return SpectBarrierScheduleRequest(**values)


def test_step5_builds_multi_barrier_schedule_in_caller_order():
    requests = (
        _request("B-west", "West wall", provided_thickness_mm=1.1),
        _request(
            "B-east",
            "East wall",
            material_key="concrete_2300kg_m3",
            distance_m=3.0,
            occupancy_factor=0.25,
        ),
    )

    result = calculate_spect_tc99m_barrier_schedule(_source(), requests)

    assert result.contract_version == SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION
    assert result.status == SPECT_BARRIER_SCHEDULE_STATUS
    assert result.production_eligible is False
    assert result.ordering_basis == "caller_request_order"
    assert result.source_physics.radionuclide == "Tc99m"
    assert [row.schedule_index for row in result.rows] == [0, 1]
    assert [row.barrier_id for row in result.rows] == ["B-west", "B-east"]
    assert [row.barrier_name for row in result.rows] == ["West wall", "East wall"]
    assert result.rows[0].material_key == "lead"
    assert result.rows[1].material_key == "concrete_2300kg_m3"
    assert "10.1002/acm2.70084" in result.rows[0].practical_provenance


def test_step5_is_deterministic_and_reuses_one_validated_dataset_contract():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    requests = (
        _request("B1", "Barrier 1"),
        _request("B2", "Barrier 2", distance_m=2.5),
    )

    first = calculate_spect_tc99m_barrier_schedule(_source(), requests, dataset=dataset)
    second = calculate_spect_tc99m_barrier_schedule(_source(), requests, dataset=dataset)

    assert first == second
    assert {row.practical_record_id for row in first.rows} == {"oumano-2025-tc99m-lead"}


def test_step5_summary_counts_pass_fail_and_not_assessed_rows():
    result = calculate_spect_tc99m_barrier_schedule(
        _source(),
        (
            _request("pass", "Passing barrier", provided_thickness_mm=1.1),
            _request("fail", "Failing barrier", provided_thickness_mm=0.0),
            _request("na", "Unspecified barrier"),
        ),
    )

    assert [row.compliance_status for row in result.rows] == [
        "PASS",
        "FAIL",
        "NOT_ASSESSED",
    ]
    assert result.pass_count == 1
    assert result.fail_count == 1
    assert result.not_assessed_count == 1


def test_step5_propagates_schedule_level_room_scatter_and_extrapolation_flags():
    result = calculate_spect_tc99m_barrier_schedule(
        _source(),
        (
            _request("caution", "Caution barrier", design_goal_uSv_per_week=0.1),
            _request("extrap", "Extrapolated barrier", design_goal_uSv_per_week=0.005),
        ),
    )

    assert result.requires_room_scatter_review is True
    assert result.contains_source_model_extrapolation is True
    assert result.rows[0].required_room_scatter_caution is True
    assert result.rows[1].required_source_model_extrapolation is True


def test_step5_supports_source_only_empty_schedule_without_promoting_production():
    result = calculate_spect_tc99m_barrier_schedule(_source())

    assert result.rows == ()
    assert result.pass_count == 0
    assert result.fail_count == 0
    assert result.not_assessed_count == 0
    assert result.requires_room_scatter_review is False
    assert result.contains_source_model_extrapolation is False
    assert result.production_eligible is False


def test_step5_rejects_duplicate_barrier_ids_case_insensitively():
    with pytest.raises(SpectBarrierScheduleError, match="Duplicate barrier_id"):
        calculate_spect_tc99m_barrier_schedule(
            _source(),
            (
                _request("Wall-A", "Wall A"),
                _request("wall-a", "Duplicate wall"),
            ),
        )


def test_step5_rejects_blank_identity_and_invalid_step4_values():
    with pytest.raises(SpectBarrierScheduleError, match="barrier_id must not be blank"):
        _request(" ", "Wall")
    with pytest.raises(SpectBarrierScheduleError, match="barrier_name must not be blank"):
        _request("B1", " ")
    with pytest.raises(SpectBarrierScheduleError, match="distance_m must be greater"):
        _request("B1", "Wall", distance_m=0.0)
    with pytest.raises(SpectBarrierScheduleError, match="occupancy_factor must be between"):
        _request("B1", "Wall", occupancy_factor=1.1)


def test_step5_rejects_raw_source_raw_members_and_unsupported_material_with_context():
    with pytest.raises(SpectBarrierScheduleError, match="validated SpectSourceDomain"):
        calculate_spect_tc99m_barrier_schedule({"radionuclide": "Tc99m"})  # type: ignore[arg-type]

    with pytest.raises(SpectBarrierScheduleError, match=r"barrier_requests\[0\]"):
        calculate_spect_tc99m_barrier_schedule(
            _source(), ({"barrier_id": "B1"},)  # type: ignore[arg-type]
        )

    with pytest.raises(SpectBarrierScheduleError, match=r"barrier_requests\[0\] \(B1\).*Unsupported"):
        calculate_spect_tc99m_barrier_schedule(
            _source(), (_request("B1", "Wall", material_key="unobtainium"),)
        )


def test_step5_remains_outside_reports_serialization_services_and_production_dispatch():
    # Step 6 deliberately introduces one read-only presentation consumer under
    # tabs/spect_preview_panel.py. Step 5 must still remain absent from all
    # production calculation, report, serialization and service paths.
    forbidden = (
        "spect_barrier_schedule",
        "calculate_spect_tc99m_barrier_schedule",
        "SpectBarrierScheduleRequest",
        "SpectBarrierScheduleResult",
    )
    paths = [Path("app.py"), Path("engine/shielding_engine.py"), Path("modalities/spect.py")]
    for directory in ("reports", "ui", "serialization", "services"):
        paths.extend(Path(directory).glob("*.py"))
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production/application path {path}"
