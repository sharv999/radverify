from pathlib import Path


def test_project_room_selector_does_not_advertise_non_production_plugin_stubs():
    text = Path("tabs/project_tab_layout.py").read_text(encoding="utf-8")
    assert "Non-production plugin stubs:" not in text
    assert "X-ray and SPECT/CT are coming soon" not in text
