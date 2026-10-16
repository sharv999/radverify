from pathlib import Path


def test_main_window_module_exists_and_owns_ui_assembly():
    app_text = Path("app.py").read_text(encoding="utf-8")
    main_window_text = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "from ui.main_window import build_ui" in app_text
    assert "return build_ui(self)" in app_text
    assert "def build_ui(app)" in main_window_text
    assert "app.main_notebook = ttk.Notebook(app)" in main_window_text
    assert "app._build_project_tab()" in main_window_text
    assert "app._build_ai_qa_tab()" not in main_window_text
    assert "AI QA" not in main_window_text


def test_app_build_ui_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _build_ui(self):\n        from ui.main_window import build_ui" in app_text
    assert "toolbar = ttk.Frame(self)" not in app_text
    assert "self.main_notebook = ttk.Notebook(self)" not in app_text
