import pytest

from engine.shielding_engine import (
    compute_xray_ncrp_simplified_source_summary,
    get_xray_primary_workload_and_use_factor,
)
from models.shielding_models import Barrier, Source


def _source(exams=125, room_type="general_radiography"):
    return Source(
        name="General radiography",
        source_type="xray_primary",
        radiation_type="120 kVp",
        params={
            "xray_method": "ncrp_simplified",
            "exam_room_type": room_type,
            "exams_per_week": exams,
            "tube_potential_kvp": 120,
        },
    )


def _barrier(role):
    b = Barrier(name=role, distance_m=3.0)
    b.barrier_role = role
    return b


def test_general_radiography_uses_barrier_specific_ncrp147_workloads():
    s = compute_xray_ncrp_simplified_source_summary(_source().params)
    assert s["primary_bucky_workload_uSv_per_week_at_1m"] == pytest.approx(125 * 2.3 * 1000.0)
    assert s["primary_floor_workload_uSv_per_week_at_1m"] == pytest.approx(125 * 5.2 * 1000.0)
    assert s["secondary_workload_uSv_per_week_at_1m"] == pytest.approx(125 * 0.034 * 1000.0)


def test_primary_floor_uses_ncrp147_floor_workload_and_use_factor():
    ctx = get_xray_primary_workload_and_use_factor(_source(), _barrier("primary_floor"))
    assert ctx["workload_uSv_per_week_at_1m"] == pytest.approx(650000.0)
    assert ctx["use_factor"] == pytest.approx(0.89)
    assert ctx["is_primary"] is True


def test_primary_bucky_uses_ncrp147_bucky_workload_and_use_factor():
    ctx = get_xray_primary_workload_and_use_factor(_source(), _barrier("primary_bucky_wall"))
    assert ctx["workload_uSv_per_week_at_1m"] == pytest.approx(287500.0)
    assert ctx["use_factor"] == pytest.approx(1.0)


def test_secondary_reference_kerma_matches_0_47_mgy_per_week_at_3m_example_geometry():
    ctx = get_xray_primary_workload_and_use_factor(_source(), _barrier("secondary_wall"))
    at_3m_uSv_per_week = ctx["workload_uSv_per_week_at_1m"] / 9.0
    assert at_3m_uSv_per_week == pytest.approx(472.2222222)


@pytest.mark.parametrize("room_type", ["chest_room", "trauma_emergency"])
def test_unqualified_room_types_fail_closed(room_type):
    with pytest.raises(ValueError, match="not yet qualified"):
        compute_xray_ncrp_simplified_source_summary(_source(room_type=room_type).params)
