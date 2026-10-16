from pathlib import Path


def test_geometry_tab_has_no_selected_room_dropdown():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    assert 'text="Selected room"' not in text
    assert "self.room_combo = ttk.Combobox" not in text
    assert 'self.room_combo["values"]' not in text


def test_geometry_room_resolution_uses_project_single_room():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    assert 'rooms = list(getattr(getattr(self.app, "project", None), "rooms", []) or [])' in text
    assert "return rooms[0] if rooms else None" in text
