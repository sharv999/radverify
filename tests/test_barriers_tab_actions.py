from pathlib import Path


def test_app_delegates_basic_barrier_actions_to_actions_module():
    text = Path("app.py").read_text(encoding="utf-8")

    expected = {
        "add_barrier": "return add_barrier(self)",
        "delete_selected_barrier_from_table": "return delete_selected_barrier_from_table(self)",
        "apply_area_preset_to_selected_barrier": "return apply_area_preset_to_selected_barrier(self)",
    }

    for name, call in expected.items():
        assert f"from tabs.barriers_tab_actions import {name}" in text
        assert call in text


def test_app_no_longer_delegates_inline_barrier_edit_wrappers():
    text = Path("app.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/barriers_tab_actions.py").read_text(encoding="utf-8")

    assert "def on_barrier_table_double_click(" in actions_text
    assert "def save_inline_barrier_edit(" in actions_text

    assert "from tabs.barriers_tab_actions import on_barrier_table_double_click" not in text
    assert "from tabs.barriers_tab_actions import save_inline_barrier_edit" not in text
    assert "def on_barrier_table_double_click(self" not in text
    assert "def save_inline_barrier_edit(self" not in text