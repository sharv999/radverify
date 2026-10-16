from pathlib import Path


def test_report_naming_module_exists_and_owns_default_filename():
    app_text = Path("app.py").read_text(encoding="utf-8")
    naming_text = Path("reports/report_naming.py").read_text(encoding="utf-8")
    helpers_text = Path("tabs/results_output_helpers.py").read_text(encoding="utf-8")

    assert "def default_report_filename(project) -> str:" in naming_text

    assert "def _default_report_filename(self" not in app_text
    assert "from reports.report_naming import default_report_filename" not in app_text

    assert "from reports.report_naming import default_report_filename" in helpers_text
    assert "return default_report_filename(app.project)" in helpers_text


def test_app_default_report_filename_wrapper_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "def _default_report_filename(self" not in app_text
    assert "from reports.report_naming import default_report_filename" not in app_text