from pathlib import Path

import pytest

from reports.report_generator import _RoomLayoutFlowable


def test_desktop_geometry_canvas_uses_12x8_field_and_ffl_fcl_label():
    text = (Path(__file__).resolve().parents[1] / "geometry" / "geometry_canvas.py").read_text(encoding="utf-8")
    assert "DESIGN_FIELD_WIDTH_M = 12.0" in text
    assert "DESIGN_FIELD_HEIGHT_M = 8.0" in text
    assert 'text=f"FFL to FCL: {height:.2f} m"' in text
    assert "field_x0 + field_w_px - (scale_metres * scale)" in text
    assert 'text="Scale: 1 m"' in text

    symbol_text = (Path(__file__).resolve().parents[1] / "geometry" / "canvas_symbols.py").read_text(encoding="utf-8")
    assert "dash=(7, 5)" in symbol_text


def test_pdf_geometry_uses_same_12x8_field_and_patient_annotations():
    room = {
        "geometry": {
            "width_m": 5.0,
            "length_m": 6.0,
            "height_m": 3.6,
            "source": {"label": "SPECT Patient Source", "x_m": 2.5, "y_m": 3.0, "rotation_deg": 0},
            "rendering": {"patient_marker_label": ""},
        },
        "pet_spect_report_route": {
            "payload": {
                "source_summary": {
                    "radionuclide": "Tc99m",
                    "administered_activity_mbq": 740.0,
                }
            }
        },
        "barriers": [
            {
                "distance_m": 3.0,
                "unshielded_weekly_dose_uSv": 32.91680993284247,
                "barrier_transmission_factor_B": 0.6075922922301522,
            }
        ],
    }
    flowable = _RoomLayoutFlowable(room, width=500, height=330)
    flowable._configure_geometry(5.0, 6.0)

    assert flowable.DESIGN_FIELD_WIDTH_M == 12.0
    assert flowable.DESIGN_FIELD_HEIGHT_M == 8.0
    assert flowable._patient_source_label({}) == "Tc-99m 740 MBq"
    assert flowable._patient_weekly_one_m_label() == "296.25 µSv/wk @ 1 m"
    assert flowable._dose_label(room["barriers"][0]).endswith("B=0.607592")

    report_text = (Path(__file__).resolve().parents[1] / "reports" / "report_generator.py").read_text(encoding="utf-8")
    assert '"Scale: 1 m"' in report_text
    assert "dash=(4.0, 3.0)" in report_text
    assert '_RoomLayoutFlowable(room, width=220 * mm, height=132 * mm),' in report_text
    assert 'self.hAlign = "CENTER"' in report_text
    assert '("N", cx, self._room_y0 - 5, "s")' in report_text
    assert '("S", cx, self._room_y1 + 5, "n")' in report_text

    field_w = flowable.DESIGN_FIELD_WIDTH_M * flowable._scale
    field_h = flowable.DESIGN_FIELD_HEIGHT_M * flowable._scale
    room_cx = (flowable._room_x0 + flowable._room_x1) / 2
    room_cy = (flowable._room_y0 + flowable._room_y1) / 2
    field_cx = flowable._field_x0 + field_w / 2
    field_cy = flowable._field_y0 + field_h / 2
    assert room_cx == pytest.approx(field_cx)
    assert room_cy == pytest.approx(field_cy)
