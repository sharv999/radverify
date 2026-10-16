import pytest

from reports.barrier_schedule import build_canonical_barrier_schedule_payload
from services.xray_results_model import build_xray_results_model, xray_results_issueable
from tests.test_xray_xr17b_control_wall_attenuation import _case


class _App:
    def __init__(self, project):
        self.project = project


def test_xr17c_intercepted_result_exposes_control_wall_provenance():
    project, room, _ = _case(True)
    row = next(r for r in build_xray_results_model(project, room) if r["barrier"] == "N wall")
    assert row["control_wall_attenuation_applied"] is True
    assert row["control_wall_material"] == "Pb"
    assert row["control_wall_thickness_mm"] == pytest.approx(0.88)
    assert 0.0 < row["control_wall_secondary_transmission"] < 1.0
    assert "Intervening Control Wall secondary attenuation credited" in row["control_wall_provenance"]
    assert "Bcw=" in row["control_wall_provenance"]


def test_xr17c_nonintercepted_result_has_no_control_wall_credit_provenance():
    project, room, _ = _case(False)
    control_barrier = next(b for b in room.barriers if b.barrier_role == "fig52_control_wall")
    control_barrier.distance_m = room.geometry.control_wall.source_distance_m(
        room.geometry.source.x_m, room.geometry.source.y_m
    )
    row = next(r for r in build_xray_results_model(project, room) if r["barrier"] == "N wall")
    assert row["control_wall_attenuation_applied"] is False
    assert row["control_wall_secondary_transmission"] == pytest.approx(1.0)
    assert row["control_wall_material"] == ""
    assert row["control_wall_thickness_mm"] is None
    assert row["control_wall_provenance"] == ""


def test_xr17d_canonical_report_schedule_preserves_credit_provenance_after_release():
    project, room, _ = _case(True)
    results = build_xray_results_model(project, room)
    rows = build_canonical_barrier_schedule_payload(_App(project), room, room_results=results)
    north = next(r for r in rows if r["name"] == "N wall")
    assert north["control_wall_attenuation_applied"] is True
    assert north["control_wall_material"] == "Pb"
    assert north["control_wall_thickness_mm"] == pytest.approx(0.88)
    assert north["control_wall_secondary_transmission"] == pytest.approx(
        next(r for r in results if r["barrier"] == "N wall")["control_wall_secondary_transmission"]
    )
    assert "Bcw=" in north["control_wall_provenance"]
    assert north["issued_output_enabled"] is True
    assert xray_results_issueable(results) is True
