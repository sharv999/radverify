"""Display-only fixed-South GXR table beam tests."""
from geometry.geometry_canvas import GeometryCanvas


class FakeCanvas:
    def __init__(self):
        self.lines = []
        self.rectangles = []

    def create_line(self, *args, **kwargs):
        self.lines.append((args, kwargs))

    def create_rectangle(self, *args, **kwargs):
        self.rectangles.append((args, kwargs))


def test_table_beam_terminates_at_receptor_inside_table():
    canvas = FakeCanvas()
    GeometryCanvas._draw_gxr_table_beam_footprint(canvas, 100, 200, 0, 50)
    assert len(canvas.lines) == 2
    assert len(canvas.rectangles) == 1
    assert all(args[:2] == (100, 140) for args, _ in canvas.lines)
    assert {args[2:] for args, _ in canvas.lines} == {(90, 203.5), (110, 203.5)}
    assert canvas.rectangles[0][0] == (90, 190, 110, 210)
    assert all(kwargs["dash"] == (3, 5) for _, kwargs in canvas.lines)


def test_table_beam_does_not_rotate_and_is_display_only():
    a, b = FakeCanvas(), FakeCanvas()
    GeometryCanvas._draw_gxr_table_beam_footprint(a, 100, 200, 0, 50)
    GeometryCanvas._draw_gxr_table_beam_footprint(b, 100, 200, 90, 50)
    assert a.lines == b.lines
    assert a.rectangles == b.rectangles
    assert all(kwargs["tags"] == ("gxr_table_beam_envelope",) for _, kwargs in a.lines)
