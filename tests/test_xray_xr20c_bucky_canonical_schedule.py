from reports.barrier_schedule import build_canonical_barrier_schedule_payload
from services.xray_results_model import build_xray_results_model
from tests.test_xray_xr20a_bucky_subbarrier_canvas import _shielded_project


class _App:
    def __init__(self, project):
        self.project = project
    def _row_confidence_from_live(self, name, live):
        return 1.0


def test_xr20c_schedule_contains_distinct_bucky_shield_row_with_lower_dose():
    project, room = _shielded_project()
    live = build_xray_results_model(project, room)
    schedule = build_canonical_barrier_schedule_payload(_App(project), room, room_results=live)
    by_name = {row["name"]: row for row in schedule}
    assert "N wall" in by_name
    assert "N Bucky shield" in by_name
    wall = by_name["N wall"]
    shield = by_name["N Bucky shield"]
    assert shield["barrier_element_type"] == "bucky_shield"
    assert shield["parent_barrier"] == "N wall"
    assert shield["material"] == "Pb (additional)"
    assert shield["thickness_mm"] == 2.2
    assert shield["occupancy_factor"] == wall["occupancy_factor"]
    assert shield["design_goal_uSv_per_week"] == wall["design_goal_uSv_per_week"]
    assert shield["transmitted_dose_uSv_per_week"] < wall["transmitted_dose_uSv_per_week"]
    assert shield["bucky_shield_attenuation_applied"] is True


def test_xr20c_subbarrier_does_not_shift_following_structural_rows():
    project, room = _shielded_project()
    live = build_xray_results_model(project, room)
    schedule = build_canonical_barrier_schedule_payload(_App(project), room, room_results=live)
    by_name = {row["name"]: row for row in schedule}
    for barrier in room.barriers:
        assert barrier.name in by_name
        expected = next(row for row in live if row.get("barrier") == barrier.name)
        assert by_name[barrier.name]["transmitted_dose_uSv_per_week"] == expected["transmitted_dose_uSv_per_week"]
        assert by_name[barrier.name]["occupancy_factor"] == expected["occupancy_factor"]
        assert by_name[barrier.name]["design_goal_uSv_per_week"] == expected["design_goal_uSv_per_week"]


def test_xr20c_report_schedule_preserves_bucky_provenance():
    project, room = _shielded_project()
    live = build_xray_results_model(project, room)
    schedule = build_canonical_barrier_schedule_payload(_App(project), room, room_results=live)
    shield = next(row for row in schedule if row["barrier_element_type"] == "bucky_shield")
    assert shield["bucky_shield_material"] == "Pb"
    assert shield["bucky_shield_thickness_mm"] == 2.2
    assert "structural wall plus Pb 2.20 mm Bucky Shield" in shield["bucky_shield_provenance"]
