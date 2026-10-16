import inspect


def test_xr16a_control_wall_uses_canonical_risk_colour_without_status_text():
    from geometry.geometry_canvas import GeometryCanvas
    text = inspect.getsource(GeometryCanvas._draw_control_wall)
    assert '_risk_colour_for_barrier(risk_map, "Control wall")' in text
    assert '_risk_status_for_barrier(risk_map, "Control wall")' not in text
    assert 'fill=colour' in text


def test_xr16a_control_wall_shows_barrier_text_and_canonical_dose_label():
    from geometry.geometry_canvas import GeometryCanvas
    text = inspect.getsource(GeometryCanvas._draw_control_wall)
    assert '"SECONDARY — control wall"' in text
    assert 'dose_labels.get("Control wall")' in text
    assert 'occupancy_factor' in text
    assert 'design_goal_uSv_per_week' in text
    assert 'thickness_mm' in text


def test_xr16a_draw_room_passes_geometry_to_control_wall_renderer():
    from geometry.geometry_canvas import GeometryCanvas
    text = inspect.getsource(GeometryCanvas.draw_room)
    assert 'self._draw_control_wall(geom.control_wall, geom, map_point, scale)' in text
