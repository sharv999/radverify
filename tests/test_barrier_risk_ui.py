from pathlib import Path


def test_barrier_risk_ui_module_exists_and_owns_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    ui_text = Path("tabs/barrier_risk_ui.py").read_text(encoding="utf-8")

    expected_functions = [
        "def barrier_heatmap_color(",
        "def get_barrier_from_table_item(",
        "def barrier_visual_score(",
        "def on_barrier_risk_row_select(",
        "def sort_barriers_by_risk(",
        "def flash_barrier_row(",
        "def derive_primary_barrier_issue(",
        "def on_barrier_table_motion(",
        "def on_barrier_table_leave(",
        "def classify_barrier_visual_state(",
    ]

    for token in expected_functions:
        assert token in ui_text

    assert "from tabs.barrier_risk_ui import barrier_heatmap_color" not in app_text
    assert "from tabs.barrier_risk_ui import classify_barrier_visual_state" not in app_text
    assert "from tabs.barrier_risk_ui import get_barrier_from_table_item" not in app_text


def test_app_barrier_risk_methods_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    removed_methods = [
        "def _barrier_heatmap_color(self",
        "def _get_barrier_from_table_item(self",
        "def _barrier_visual_score(self",
        "def on_barrier_risk_row_select(self",
        "def sort_barriers_by_risk(self",
        "def flash_barrier_row(self",
        "def _derive_primary_barrier_issue(",
        "def on_barrier_table_motion(self",
        "def on_barrier_table_leave(self",
        "def _classify_barrier_visual_state(",
    ]

    for token in removed_methods:
        assert token not in app_text


def test_barrier_risk_callers_use_module_functions_directly():
    joined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "tabs/barriers_openings.py",
            "tabs/barriers_optimizer.py",
            "tabs/barriers_tab.py",
            "tabs/barriers_tab_actions.py",
            "tabs/results_tab_rendering.py",
        ]
    )

    forbidden = [
        "app._barrier_heatmap_color(",
        "app._get_barrier_from_table_item(",
        "app._barrier_visual_score(",
        "app._derive_primary_barrier_issue(",
        "app._classify_barrier_visual_state(",
        "app.flash_barrier_row(",
        "app.on_barrier_table_motion",
        "app.on_barrier_table_leave",
    ]

    for token in forbidden:
        assert token not in joined

    assert "flash_barrier_row(app," in joined
    assert "on_barrier_table_motion(app, event)" in joined
    assert "on_barrier_table_leave(app, event)" in joined