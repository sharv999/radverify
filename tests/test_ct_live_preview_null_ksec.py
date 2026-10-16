from pathlib import Path


def test_ct_live_preview_blocks_blank_ksec_before_compute_summary():
    app_text = Path("app.py").read_text(encoding="utf-8")
    preview_text = Path("tabs/source_live_preview.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")

    assert "from tabs.source_live_preview import update_live_source_preview_from_form" in app_text
    assert "source_live_preview_lines" in preview_text
    assert "BLOCKED: selected CT scanner has NULL/missing ksec." in ct_text
