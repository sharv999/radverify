from pathlib import Path


def test_app_delegates_barriers_tab_layout_to_layout_module():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "from tabs.barriers_tab_layout import build_barriers_tab" in text
    assert "return build_barriers_tab(self)" in text
    assert "from tabs.barriers_tab import build_barriers_tab" not in text


def test_barriers_tab_layout_delegates_to_existing_barriers_module():
    text = Path("tabs/barriers_tab_layout.py").read_text(encoding="utf-8")

    assert "from tabs.barriers_tab import build_barriers_tab as _build_barriers_tab" in text
    assert "return _build_barriers_tab(app)" in text


def test_barriers_tab_does_not_expose_heatmap_checkbox():
    text = Path("tabs/barriers_tab.py").read_text(encoding="utf-8")

    assert 'text="Heatmap View"' not in text
    assert "variable=app.heatmap_mode_var" not in text
