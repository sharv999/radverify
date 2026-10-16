from pathlib import Path


def test_geometry_scanner_change_updates_source_label_at_end_of_handler():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    assert "def _set_geometry_source_label_from_scanner" in text

    start = text.index("    def on_geometry_scanner_changed")
    end = text.index("\n\n    def load_selected_room_geometry", start)
    block = text[start:end]

    assert "self._set_geometry_source_label_from_scanner(room, scanner)" in block

    final_label_pos = block.rfind("self._set_geometry_source_label_from_scanner(room, scanner)")
    redraw_pos = block.rfind("self.request_redraw()")

    assert final_label_pos != -1
    assert redraw_pos != -1
    assert final_label_pos < redraw_pos


def test_geometry_scanner_label_helper_updates_variable_and_model():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    start = text.index("    def _set_geometry_source_label_from_scanner")
    end = text.index("\n\n    def _scanner_phantom_for_family", start)
    block = text[start:end]

    assert "self.source_label_var.set(model_label)" in block
    assert "room.geometry.source.label = model_label" in block
    assert "_friendly_model_for_scanner(scanner)" in block
