from engine.shielding_engine import default_barriers
from models.shielding_models import Room
from services.room_defaults import apply_new_xray_wall_defaults, apply_room_constraint_defaults


class _App:
    def __init__(self):
        self.room_constraint_summary = {}


def test_xr19c1_generic_room_constraints_do_not_restore_gxr_wall_t_point_2():
    room = Room(name="X-ray Room 1", modality="X-RAY", barriers=default_barriers())
    apply_new_xray_wall_defaults(room)

    # This is the real post-transition call that previously changed T=1.0
    # straight back to the generic Corridor value T=0.2.
    apply_room_constraint_defaults(_App(), room)

    walls = [b for b in room.barriers if b.name in {"N wall", "E wall", "S wall", "W wall"}]
    assert len(walls) == 4
    for barrier in walls:
        assert barrier.material == "Pb"
        assert barrier.thickness_mm == 0.88
        assert barrier.occupancy_factor == 1.0
        assert barrier.design_goal_uSv_per_week == 10.0
