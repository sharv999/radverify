import inspect


def test_xr14a_gxr_subpanels_stand_alone_without_outer_heading():
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab._build_ui)
    assert 'text="General Radiography geometry"' not in text
    assert 'self.xray_chest_bucky_frame = ttk.LabelFrame(left, text="Chest Bucky"' in text
    assert 'self.xray_control_wall_frame = ttk.LabelFrame(left, text="Control Wall"' in text


def test_xr14a_control_wall_uses_rotate_button_not_orientation_dropdown():
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab._build_ui)
    assert 'Rotate control wall 90° CW' in text
    assert 'text="Orientation"' not in text
    assert 'values=["Horizontal","Vertical"]' not in text
    assert hasattr(GeometryTab, 'rotate_xray_control_wall_cw')


def test_xr14a_rotate_control_wall_toggles_hidden_orientation_and_updates_existing_wall():
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab.rotate_xray_control_wall_cw)
    assert '(current + 90) % 360' in text
    assert 'self.add_or_update_xray_control_wall()' in text

