from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def default_report_filename(app) -> str:
    from reports.report_naming import default_report_filename

    return default_report_filename(app.project)


def resolve_logo_path(app) -> Optional[Path]:
    from reports.report_assets import resolve_logo_path

    return resolve_logo_path()


def build_generation_summary_lines(
    app,
    pdf_path: Path,
    ai_report: Optional[Dict[str, Any]] = None,
) -> list[str]:
    from tabs.results_tab_text import build_generation_summary_lines

    return build_generation_summary_lines(app, pdf_path, ai_report=ai_report)