from pathlib import Path


def test_geometry_canvas_derives_one_m_label_from_source_without_ksec_label_argument():
    text = Path("geometry/geometry_canvas.py").read_text(encoding="utf-8")

    assert "if ksec_label:\n            try:" not in text
    assert "ksec > 0 and scans > 0 and workload > 0" in text
    assert 'one_m_label = f"{weekly_scatter_uSv:.0f} µSv/wk @ 1 m"' in text
    assert "marker_points.reference_circle" in text
    assert "reference_circle_radius_m" in text
    assert "reference_circle_label_gap_px" in text


def test_canvas_one_m_circle_label_gap_is_descriptor_driven():
    symbols_text = Path("geometry/canvas_symbols.py").read_text(encoding="utf-8")
    canvas_text = Path("geometry/geometry_canvas.py").read_text(encoding="utf-8")

    assert "cy - r - float(label_gap_px)" in symbols_text
    assert 'anchor="center"' in symbols_text
    assert 'rendering.get("reference_circle_label_gap_px", 10.0)' in canvas_text
