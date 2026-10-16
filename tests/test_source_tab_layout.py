from pathlib import Path


def test_app_delegates_sources_tab_layout_to_layout_module():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "from tabs.source_tab_layout import build_sources_tab" in text
    assert "return build_sources_tab(self)" in text
    assert "self.source_form_container = ttk.LabelFrame(right, text=\"Modality-Defined Source Parameters\")" not in text


def test_source_tab_layout_owns_sources_tab_widget_construction():
    text = Path("tabs/source_tab_layout.py").read_text(encoding="utf-8")

    assert "def build_sources_tab(app)" in text
    assert "self.source_form_container = ttk.LabelFrame(right, text=\"Modality-Defined Source Parameters\")" in text
    assert "self.source_calc_frame = ttk.LabelFrame(right, text=\"Live Source Calculations\")" in text


def test_sources_right_pane_is_vertically_scrollable_for_unified_modality_forms():
    text = Path("tabs/source_tab_layout.py").read_text(encoding="utf-8")

    assert "self.sources_right_canvas = tk.Canvas(" in text
    assert "self.sources_right_scrollbar = ttk.Scrollbar(" in text
    assert 'orient="vertical"' in text
    assert "command=self.sources_right_canvas.yview" in text
    assert "self.sources_right_canvas.configure(yscrollcommand=self.sources_right_scrollbar.set)" in text
    assert "self.sources_right_canvas.create_window(" in text
    assert 'anchor="nw"' in text
    assert 'right.bind("<Configure>", _sync_sources_scrollregion)' in text
    assert 'self.sources_right_canvas.bind("<Configure>", _sync_sources_content_width)' in text
    assert "build_pet_preview_panel(self, right)" not in text
    assert "build_spect_preview_panel(self, right)" not in text
