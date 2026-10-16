from pathlib import Path


def test_results_tab_rendering_module_exists_and_owns_rendering_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    rendering_text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")

    assert "from tabs.results_tab_rendering import build_live_results_lines" in app_text
    assert "from tabs.results_tab_rendering import refresh_barrier_schedule" in app_text
    assert "from tabs.results_tab_rendering import render_barrier_risk_panel" in app_text
    assert "def build_live_results_lines(app)" in rendering_text
    assert "def refresh_barrier_schedule(app)" in rendering_text
    assert "def render_barrier_risk_panel(app, room" in rendering_text


def test_app_results_rendering_methods_are_thin_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _build_live_results_lines(self):\n        from tabs.results_tab_rendering import build_live_results_lines" in app_text
    assert "    def refresh_results_tab(self):\n        from tabs.results_tab_rendering import refresh_results_tab" in app_text
    assert "    def refresh_barrier_schedule(self):\n        from tabs.results_tab_rendering import refresh_barrier_schedule" in app_text
    assert "    def render_barrier_risk_panel(self, room, room_results=None):\n        from tabs.results_tab_rendering import render_barrier_risk_panel" in app_text

    assert "# AI QA SUMMARY" not in app_text
    assert "Barrier risk panel error" not in app_text
