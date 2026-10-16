from pathlib import Path

from geometry.geometry_model import ControlWall
from modalities.xray import XRAY_MODALITY

ROOT = Path(__file__).resolve().parents[1]


def test_control_wall_model_default_is_qualified_pb_construction():
    wall = ControlWall()
    assert wall.material == "Pb"
    assert wall.thickness_mm == 0.88


def test_xray_canvas_uses_colour_without_status_words():
    assert XRAY_MODALITY.layout_rendering.show_barrier_status_text is False
    source = (ROOT / "geometry" / "geometry_canvas.py").read_text(encoding="utf-8")
    block = source[source.index("    def _draw_control_wall("):source.index("    def _draw_wall_bucky(")]
    assert 'lines = ["Control wall", "SECONDARY — control wall"]' in block
    assert 'f"Control wall | {status}"' not in block
    assert '_risk_colour_for_barrier(risk_map, "Control wall")' in block


def test_control_wall_edits_are_live_applied_for_colour_refresh():
    source = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    assert "def on_xray_control_field_changed" in source
    assert 'control_var.trace_add("write", self.on_xray_control_field_changed)' in source
    assert "self.add_or_update_xray_control_wall()" in source[source.index("def on_xray_control_field_changed"):source.index("def on_barrier_field_change")]


def test_absent_or_removed_control_wall_resets_editor_to_pb_088():
    source = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    assert source.count('self.xray_control_material_var.set("Pb")') >= 2
    assert source.count('self.xray_control_thickness_var.set("0.88")') >= 2
