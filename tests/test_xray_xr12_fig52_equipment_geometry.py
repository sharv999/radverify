from geometry.geometry_model import ControlWall
from geometry.canvas_symbols import draw_xray_machine_icon, draw_wall_bucky


class FakeCanvas:
    def __init__(self): self.calls=[]
    def _add(self, kind, *args, **kwargs): self.calls.append((kind,args,kwargs)); return len(self.calls)
    def create_polygon(self,*a,**k): return self._add('polygon',*a,**k)
    def create_line(self,*a,**k): return self._add('line',*a,**k)
    def create_text(self,*a,**k): return self._add('text',*a,**k)
    def create_rectangle(self,*a,**k): return self._add('rectangle',*a,**k)


def test_xr12_control_wall_nib_length_round_trips_and_legacy_defaults():
    wall = ControlWall(center_x_m=2.0, center_y_m=3.0, length_m=1.8, orientation_deg=90, nib_length_m=0.9)
    restored = ControlWall.from_dict(wall.to_dict())
    assert restored == wall
    assert ControlWall.from_dict({'length_m': 1.5}).nib_length_m == 0.75


def test_xr12_gxr_icon_is_superseded_by_simple_table_tube_schematic():
    c=FakeCanvas(); draw_xray_machine_icon(c,100,100,scale=40)
    texts=[k.get('text') for kind,args,k in c.calls if kind=='text']
    assert 'Tube 1' not in texts
    assert 'Tube 2' not in texts
    assert 'Radiographic table' not in texts
    assert sum(1 for kind,args,k in c.calls if kind=='polygon') >= 3

def test_xr12_chest_bucky_is_solid_wall_stand_not_old_dashed_box():
    c=FakeCanvas(); draw_wall_bucky(c,100,100)
    texts=[k.get('text') for kind,args,k in c.calls if kind=='text']
    assert 'Chest bucky' not in texts
    rects=[k for kind,args,k in c.calls if kind=='rectangle']
    assert len(rects) == 1
    assert all('dash' not in k for k in rects)
