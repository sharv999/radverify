from pathlib import Path

from tabs.results_tab_help import (
    parse_results_barrier_line,
    parse_solver_reasoning_line,
    solver_help_title,
)


def test_results_tab_help_module_parses_clickable_barrier_lines():
    assert parse_results_barrier_line("✅ CT Room / North Wall -> PASS") == ("CT Room", "North Wall")
    assert parse_results_barrier_line("⚠️ X-ray / Door -> REVIEW") == ("X-ray", "Door")
    assert parse_results_barrier_line("Not a barrier line") == (None, None)


def test_results_tab_help_module_detects_solver_reasoning_lines():
    assert parse_solver_reasoning_line("Solver reasoning: CT component used")
    assert not parse_solver_reasoning_line("✅ CT / North -> PASS")


def test_results_tab_help_module_titles_solver_paths():
    assert solver_help_title("ncrp-primary") == "NCRP solver"
    assert solver_help_title("aapm-ct") == "AAPM solver"
    assert solver_help_title("mu-buildup") == "Mu + buildup solver"


def test_results_help_module_owns_results_help_methods_without_app_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")
    help_text = Path("tabs/results_tab_help.py").read_text(encoding="utf-8")

    required_helpers = [
        "def parse_results_barrier_line(",
        "def room_barrier_from_results_text_index(",
        "def solver_help_title(",
        "def solver_help_text(",
        "def parse_solver_reasoning_line(",
        "def solver_reasoning_text(",
        "def show_solver_help_from_results_line(",
        "def on_results_text_click(",
    ]

    for token in required_helpers:
        assert token in help_text

    removed_app_wrappers = [
        "from tabs.results_tab_help import parse_results_barrier_line",
        "from tabs.results_tab_help import room_barrier_from_results_text_index",
        "from tabs.results_tab_help import solver_help_title",
        "from tabs.results_tab_help import solver_help_text",
        "from tabs.results_tab_help import parse_solver_reasoning_line",
        "from tabs.results_tab_help import solver_reasoning_text",
        "from tabs.results_tab_help import show_solver_help_from_results_line",
        "from tabs.results_tab_help import on_results_text_click",
        "def _parse_results_barrier_line(self",
        "def _room_barrier_from_results_text_index(self",
        "def _solver_help_text(self",
        "def _solver_reasoning_text(self",
    ]

    for token in removed_app_wrappers:
        assert token not in app_text