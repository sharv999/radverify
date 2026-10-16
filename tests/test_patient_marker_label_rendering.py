from geometry.canvas_symbols import draw_nm_patient_icon


class _CanvasSpy:
    def __init__(self):
        self.texts = []
        self.lines = []

    def create_oval(self, *args, **kwargs):
        return None

    def create_line(self, *args, **kwargs):
        self.lines.append((args, kwargs))
        return None

    def create_text(self, *args, **kwargs):
        self.texts.append(kwargs.get("text"))
        return None


def test_patient_marker_icon_uses_descriptor_supplied_label():
    canvas = _CanvasSpy()
    draw_nm_patient_icon(canvas, 100.0, 100.0, 50.0, offset_m=0.0, label="PET")
    assert canvas.texts == ["PET"]


def test_patient_marker_icon_can_suppress_label():
    canvas = _CanvasSpy()
    draw_nm_patient_icon(canvas, 100.0, 100.0, 50.0, offset_m=0.0, label="")
    assert canvas.texts == []


def test_patient_marker_icon_draws_body_outline_lines():
    canvas = _CanvasSpy()
    draw_nm_patient_icon(canvas, 100.0, 100.0, 50.0, offset_m=0.0, label="SPECT")
    assert len(canvas.lines) >= 4
