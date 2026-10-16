from geometry.canvas_symbols import draw_chest_bucky_tube_combo


class FakeCanvas:
    def __init__(self): self.calls=[]
    def _add(self,k,*a,**kw): self.calls.append((k,a,kw)); return len(self.calls)
    def create_polygon(self,*a,**kw): return self._add("polygon",*a,**kw)
    def create_line(self,*a,**kw): return self._add("line",*a,**kw)


def _coords(args):
    return args[0] if len(args)==1 and isinstance(args[0], list) else args


def test_xr13b_east_wall_rear_plate_touches_wall_and_stand_is_in_front():
    c=FakeCanvas(); draw_chest_bucky_tube_combo(c, 300, 100, "E", 40, distance_m=2.5)
    polys=[_coords(a) for k,a,kw in c.calls if k=="polygon"]
    rear, stand = polys[0], polys[1]
    rear_x=list(rear[0::2]); stand_x=list(stand[0::2])
    assert max(rear_x) == 300  # rear plate touches E wall face
    assert max(stand_x) <= min(rear_x)  # tall bucky is room-side / in front


def test_xr13b_centreline_extends_half_metre_beyond_tube_side():
    c=FakeCanvas(); draw_chest_bucky_tube_combo(c, 300, 100, "E", 40, distance_m=2.5)
    line=next(a for k,a,kw in c.calls if k=="line")
    # E wall points inward to decreasing x: 2.5 m to tube + 0.5 m extension.
    assert line[0] == 300 + 0.1*40
    assert line[2] == 300 - 3.0*40


def test_xr13b_geometry_tab_hides_xray_table_rotation_control():
    import inspect
    from tabs.geometry_tab import GeometryTab
    text=inspect.getsource(GeometryTab._update_source_control_visibility)
    assert "Rotate table/tube 90° CW" not in text
    assert "show_xray_rotation" not in text
    assert "if show_ct_ksec:" in text
