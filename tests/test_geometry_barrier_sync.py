from pathlib import Path


def test_geometry_barrier_sync_module_owns_app_sync_helpers():
    app_text = Path("app.py").read_text(encoding="utf-8")
    sync_text = Path("geometry/barrier_sync.py").read_text(encoding="utf-8")

    # These two still remain as app-level compatibility wrappers for now.
    required_remaining_wrappers = [
        "from geometry.barrier_sync import apply_geometry_to_selected_room_barriers",
        "from geometry.barrier_sync import geometry_changed",
    ]

    for token in required_remaining_wrappers:
        assert token in app_text

    # safe_refresh_barrier_schedule has moved one step further:
    # callers now import/use geometry.barrier_sync.safe_refresh_barrier_schedule directly.
    assert "def safe_refresh_barrier_schedule(app)" in sync_text
    assert "from geometry.barrier_sync import safe_refresh_barrier_schedule" not in app_text


def test_app_geometry_barrier_sync_methods_are_thin_wrappers_where_still_intentional():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert (
        "    def _apply_geometry_to_selected_room_barriers(self, room: Room) -> None:\n"
        "        from geometry.barrier_sync import apply_geometry_to_selected_room_barriers"
    ) in app_text

    assert (
        "    def geometry_changed(self):\n"
        "        from geometry.barrier_sync import geometry_changed"
    ) in app_text

    assert "    def _safe_refresh_barrier_schedule(self):" not in app_text
    assert "from geometry.barrier_sync import safe_refresh_barrier_schedule" not in app_text


def test_safe_refresh_barrier_schedule_callers_use_sync_function_directly():
    paths = [
        Path("tabs/barriers_optimizer.py"),
        Path("tabs/barriers_tab_actions.py"),
        Path("tabs/barrier_risk_ui.py"),
        Path("tabs/geometry_tab.py"),
        Path("tabs/project_tab_actions.py"),
        Path("tabs/source_ct_actions.py"),
        Path("tabs/source_tab_actions.py"),
        Path("services/app_refresh.py"),
        Path("services/project_ui_state.py"),
    ]

    joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "._safe_refresh_barrier_schedule(" not in joined
    assert "safe_refresh_barrier_schedule(" in joined