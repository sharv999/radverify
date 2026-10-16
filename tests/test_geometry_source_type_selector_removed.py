from pathlib import Path


def test_geometry_does_not_expose_obsolete_source_type_selector():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    assert '"Source type"' not in text
    assert "production_modality_names()" not in text
    # Hidden compatibility state remains for source-sync internals; modality is
    # populated from the sole room/project source inventory rather than edited
    # independently in Geometry.
    assert "self.source_type_var = tk.StringVar" in text
    assert "self.load_source_from_project(room)" in text
