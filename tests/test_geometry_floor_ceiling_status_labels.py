from geometry.geometry_canvas import GeometryCanvas


class _FloorCeilingRecorder:
    def __init__(self):
        self.calls = []

    def _risk_colour_for_barrier(self, risk_map, barrier_name):
        return GeometryCanvas._risk_colour_for_barrier(self, risk_map, barrier_name)

    def _risk_status_for_barrier(self, risk_map, barrier_name):
        return GeometryCanvas._risk_status_for_barrier(self, risk_map, barrier_name)

    def _draw_planar_barrier_label(self, **kwargs):
        self.calls.append(kwargs)


class _PlanarLabelRecorder:
    def __init__(self):
        self.text = []

    def _append_dose_label_lines(self, lines, dose):
        return GeometryCanvas._append_dose_label_lines(self, lines, dose)

    def create_text(self, x, y, **kwargs):
        self.text.append(kwargs["text"])


def test_floor_and_ceiling_canvas_labels_receive_live_pass_fail_status():
    canvas = _FloorCeilingRecorder()

    GeometryCanvas._draw_floor_ceiling_labels(
        canvas,
        field_x0=0.0,
        field_y0=0.0,
        field_w_px=800.0,
        scale=100.0,
        wall_t_values={"Floor": 1.0, "Ceiling": 1.0},
        wall_material_labels={"Floor": "Concrete 150 mm", "Ceiling": "Concrete 150 mm"},
        dose_labels={},
        wall_p_values={"Floor": 10.0, "Ceiling": 10.0},
        risk_map={"Floor": "fail", "Ceiling": "pass"},
    )

    by_label = {call["label"]: call for call in canvas.calls}
    assert by_label["Ceiling"]["status"] == "PASS"
    assert by_label["Floor"]["status"] == "FAIL"


def test_planar_barrier_heading_shows_status_only_when_live_status_exists():
    with_status = _PlanarLabelRecorder()
    GeometryCanvas._draw_planar_barrier_label(
        with_status,
        label="Floor",
        key_options=("Floor",),
        x=10.0,
        y=20.0,
        anchor="e",
        wall_t_values={},
        wall_material_labels={},
        status="PASS",
    )
    assert with_status.text[0] == "Floor | PASS"

    without_status = _PlanarLabelRecorder()
    GeometryCanvas._draw_planar_barrier_label(
        without_status,
        label="Ceiling",
        key_options=("Ceiling",),
        x=10.0,
        y=20.0,
        anchor="w",
        wall_t_values={},
        wall_material_labels={},
        status="",
    )
    assert without_status.text[0] == "Ceiling"


class _WallLabelRecorder:
    def __init__(self):
        self.text = []

    def _append_dose_label_lines(self, lines, dose):
        return GeometryCanvas._append_dose_label_lines(self, lines, dose)

    def create_text(self, x, y, **kwargs):
        self.text.append(kwargs["text"])


def test_cardinal_wall_heading_uses_same_live_status_contract_as_floor_and_ceiling():
    canvas = _WallLabelRecorder()
    GeometryCanvas._draw_wall_labels(
        canvas,
        "N",
        100.0,
        100.0,
        wall_t_values={"N": 0.2},
        wall_material_labels={"N": "Pb 0.88 mm"},
        wall_p_values={"N": 10.0},
        status="FAIL",
    )
    assert canvas.text[0] == "N | FAIL"

    canvas = _WallLabelRecorder()
    GeometryCanvas._draw_wall_labels(
        canvas,
        "E",
        100.0,
        100.0,
        wall_t_values={},
        wall_material_labels={},
        status="PASS",
    )
    assert canvas.text[0] == "E | PASS"


def test_floor_and_ceiling_status_text_can_be_suppressed_for_colour_only_modalities():
    canvas = _FloorCeilingRecorder()

    GeometryCanvas._draw_floor_ceiling_labels(
        canvas,
        field_x0=0.0,
        field_y0=0.0,
        field_w_px=800.0,
        scale=100.0,
        wall_t_values={"Floor": 1.0, "Ceiling": 1.0},
        wall_material_labels={"Floor": "Concrete 150 mm", "Ceiling": "Concrete 150 mm"},
        dose_labels={},
        wall_p_values={"Floor": 10.0, "Ceiling": 10.0},
        risk_map={"Floor": "fail", "Ceiling": "pass"},
        show_status_text=False,
    )

    by_label = {call["label"]: call for call in canvas.calls}
    assert by_label["Ceiling"]["status"] == ""
    assert by_label["Floor"]["status"] == ""
    assert by_label["Ceiling"]["fill"] != by_label["Floor"]["fill"]
