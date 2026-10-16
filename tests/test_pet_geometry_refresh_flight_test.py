from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_central_geometry_sync_refreshes_pet_barrier_results_preview():
    text = (ROOT / "geometry" / "barrier_sync.py").read_text(encoding="utf-8")
    geometry_changed = text[text.index("def geometry_changed(app) -> None:"):]

    assert "sync_geometry_source_barriers_for_room(" in geometry_changed
    assert "from tabs.pet_preview_panel import refresh_pet_barrier_results_preview" in geometry_changed
    assert "refresh_pet_barrier_results_preview(app, room=room)" in geometry_changed
    assert geometry_changed.index("sync_geometry_source_barriers_for_room(") < geometry_changed.index(
        "refresh_pet_barrier_results_preview(app, room=room)"
    )


def test_direct_geometry_barrier_edits_refresh_pet_barrier_results_preview():
    text = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    start = text.index("    def on_barrier_field_change(self, *_):")
    end = text.index("\n\n    def safe_live_update", start)
    method = text[start:end]

    assert "self.apply_barrier_fields_to_room(room)" in method
    assert "from tabs.pet_preview_panel import refresh_pet_barrier_results_preview" in method
    assert "refresh_pet_barrier_results_preview(self.app, room=room)" in method
    assert method.index("self.apply_barrier_fields_to_room(room)") < method.index(
        "refresh_pet_barrier_results_preview(self.app, room=room)"
    )


def test_pet_geometry_refresh_hooks_do_not_modify_production_barriers_tab():
    barriers_actions = (ROOT / "tabs" / "barriers_tab_actions.py").read_text(encoding="utf-8")
    barriers_tab = (ROOT / "tabs" / "barriers_tab.py").read_text(encoding="utf-8")

    assert "refresh_pet_barrier_results_preview" not in barriers_actions
    assert "refresh_pet_barrier_results_preview" not in barriers_tab


def test_central_geometry_sync_resets_spect_preview_position_to_canonical_geometry():
    text = (ROOT / "geometry" / "barrier_sync.py").read_text(encoding="utf-8")
    geometry_changed = text[text.index("def geometry_changed(app) -> None:"):]

    assert "reset_spect_preview_position_to_room_geometry" in geometry_changed
    assert "reset_spect_preview_position_to_room_geometry(app, room, refresh=False)" in geometry_changed
    assert "refresh_spect_preview(app, room)" in geometry_changed
    assert geometry_changed.index("sync_geometry_source_barriers_for_room(") < geometry_changed.index(
        "reset_spect_preview_position_to_room_geometry(app, room, refresh=False)"
    )
