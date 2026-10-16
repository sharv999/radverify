from pathlib import Path


def test_results_text_and_help_modules_own_result_interpretation_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    help_text = Path("tabs/results_tab_help.py").read_text(encoding="utf-8")
    text_text = Path("tabs/results_tab_text.py").read_text(encoding="utf-8")

    expected_help_functions = [
        "def parse_results_barrier_line(",
        "def room_barrier_from_results_text_index(",
        "def solver_help_text(",
        "def solver_reasoning_text(",
    ]

    expected_text_functions = [
        "def dominant_source_text(",
        "def result_block_header(",
    ]

    for token in expected_help_functions:
        assert token in help_text

    for token in expected_text_functions:
        assert token in text_text

    removed_app_methods = [
        "def _parse_results_barrier_line(self",
        "def _solver_help_text(self",
        "def _room_barrier_from_results_text_index(self",
        "def _dominant_source_text(self",
        "def _solver_reasoning_text(self",
        "def _result_block_header(self",
    ]

    for token in removed_app_methods:
        assert token not in app_text


def test_results_text_callers_use_helpers_directly():
    joined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "tabs/barrier_live_results.py",
            "tabs/results_tab_rendering.py",
            "reports/results_payload_builder.py",
        ]
    )

    forbidden = [
        "app._dominant_source_text(",
        "app._solver_reasoning_text(",
        "app._result_block_header(",
        "app._solver_help_text(",
        "app._parse_results_barrier_line(",
        "app._room_barrier_from_results_text_index(",
    ]

    for token in forbidden:
        assert token not in joined

    assert "dominant_source_text(room, barrier, live)" in joined
    assert "solver_reasoning_text(room, barrier, live)" in joined