from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_new_control_wall_creation_forces_pb_088():
    source=(ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    block=source[source.index("    def add_or_update_xray_control_wall"):source.index("    def remove_xray_control_wall")]
    assert 'is_new_control_wall = getattr(g, "control_wall", None) is None' in block
    assert 'self.xray_control_material_var.set("Pb")' in block
    assert 'self.xray_control_thickness_var.set("0.88")' in block

def test_existing_control_wall_remains_user_editable():
    source=(ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    block=source[source.index("    def add_or_update_xray_control_wall"):source.index("    def remove_xray_control_wall")]
    assert 'material = str(self.xray_control_material_var.get() or "Pb")' in block
    assert 'thickness = max(0.0, float(self.xray_control_thickness_var.get()))' in block
