from pathlib import Path


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_host_live_preview_and_source_actions_delegate_to_plugins():
    preview = _text("tabs/source_live_preview.py")
    actions = _text("tabs/source_tab_actions.py")

    assert "source_live_preview_lines(" in preview
    assert "finalise_source_form_params_for_type(" in actions
    for token in ("ct_scatter", "nm_patient", "xray_primary", "primary_xray", "general_xray"):
        assert token not in preview
    for token in ('src.source_type == "nm_patient"', 'src.source_type == "xray_primary"'):
        assert token not in actions


def test_shared_source_factory_and_form_state_do_not_own_nm_rules():
    factory = _text("sources/source_factory.py")
    form_state = _text("tabs/source_form_state.py")
    enforcement = _text("sources/room_source_enforcement.py")

    assert "DEFAULT_NM_TCM99M_SOURCE_FACTORS" not in factory
    assert 'source_type == "nm_patient"' not in factory
    assert 'src.source_type == "nm_patient"' not in form_state
    assert 'source_type == "nm_patient"' not in enforcement
    assert "sanitize_source_params_for_type(" in form_state
    assert "sanitize_source_params_for_type(" in enforcement


def test_generic_renderer_and_export_do_not_name_ct_source_types():
    renderer = _text("geometry/scanner_renderer.py")
    report = _text("reports/report_generator.py")

    assert "_ct_scanner_label_values" not in renderer
    assert '"spect_ct_secondary_scatter"' not in renderer
    assert 'stype not in {"ct_scatter", "spect_ct_secondary_scatter"}' not in report
    assert 'source_contribution_group(stype) != "ct_scatter"' in report
