from pathlib import Path


def test_project_tab_layout_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    layout_text = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")

    assert "from tabs.project_tab_layout import build_project_tab" in app_text
    assert "return build_project_tab(self)" in app_text
    assert "Apply Project Changes" not in app_text
    assert "PROJECT_FIELD_LABELS" in layout_text
    assert "Apply Project Changes" in layout_text


def test_project_tab_layout_exposes_builder():
    layout_text = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")

    assert "def build_project_tab(app)" in layout_text
    assert "app.project_vars" in layout_text
    assert "app.project_notes" in layout_text


def test_project_tab_has_client_database_controls_and_no_project_modality_selector():
    layout_text = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/project_tab_actions.py").read_text(encoding="utf-8")

    assert 'PROJECT_FIELD_LABELS = ["Project Name", "Client", "Site", "Assessor", "Date"]' in layout_text
    assert "app.project_client_combo = ttk.Combobox" in layout_text
    assert 'text="Add..."' in layout_text
    assert 'text="Delete"' in layout_text
    assert 'project_vars["Modality"]' not in layout_text
    assert 'project_vars["Modality"]' not in actions_text


def test_project_tab_has_single_refurbishment_checkbox_with_new_build_default():
    layout_text = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")

    assert 'app.project_refurbishment_var = tk.BooleanVar(value=False)' in layout_text
    assert 'text="Project Type"' in layout_text
    assert 'text="Refurbishment / existing facility (unchecked = New build)"' in layout_text
    assert layout_text.count('variable=app.project_refurbishment_var') == 1
