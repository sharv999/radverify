from pathlib import Path


def test_gxr_chest_bucky_dropdown_only_east_west():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    assert 'values=["E", "W"], state="readonly"' in text


def test_gxr_chest_bucky_update_guards_wall_selection():
    text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")
    section = text.split("def add_or_update_xray_chest_receptor(self):", 1)[1].split("def nudge_xray_chest_bucky", 1)[0]
    assert 'if wall not in {"E", "W"}:' in section
    assert 'g.bucky_shield = BuckyShield(wall=wall, offset_m=offset)' in section
