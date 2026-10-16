from types import SimpleNamespace


def test_default_ct_scanner_identity_initialiser_exists():
    text = open("geometry/source_sync.py", encoding="utf-8").read()

    assert "def initialise_missing_ct_source_from_geometry_selection" in text
    assert "manual_ksec_override" in text
    assert "on_geometry_scanner_changed" in text


def test_geometry_room_load_calls_default_ct_identity_initialiser():
    text = open("tabs/geometry_tab.py", encoding="utf-8").read()

    start = text.index("    def load_selected_room_geometry")
    end = text.index("    def draw_room_with_risk", start)
    block = text[start:end]

    assert "self.initialise_missing_ct_source_from_geometry_selection(room)" in block


def test_default_ct_identity_initialiser_does_not_overwrite_manual_override():
    text = open("geometry/source_sync.py", encoding="utf-8").read()

    start = text.index("def initialise_missing_ct_source_from_geometry_selection")
    end_marker = "\n    def sync_geometry_source_metadata_from_project_source"
    end = text.index(end_marker, start)
    block = text[start:end]

    assert 'manual_ksec_override", "0"' in block or "manual_ksec_override" in block
    assert "return" in block
    assert "on_geometry_scanner_changed" in block


def test_geometry_dropdown_loads_scanner_from_family_reverse_map():
    text = open("geometry/source_sync.py", encoding="utf-8").read()

    start = text.index("def load_scanner_from_room_source")
    end = text.index("\n\n    def apply_geometry_source_to_project", start)
    block = text[start:end]

    assert "_scanner_display_to_family" in block
    assert "family_id" in block
    assert "source_option_var.set(display_value)" in block