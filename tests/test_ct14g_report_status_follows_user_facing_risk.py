from pathlib import Path


def test_canonical_barrier_schedule_has_user_facing_status_helper():
    text = Path("reports/barrier_schedule.py").read_text(encoding="utf-8")

    assert "def _user_facing_status(" in text
    assert "margin < 0.5" in text
    assert 'return "REVIEW"' in text


def test_results_payload_builder_uses_canonical_schedule_not_raw_compliance_loop():
    text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8")

    assert "from reports.barrier_schedule import build_canonical_barrier_schedule_payload" in text
    assert "barrier_rows = build_canonical_barrier_schedule_payload(" in text
    assert 'row["compliance_status"] = status' in text


def test_barriers_tab_and_pdf_share_canonical_schedule_builder():
    ui_text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")
    payload_text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8")

    assert "build_canonical_barrier_schedule_payload" in ui_text
    assert "build_canonical_barrier_schedule_payload" in payload_text
