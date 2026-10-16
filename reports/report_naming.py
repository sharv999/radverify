from __future__ import annotations


def default_report_filename(project) -> str:
    """Build a safe default PDF filename from project metadata."""
    project_name = str(getattr(project, "project_name", "") or "").strip()
    site = str(getattr(project, "site", "") or "").strip()
    base = project_name or site or "shielding_report"

    safe = "".join(ch if ch.isalnum() or ch in (" ", "-", "_") else "_" for ch in base).strip()
    safe = "_".join(safe.split())
    if not safe:
        safe = "shielding_report"

    return f"{safe}.pdf"
