from geometry.canvas_symbols import draw_xray_machine_icon, draw_chest_bucky_tube_combo

class FakeCanvas:
    def __init__(self): self.calls=[]
    def _add(self,k,*a,**kw): self.calls.append((k,a,kw)); return len(self.calls)
    def create_polygon(self,*a,**kw): return self._add('polygon',*a,**kw)
    def create_line(self,*a,**kw): return self._add('line',*a,**kw)
    def create_rectangle(self,*a,**kw): return self._add('rectangle',*a,**kw)
    def create_text(self,*a,**kw): return self._add('text',*a,**kw)

def test_table_tube_schematic_is_plain_and_has_no_old_tube_labels():
    c=FakeCanvas(); draw_xray_machine_icon(c,100,100,scale=40)
    assert not [kw.get('text') for k,a,kw in c.calls if k=='text']
    assert sum(k=='polygon' for k,a,kw in c.calls) >= 3

def test_optional_chest_bucky_combo_places_tube_2p5m_inward_from_north_wall():
    c=FakeCanvas(); draw_chest_bucky_tube_combo(c,100,50,'N',40,distance_m=2.5)
    centreline=next(a for k,a,kw in c.calls if k=='line')
    assert centreline[0] == centreline[2] == 100
    assert centreline[1] < 50 and centreline[3] > 150
    # Bucky stand + receptor + tube housing + tube triangle.
    assert sum(k=='polygon' for k,a,kw in c.calls) == 4


def test_xray_tube_triangles_point_toward_their_housings():
    c=FakeCanvas(); draw_xray_machine_icon(c,100,100,scale=40)
    triangle=[a for k,a,kw in c.calls if k=='polygon'][-1]
    coords=triangle[0] if len(triangle)==1 and isinstance(triangle[0], list) else triangle
    ys=list(coords[1::2])
    assert min(ys) < max(ys)  # apex is the upper point, toward table-tube housing

    c=FakeCanvas(); draw_chest_bucky_tube_combo(c,100,50,'N',40,distance_m=2.5)
    triangle=[a for k,a,kw in c.calls if k=='polygon'][-1]
    coords=triangle[0] if len(triangle)==1 and isinstance(triangle[0], list) else triangle
    ys=list(coords[1::2])
    assert max(ys) > min(ys)  # N-wall combo points inward toward its housing

def test_xray_layout_disables_one_m_reference_circle():
    from modalities.xray import XRAY_PLUGIN
    assert XRAY_PLUGIN.spec.layout_rendering.show_one_m_circle is False
