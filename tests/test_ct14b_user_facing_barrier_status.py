from pathlib import Path


def test_barriers_tab_renders_canonical_barrier_schedule_status():
    text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")

    assert "from reports.barrier_schedule import build_canonical_barrier_schedule_payload" in text
    assert "schedule_rows = build_canonical_barrier_schedule_payload(" in text
    assert 'status = str(row.get("compliance_status") or row.get("status") or "").strip().upper()' in text
    assert "from tabs.barrier_table_formatting import format_barrier_table_cell" in text
    assert 'values = [format_barrier_table_cell(row, col) for col in app.BARRIER_COLUMNS]' in text


def test_legacy_user_facing_status_helper_preserves_physics_precedence():
    text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")

    assert "def user_facing_status_from_visual_risk" in text
    assert 'if risk in {"FAIL", "REVIEW"}:\n        return risk' in text
    assert 'if status in {"FAIL", "ERROR", "NON-COMPLIANT"}:\n        return "FAIL"' in text
    assert 'if status in {"REVIEW", "WARN", "WARNING"}:\n        return "REVIEW"' in text
