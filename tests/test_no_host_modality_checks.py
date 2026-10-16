from pathlib import Path


def test_core_orchestration_has_no_modality_identity_branches():
    paths = (
        Path("geometry/source_sync.py"),
        Path("tabs/geometry_tab.py"),
        Path("tabs/source_tab_actions.py"),
        Path("reports/solver_reasoning_text.py"),
    )
    forbidden = (
        '== "CT"',
        '== "SPECT/CT"',
        '== "SPECT"',
        '== "PET"',
        '== "X-ray"',
        'in {"CT", "SPECT/CT"}',
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} still branches on {token}"


def test_geometry_behaviour_is_owned_by_modality_plugins():
    from modalities.registry import geometry_ui_for_modality, source_type_for_modality_role

    ct_ui = geometry_ui_for_modality("CT")
    spect_ct_ui = geometry_ui_for_modality("SPECT/CT")
    xray_ui = geometry_ui_for_modality("X-ray")

    assert ct_ui.scanner_metadata_group == "ct_standalone_diagnostic"
    assert spect_ct_ui.scanner_metadata_group == "hybrid_ct_component_attenuation_correction"
    assert xray_ui.static_options == ("General Radiography",)
    assert source_type_for_modality_role("CT", ct_ui.primary_source_role) == "ct_scatter"
    assert source_type_for_modality_role("SPECT/CT", spect_ct_ui.primary_source_role) == "spect_ct_secondary_scatter"
