from geometry.geometry_model import ControlWall, RadiationSourceGeometry, RoomGeometry


def _room(control_wall):
    return RoomGeometry(
        room_name="XR-17A",
        width_m=6.0,
        length_m=5.0,
        source=RadiationSourceGeometry(label="X-ray", x_m=2.0, y_m=2.0),
        control_wall=control_wall,
    )


def test_xr17a_external_wall_rays_are_perpendicular_and_deterministic():
    g = _room(None)
    assert g.external_wall_ray("N") == ((2.0, 2.0), (2.0, 5.0))
    assert g.external_wall_ray("S") == ((2.0, 2.0), (2.0, 0.0))
    assert g.external_wall_ray("E") == ((2.0, 2.0), (6.0, 2.0))
    assert g.external_wall_ray("W") == ((2.0, 2.0), (0.0, 2.0))


def test_xr17a_horizontal_control_wall_intercepts_only_ray_crossing_finite_segment():
    g = _room(ControlWall(center_x_m=2.0, center_y_m=3.0, length_m=2.0, orientation_deg=0))
    assert g.control_wall_intercepts_external_wall_ray("N") is True
    assert g.control_wall_intercepts_external_wall_ray("S") is False
    assert g.control_wall_intercepts_external_wall_ray("E") is False
    assert g.control_wall_intercepts_external_wall_ray("W") is False


def test_xr17a_vertical_control_wall_intercepts_only_ray_crossing_finite_segment():
    g = _room(ControlWall(center_x_m=4.0, center_y_m=2.0, length_m=2.0, orientation_deg=90))
    assert g.control_wall_intercepts_external_wall_ray("E") is True
    assert g.control_wall_intercepts_external_wall_ray("W") is False
    assert g.control_wall_intercepts_external_wall_ray("N") is False
    assert g.control_wall_intercepts_external_wall_ray("S") is False


def test_xr17a_finite_segment_miss_does_not_receive_interception():
    g = _room(ControlWall(center_x_m=4.5, center_y_m=3.0, length_m=1.0, orientation_deg=180))
    assert g.control_wall_intercepts_external_wall_ray("N") is False


def test_xr17a_endpoint_contact_counts_as_interception():
    g = _room(ControlWall(center_x_m=3.0, center_y_m=3.0, length_m=2.0, orientation_deg=180))
    assert g.control_wall_intercepts_external_wall_ray("N") is True


def test_xr17a_180_and_270_preserve_same_main_segment_intersection_geometry():
    horizontal = _room(ControlWall(center_x_m=2.0, center_y_m=3.0, length_m=2.0, orientation_deg=180))
    vertical = _room(ControlWall(center_x_m=4.0, center_y_m=2.0, length_m=2.0, orientation_deg=270))
    assert horizontal.control_wall_intercepts_external_wall_ray("N") is True
    assert vertical.control_wall_intercepts_external_wall_ray("E") is True


def test_xr17a_no_control_wall_never_intercepts():
    g = _room(None)
    assert all(not g.control_wall_intercepts_external_wall_ray(w) for w in "NESW")
