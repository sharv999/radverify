from pathlib import Path


def test_results_tab_layout_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    layout_text = Path("tabs/results_tab_layout.py").read_text(encoding="utf-8")

    assert "from tabs.results_tab_layout import build_results_tab" in app_text
    assert "return build_results_tab(self)" in app_text
    assert "def build_results_tab(app)" in layout_text
    assert 'text="Generate Outputs"' in layout_text


def test_results_tab_actions_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/results_tab_actions.py").read_text(encoding="utf-8")

    assert "from tabs.results_tab_actions import generate_outputs" in app_text
    assert "return generate_outputs(self)" in app_text
    assert "from reports.output_pipeline import generate_outputs_from_app" not in app_text
    assert "generate_outputs_from_app(" in actions_text
