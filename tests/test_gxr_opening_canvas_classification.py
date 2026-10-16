from pathlib import Path


def test_opening_overlay_classification_uses_live_result_path():
    text = Path("tabs/results_barrier_maps.py").read_text(encoding="utf-8")
    assert 'label = "SECONDARY\\n" + label' in text
    assert 'live.get("radiation_classification", "")' in text
    assert 'dose_map[name] = label' in text


def test_canvas_keeps_opening_id_and_appends_live_overlay():
    text = Path("geometry/geometry_canvas.py").read_text(encoding="utf-8")
    assert 'lines = [label]' in text
    assert 'self._append_dose_label_lines(lines, dose)' in text
