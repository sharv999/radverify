from pathlib import Path


def test_barrier_live_results_module_owns_dominant_source_lookup():
    app_text = Path("app.py").read_text(encoding="utf-8")
    live_text = Path("tabs/barrier_live_results.py").read_text(encoding="utf-8")
    assert "def dominant_source_for_barrier(app, barrier_name: str)" in live_text

    assert "def _dominant_source_for_barrier(self" not in app_text
    assert "from tabs.barrier_live_results import dominant_source_for_barrier" not in app_text
