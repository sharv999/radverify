from geometry.barrier_sync import apply_geometry_to_selected_room_barriers
from geometry.default_room_geometry import create_default_room_geometry
from models.shielding_models import Room


class _App:
    def create_default_room_geometry(self, room_name, modality):
        return create_default_room_geometry(room_name, modality)

    def _coerce_barrier_schema(self, barrier):
        return barrier

    def enforce_room_source_types(self, room):
        return None


def _roles(room):
    return {b.name: b.barrier_role for b in room.barriers}


def test_xr10_new_gxr_geometry_has_explicit_default_chest_receptor():
    g = create_default_room_geometry("X-ray Room 1", "X-ray")
    assert g.wall_bucky is not None
    assert g.wall_bucky.wall == "W"
    assert g.wall_bucky.offset_m == 1.2


def test_xr10_new_gxr_room_seeds_representative_fig52_wall_scenarios():
    room = Room(name="X-ray Room 1", modality="X-ray", barriers=[], geometry=None)
    apply_geometry_to_selected_room_barriers(_App(), room)

    assert _roles(room) == {
        "N wall": "fig52_secondary_wall",
        "E wall": "fig52_cross_table_wall",
        "S wall": "fig52_secondary_wall",
        "W wall": "fig52_chest_bucky_wall",
        "Control wall": "fig52_control_wall",
        "Floor": "fig52_floor_under_table",
        "Ceiling": "fig52_ceiling",
    }


def test_xr10_sync_preserves_user_assigned_fig52_roles_after_initial_seed():
    room = Room(name="X-ray Room 1", modality="X-ray", barriers=[], geometry=None)
    app = _App()
    apply_geometry_to_selected_room_barriers(app, room)
    next(b for b in room.barriers if b.name == "E wall").barrier_role = "fig52_secondary_wall"
    next(b for b in room.barriers if b.name == "S wall").barrier_role = "fig52_secondary_wall"

    apply_geometry_to_selected_room_barriers(app, room)

    roles = _roles(room)
    assert roles["E wall"] == "fig52_secondary_wall"
    assert roles["S wall"] == "fig52_secondary_wall"
    assert roles["W wall"] == "fig52_chest_bucky_wall"


def test_xr10_moving_wall_bucky_reassigns_only_chest_wall_not_cross_table_guess():
    room = Room(name="X-ray Room 1", modality="X-ray", barriers=[], geometry=None)
    app = _App()
    apply_geometry_to_selected_room_barriers(app, room)
    room.geometry.wall_bucky.wall = "E"

    apply_geometry_to_selected_room_barriers(app, room)

    roles = _roles(room)
    assert roles["E wall"] == "fig52_chest_bucky_wall"
    assert roles["N wall"] == "fig52_secondary_wall"
    # Existing project roles are not silently re-guessed after the user edits geometry.
    assert roles["S wall"] == "fig52_secondary_wall"
