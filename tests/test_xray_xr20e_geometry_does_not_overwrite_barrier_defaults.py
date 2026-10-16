from pathlib import Path


def test_generic_geometry_update_does_not_commit_barrier_editor_fields():
    source = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    start = source.index("    def update_model_from_fields(self, show_errors=True):")
    end = source.index("    def _opening_material_values", start)
    body = source[start:end]

    assert "self.app._apply_geometry_to_selected_room_barriers(room)" in body
    assert "self.apply_barrier_fields_to_room(room)" not in body
    assert "self.apply_p_field_to_room(room)" not in body


def test_barrier_specific_callbacks_remain_authoritative():
    source = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    start = source.index("    def on_barrier_field_change(self, *_):")
    end = source.index("    def update_model_from_fields", start)
    body = source[start:end]
    assert "self.apply_barrier_fields_to_room(room)" in body

    sync = Path("geometry/barrier_sync.py").read_text(encoding="utf-8")
    p_start = sync.index("    def on_p_changed(self, event=None):")
    p_end = sync.index("    def _normalise_t_value", p_start)
    assert "self.apply_p_field_to_room(room)" in sync[p_start:p_end]
