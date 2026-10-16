from pathlib import Path

from modalities.registry import layout_rendering_for_modality
from reports.results_payload_builder import _room_geometry_dict
from geometry.geometry_model import RoomGeometry


def test_ct_plugin_owns_layout_symbol_dimensions_and_annotation():
    spec = layout_rendering_for_modality("CT")
    assert spec.source_symbol_kind == "ct_scanner"
    assert spec.equipment_width_m > 0
    assert spec.equipment_depth_m > 0
    assert spec.table_width_m > 0
    assert spec.table_length_m > 0
    assert spec.annotation_kind == "ct_weekly_scatter"


def test_layout_payload_carries_plugin_owned_rendering_metadata():
    payload = _room_geometry_dict(RoomGeometry(), "CT")
    rendering = payload["rendering"]
    assert rendering["source_symbol_kind"] == "ct_scanner"
    assert rendering["equipment_width_m"] > 0
    assert rendering["annotation_kind"] == "ct_weekly_scatter"


def test_renderers_do_not_infer_modality_from_source_label_or_import_ct_dimensions():
    canvas_text = Path("geometry/geometry_canvas.py").read_text(encoding="utf-8")
    pdf_text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    scanner_text = Path("geometry/scanner_renderer.py").read_text(encoding="utf-8")

    assert '"x-ray" in source_lc' not in canvas_text
    assert '"spect" in source_lc' not in canvas_text
    assert "CT_GANTRY_WIDTH_M" not in pdf_text
    assert "CT_TABLE_LENGTH_M" not in pdf_text
    assert "CT_GANTRY_WIDTH_M" not in scanner_text
    assert "CT_TABLE_LENGTH_M" not in scanner_text


def test_production_modalities_use_colour_only_barrier_status_presentation():
    assert layout_rendering_for_modality("PET").show_barrier_status_text is False
    assert layout_rendering_for_modality("SPECT").show_barrier_status_text is False
    assert layout_rendering_for_modality("CT").show_barrier_status_text is False
