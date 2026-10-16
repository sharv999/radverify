from pathlib import Path


def test_room_defaults_module_exists_and_owns_default_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    defaults_text = Path("services/room_defaults.py").read_text(encoding="utf-8")

    assert "from services.room_defaults import apply_room_constraint_defaults" in app_text
    assert "def apply_room_constraint_defaults" in defaults_text
    assert "get_barrier_design_defaults" in defaults_text
    assert "barrier.occupancy_factor = float" in defaults_text


def test_app_room_constraint_defaults_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _apply_room_constraint_defaults(self, room: Room) -> None:\n        from services.room_defaults import apply_room_constraint_defaults" in app_text
    assert "barrier.occupancy_factor = float(defaults" not in app_text
