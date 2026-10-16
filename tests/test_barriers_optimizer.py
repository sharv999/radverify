from pathlib import Path


def test_barriers_optimizer_module_exists_and_owns_optimizer_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    optimizer_text = Path("tabs/barriers_optimizer.py").read_text(encoding="utf-8")

    assert "from tabs.barriers_optimizer import jump_to_barrier" in app_text
    assert "from tabs.barriers_optimizer import optimise_barriers" in app_text
    assert "from tabs.barriers_optimizer import render_optimizer_recommendations" in app_text
    assert "optimise_flagged_barriers(" not in app_text
    assert "optimise_flagged_barriers(" in optimizer_text
    assert "Generated {count} optimisation recommendation(s)" in optimizer_text
    assert "def render_optimizer_recommendations" in optimizer_text


def test_app_barriers_optimizer_methods_are_thin_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def jump_to_barrier(self, room_name: str, barrier_name: str):\n        from tabs.barriers_optimizer import jump_to_barrier" in app_text
    assert "    def _optimise_barriers(self, room_name: Optional[str] = None):\n        from tabs.barriers_optimizer import optimise_barriers" in app_text
    assert "    def optimise_selected_room(self):\n        from tabs.barriers_optimizer import optimise_selected_room" in app_text
    assert "    def optimise_all_rooms(self):\n        from tabs.barriers_optimizer import optimise_all_rooms" in app_text
    assert "    def render_optimizer_recommendations(self, recommendations: list[Dict[str, Any]]):\n        from tabs.barriers_optimizer import render_optimizer_recommendations" in app_text
