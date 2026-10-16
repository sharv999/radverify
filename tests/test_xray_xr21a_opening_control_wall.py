from types import SimpleNamespace

import pytest

from geometry.geometry_model import ControlWall, Opening, RadiationSourceGeometry, RoomGeometry
from models.shielding_models import Barrier, Project, Room, Source
from services.opening_physics import make_opening_physics_barrier, opening_live_result


class _Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def _case(offset=3.0, control=True):
    g = RoomGeometry(
        room_name="XR", width_m=6.0, length_m=6.0,
        source=RadiationSourceGeometry(label="X-ray", x_m=3.0, y_m=2.0),
        control_wall=(ControlWall(center_x_m=3.0, center_y_m=4.0, length_m=1.0,
                                  orientation_deg=0, material="Pb", thickness_mm=0.88)
                      if control else None),
    )
    opening = Opening(wall="N", opening_type="door", offset_m=offset, width_m=0.9,
                      pb_equiv_mm=0.88, material="Pb", id="D1")
    g.openings = [opening]
    north = Barrier(name="N wall", material="Pb", thickness_mm=0.88,
                    barrier_role="fig52_secondary_wall", distance_m=4.0,
                    occupancy_factor=0.5, design_goal_uSv_per_week=20.0)
    src = Source(name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp",
                 room_name="XR", params={"xray_method":"ncrp_simplified", "exam_room_type":"general_radiography", "exams_per_week":125})
    room = Room(name="XR", modality="X-RAY", sources=[src], barriers=[north], geometry=g)
    project = Project(project_name="XR21A", modality="X-RAY", rooms=[room], sources=[src])
    app = SimpleNamespace(project=project, global_energy_var=_Var("120 kVp"), solver_mode_var=_Var("Auto"))
    return app, room, opening


def test_xr21a_opening_ray_uses_actual_opening_centre_and_finite_control_wall():
    app, room, opening = _case(offset=3.0, control=True)
    assert room.geometry.opening_center_point(opening) == (3.0, 6.0)
    assert room.geometry.source_to_opening_distance_m(opening) == pytest.approx(4.0)
    assert room.geometry.control_wall_intercepts_opening_ray(opening) is True

    _, miss_room, miss = _case(offset=5.0, control=True)
    assert miss_room.geometry.control_wall_intercepts_opening_ray(miss) is False


def test_xr21a_opening_inherits_parent_t_p_and_gets_control_wall_credit_only_when_intercepted():
    app, room, opening = _case(offset=3.0, control=True)
    barrier = make_opening_physics_barrier(room, opening, 1)
    assert barrier.occupancy_factor == pytest.approx(0.5)
    assert barrier.design_goal_uSv_per_week == pytest.approx(20.0)
    assert barrier.distance_m == pytest.approx(4.0)

    _, credited = opening_live_result(app, room, opening, 1)
    assert credited["control_wall_attenuation_applied"] is True
    assert 0.0 < credited["control_wall_secondary_transmission"] < 1.0
    assert "inherits T=0.5 and P=20" in credited["notes"]

    app0, room0, opening0 = _case(offset=3.0, control=False)
    _, baseline = opening_live_result(app0, room0, opening0, 1)
    assert baseline["control_wall_attenuation_applied"] is False
    assert credited["unshielded_weekly_dose_uSv"] < baseline["unshielded_weekly_dose_uSv"]
    assert credited["transmitted_dose_uSv_per_week"] < baseline["transmitted_dose_uSv_per_week"]
