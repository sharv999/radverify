from pathlib import Path


def test_report_assets_module_exists_and_owns_logo_resolution():
    app_text = Path("app.py").read_text(encoding="utf-8")
    assets_text = Path("reports/report_assets.py").read_text(encoding="utf-8")
    helpers_text = Path("tabs/results_output_helpers.py").read_text(encoding="utf-8")

    assert "def resolve_logo_path(" in assets_text

    assert "from reports.report_assets import resolve_logo_path" not in app_text
    assert "def _resolve_logo_path(self" not in app_text

    assert "from reports.report_assets import resolve_logo_path" in helpers_text
    assert "return resolve_logo_path()" in helpers_text


def test_app_logo_resolution_wrapper_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "def _resolve_logo_path(self" not in app_text
    assert "from reports.report_assets import resolve_logo_path" not in app_text