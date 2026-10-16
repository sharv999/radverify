from pathlib import Path

from modalities.registry import production_modality_names, source_type_options


def test_public_modality_controls_expose_only_production_registry_entries():
    assert production_modality_names() == ["CT", "X-ray", "SPECT", "PET"]

    app_text = Path("app.py").read_text(encoding="utf-8")
    project_layout = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")
    geometry_text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    assert "ROOM_TYPES = production_modality_names()" in app_text
    # One-room projects own modality selection directly on Project.
    assert "values=tuple(app.ROOM_TYPES)" in project_layout
    assert "production_modality_names()" not in geometry_text
    assert '"Source type"' not in geometry_text

    # Non-production modalities remain registered for compatibility, but are not
    # advertised in normal production-selection UI.
    assert "Non-production plugin stubs:" not in project_layout
    assert "X-ray and SPECT/CT are coming soon" not in project_layout


def test_sources_tab_initial_choices_are_production_only():
    source_layout = Path("tabs/source_tab_layout.py").read_text(encoding="utf-8")
    assert "values=source_type_options(production_only=True)" in source_layout
    assert source_type_options(production_only=True) == ["ct_scatter", "xray_primary", "spect_patient", "pet_patient"]
    assert "xray_primary" in source_type_options(production_only=True)
    assert "spect_ct_secondary_scatter" not in source_type_options(production_only=True)
