from pathlib import Path


def test_results_output_helpers_owned_outside_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    helpers_text = Path("tabs/results_output_helpers.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/results_tab_actions.py").read_text(encoding="utf-8")

    expected_helpers = [
        "def default_report_filename(",
        "def resolve_logo_path(",
        "def build_generation_summary_lines(",
    ]

    for token in expected_helpers:
        assert token in helpers_text

    removed_app_methods = [
        "def _default_report_filename(self",
        "def _resolve_logo_path(self",
        "def _build_generation_summary_lines(",
    ]

    for token in removed_app_methods:
        assert token not in app_text

    assert "default_report_filename(app)" in actions_text
    assert "resolve_logo_path(app)" in actions_text
    assert "app._default_report_filename(" not in actions_text
    assert "app._resolve_logo_path(" not in actions_text


def test_generate_outputs_wrapper_remains_as_button_command_boundary():
    app_text = Path("app.py").read_text(encoding="utf-8")
    layout_text = Path("tabs/results_tab_layout.py").read_text(encoding="utf-8")

    assert "def generate_outputs(self):" in app_text
    assert "command=app.generate_outputs" in layout_text