from pathlib import Path


def test_geometry_rotation_control_is_exposed_for_ct_only():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    assert "self.rotate_scanner_button = ttk.Button(" in text
    assert 'show_ct_ksec = selector_kind == "ct_scanner_database"' in text
    assert 'if show_ct_ksec:' in text
    assert 'self.rotate_scanner_button.configure(text="Rotate scanner 90° CW")' in text
    assert 'self.rotate_scanner_button.grid_remove()' in text
    assert 'show_xray_rotation' not in text
    assert 'Rotate table/tube 90° CW' not in text
