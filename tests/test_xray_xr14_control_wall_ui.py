import inspect


def test_xr14_control_wall_canvas_has_same_side_nibs():
    from geometry.geometry_canvas import GeometryCanvas
    text = inspect.getsource(GeometryCanvas._draw_control_wall)
    assert 'v1x, v1y = (-ux * c45 - nx * s45)' in text
    assert 'v2x, v2y = ( ux * c45 - nx * s45)' in text


def test_xr14_gxr_controls_are_grouped_into_chest_bucky_and_control_wall_panels():
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab._build_ui)
    assert 'text="Chest Bucky"' in text
    assert 'text="Control Wall"' in text
    assert 'chest_bucky_frame' in text
    assert 'control_wall_frame' in text
