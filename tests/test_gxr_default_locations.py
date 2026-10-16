from geometry.default_room_geometry import create_default_room_geometry


def test_gxr_new_room_default_positions():
    g = create_default_room_geometry("X-ray Room 1", "X-ray")
    assert (g.source.x_m, g.source.y_m) == (2.0, 2.4)
    assert (g.wall_bucky.wall, g.wall_bucky.offset_m) == ("W", 1.2)
    assert (g.control_wall.center_x_m, g.length_m - g.control_wall.center_y_m) == (2.0, 1.5)
    assert (g.control_wall.length_m, g.control_wall.nib_length_m) == (1.5, 0.75)

def test_other_modality_has_no_gxr_control_wall():
    g = create_default_room_geometry("CT Room", "CT")
    assert g.control_wall is None


def test_gxr_modality_transition_seeds_geometry_without_changing_room_dimensions():
    from types import SimpleNamespace
    from services.room_defaults import apply_new_xray_geometry_defaults

    old = create_default_room_geometry("Room", "CT")
    old.length_m = 7.0
    old.width_m = 5.0
    room = SimpleNamespace(name="Room", modality="X-ray", geometry=old)
    apply_new_xray_geometry_defaults(room)
    g = room.geometry
    assert (g.length_m, g.width_m) == (7.0, 5.0)
    assert (g.source.x_m, g.source.y_m) == (2.0, 2.4)
    assert (g.wall_bucky.wall, g.wall_bucky.offset_m) == ("W", 1.2)
    assert (g.control_wall.center_x_m, g.length_m - g.control_wall.center_y_m) == (2.0, 1.5)

def test_gxr_geometry_transition_does_not_reset_non_xray():
    from types import SimpleNamespace
    from services.room_defaults import apply_new_xray_geometry_defaults
    g = create_default_room_geometry("Room", "CT")
    room = SimpleNamespace(name="Room", modality="CT", geometry=g)
    apply_new_xray_geometry_defaults(room)
    assert room.geometry is g


def test_new_gxr_bucky_shield_is_canonical_and_aligned():
    g = create_default_room_geometry("X-ray Room 1", "X-ray")
    assert g.bucky_shield is not None
    assert (g.bucky_shield.wall, g.bucky_shield.offset_m) == (g.wall_bucky.wall, g.wall_bucky.offset_m)
    assert (g.bucky_shield.width_m, g.bucky_shield.material, g.bucky_shield.thickness_mm) == (1.2, "Pb", 2.2)

def test_gxr_transition_initialises_bucky_shield():
    from types import SimpleNamespace
    from services.room_defaults import apply_new_xray_geometry_defaults
    room = SimpleNamespace(name="Room", modality="X-ray", geometry=create_default_room_geometry("Room", "CT"))
    apply_new_xray_geometry_defaults(room)
    assert room.geometry.bucky_shield is not None
    assert room.geometry.bucky_shield.wall == "W"
    assert room.geometry.bucky_shield.offset_m == 1.2
