from copy import deepcopy
from types import SimpleNamespace

import pytest

from reports.results_payload_builder import build_results_payload
from services.xray_results_model import build_xray_results_model, xray_results_issueable
from tests.test_xray_xr15c_control_wall_report_kat import _kat_case


class _App:
    def __init__(self, project):
        self.project = project
        self.global_energy_var = SimpleNamespace(get=lambda: "xray_120kvp")
        self.solver_mode_var = SimpleNamespace(get=lambda: "auto")
    def get_sources_for_room(self, room_name):
        return [s for s in self.project.sources if s.room_name == room_name]
    def _row_confidence_from_live(self, name, row):
        return 1.0


def test_xr15d_internal_control_wall_is_explicitly_released_for_issueable_output():
    _, project, room = _kat_case()
    rows = build_xray_results_model(project, room)
    assert xray_results_issueable(rows) is True
    assert all(r["issued_output_enabled"] is True for r in rows)
    payload = build_results_payload(_App(project), report_status="Draft")
    q = payload["rooms"][0]["xray_report_qualification"]
    assert q["fig52_requalification_version"] == "xr15d-issueable-control-wall-v1"
    assert q["control_wall_qualified"] is True
    assert payload["export_eligibility"]["can_export_pdf"] is True


def test_xr15d_zero_distance_control_wall_fails_closed():
    _, project, room = _kat_case()
    room.geometry.control_wall.center_x_m = 1.0
    room.geometry.control_wall.center_y_m = 1.0
    room.barriers[0].distance_m = 0.0
    with pytest.raises(ValueError, match="positive source-to-wall distance"):
        build_xray_results_model(project, room)


def test_xr15d_geometry_barrier_distance_mismatch_fails_closed():
    _, project, room = _kat_case()
    room.barriers[0].distance_m = 3.0
    with pytest.raises(ValueError, match="distance does not match persisted geometry"):
        build_xray_results_model(project, room)


def test_xr15d_geometry_barrier_shielding_input_mismatch_fails_closed():
    _, project, room = _kat_case()
    room.barriers[0].thickness_mm = 0.5
    with pytest.raises(ValueError, match="thickness does not match persisted geometry"):
        build_xray_results_model(project, room)
