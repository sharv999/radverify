from pathlib import Path


def test_barrier_live_results_module_exists_and_owns_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    live_text = Path("tabs/barrier_live_results.py").read_text(encoding="utf-8")

    assert "def get_barrier_live_result(app, room: Room, barrier: Barrier)" in live_text
    assert "from tabs.barrier_live_results import get_barrier_live_result" not in app_text
    assert "def get_barrier_live_result(self" not in app_text


def test_live_result_callers_use_module_helpers_directly():
    paths = [
        "tabs/barriers_tab_actions.py",
        "tabs/barrier_risk_ui.py",
        "tabs/results_tab_rendering.py",
    ]

    joined = "\n".join(Path(path).read_text(encoding="utf-8") for path in paths)

    assert "app.get_barrier_live_result(" not in joined
    assert "get_barrier_live_result(app," in joined