from pathlib import Path


def test_source_live_preview_module_delegates_to_plugin():
    app_text = Path("app.py").read_text(encoding="utf-8")
    preview_text = Path("tabs/source_live_preview.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    xray_text = Path("modalities/xray.py").read_text(encoding="utf-8")
    registry_text = Path("modalities/registry.py").read_text(encoding="utf-8")

    assert "from tabs.source_live_preview import update_live_source_preview_from_form" in app_text
    assert "return update_live_source_preview_from_form(self)" in app_text
    assert "source_live_preview_lines(" in preview_text
    assert "compute_ct_source_summary" in ct_text
    assert "compute_nm_source_summary" in registry_text
    assert "compute_xray_ncrp_simplified_source_summary" in xray_text
    assert 'if stype ==' not in preview_text
    assert 'elif stype ==' not in preview_text


def test_app_live_source_preview_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def update_live_source_preview_from_form(self):\n        from tabs.source_live_preview import update_live_source_preview_from_form" in app_text
    assert "BLOCKED: selected CT scanner has NULL/missing ksec." not in app_text
