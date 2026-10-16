from pathlib import Path


def test_pet_preview_error_path_initialises_room_before_validation():
    text = Path("tabs/pet_preview_panel.py").read_text(encoding="utf-8")
    marker = 'def update_pet_preview(app, *_args) -> None:'
    block = text[text.index(marker):text.index('\n\ndef _update_pet_room_mode_fields', text.index(marker))]
    assert 'room = None\n    try:' in block
    assert 'refresh_pet_barrier_results_preview(app, room=room)' in block


def test_pet_canvas_preview_marker_uses_canonical_geometry_source_position():
    text = Path("geometry/pet_preview_overlay.py").read_text(encoding="utf-8")
    assert 'source = getattr(geom, "source", None)' in text
    assert 'sx_m = float(getattr(source, "x_m"' in text
    assert 'sy_m = float(getattr(source, "y_m"' in text
