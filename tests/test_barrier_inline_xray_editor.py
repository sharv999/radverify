from pathlib import Path


def test_barrier_inline_xray_editor_extracted():
    app_text = Path("app.py").read_text(encoding="utf-8")
    editor_text = Path("tabs/barrier_inline_editors.py").read_text(encoding="utf-8")
    values_text = Path("tabs/barrier_inline_values.py").read_text(encoding="utf-8")

    assert "def show_xray_barrier_role_dropdown(" in editor_text
    assert "def xray_barrier_role_values(" in values_text
    assert "xray_barrier_role_values" in editor_text

    assert "def show_xray_barrier_role_dropdown(" not in app_text
    assert "def _xray_barrier_role_values(" not in app_text


def test_app_xray_inline_editor_methods_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "from tabs.barrier_inline_editors import xray_barrier_role_values" not in app_text
    assert "return xray_barrier_role_values()" not in app_text
    assert "return show_xray_barrier_role_dropdown(self" not in app_text