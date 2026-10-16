from pathlib import Path


def test_geometry_canvas_includes_status_legend():
    text = (Path(__file__).resolve().parents[1] / "geometry" / "geometry_canvas.py").read_text(encoding="utf-8")
    assert 'text="Legend"' in text
    assert '("PASS", COLOUR_PASS)' in text
    assert '("REVIEW", COLOUR_REVIEW_DARK)' in text
    assert '("FAIL", COLOUR_FAIL)' in text
    assert 'scale_y - 55' in text


def test_pdf_barrier_plan_includes_status_legend():
    text = (Path(__file__).resolve().parents[1] / "reports" / "report_generator.py").read_text(encoding="utf-8")
    assert 'self._draw_status_legend()' in text
    assert '"Legend"' in text
    assert '("PASS", COLOUR_PASS)' in text
    assert '("REVIEW", COLOUR_REVIEW_DARK)' in text
    assert '("FAIL", COLOUR_FAIL)' in text
    assert 'y = scale_y - (12 * mm)' in text
