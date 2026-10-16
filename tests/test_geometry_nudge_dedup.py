from pathlib import Path


def test_geometry_nudge_method_has_single_owner():
    geometry_tab_text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    nudge_mixin_text = Path("geometry/geometry_nudge.py").read_text(encoding="utf-8")

    assert "def nudge_source_position" not in geometry_tab_text
    assert nudge_mixin_text.count("def nudge_source_position") == 1


def test_geometry_nudge_commits_to_model_update_path():
    nudge_mixin_text = Path("geometry/geometry_nudge.py").read_text(encoding="utf-8")

    assert "self.update_model_from_fields(show_errors=False)" in nudge_mixin_text
    assert "draw_room_with_risk" in nudge_mixin_text or "request_redraw" in nudge_mixin_text
