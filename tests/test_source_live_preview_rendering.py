from pathlib import Path


def test_source_live_preview_rendering_helpers_extracted():
    app_text = Path("app.py").read_text(encoding="utf-8")
    preview_text = Path("tabs/source_live_preview.py").read_text(encoding="utf-8")

    assert "from tabs.source_live_preview import configure_source_calc_text_tags" in app_text
    assert "from tabs.source_live_preview import insert_source_calc_lines" in app_text
    assert "from tabs.source_live_preview import source_calc_line_tags" in app_text

    assert "def configure_source_calc_text_tags(app)" in preview_text
    assert "def insert_source_calc_lines(app, lines: list[str])" in preview_text
    assert "def source_calc_line_tags(app, line: str)" in preview_text

    assert 'self.source_calc_text.tag_configure(' not in app_text
    assert 'self.source_calc_text.insert("end"' not in app_text


def test_app_source_live_preview_rendering_methods_are_thin_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert (
        "    def _configure_source_calc_text_tags(self) -> None:\n"
        "        from tabs.source_live_preview import configure_source_calc_text_tags"
    ) in app_text
    assert (
        "    def _insert_source_calc_lines(self, lines: list[str]) -> None:\n"
        "        from tabs.source_live_preview import insert_source_calc_lines"
    ) in app_text
