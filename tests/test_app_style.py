from pathlib import Path


def test_app_style_module_exists_and_owns_style_configuration():
    app_text = Path("app.py").read_text(encoding="utf-8")
    style_text = Path("ui/app_style.py").read_text(encoding="utf-8")

    assert "from ui.app_style import configure_app_style" in app_text
    assert "style.theme_use" in style_text
    assert "Bahnschrift" in style_text
    assert "ttk.Style" in style_text


def test_app_configure_app_style_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _configure_app_style(self):\n        from ui.app_style import configure_app_style" in app_text
    assert "style.configure(\"Treeview\"" not in app_text
