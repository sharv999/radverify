from pathlib import Path


def test_geometry_design_goal_dropdown_includes_100_uSv_per_week():
    text = (Path(__file__).resolve().parents[1] / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    assert 'values=["10 µSv/wk", "20 µSv/wk", "50 µSv/wk", "100 µSv/wk"]' in text
