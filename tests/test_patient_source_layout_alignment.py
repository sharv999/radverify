from geometry.canvas_symbols import nm_patient_point
from geometry.geometry_canvas import _format_isotope_label, _resolve_patient_canvas_label

from modalities.registry import layout_rendering_for_modality





def test_spect_patient_source_symbol_is_coincident_with_canonical_source_point():

    rendering = layout_rendering_for_modality("SPECT")



    assert rendering.show_patient_symbol is True

    assert rendering.patient_symbol_offset_m == 0.0

    assert rendering.patient_marker_label == ""

    assert nm_patient_point(100.0, 200.0, 80.0, offset_m=rendering.patient_symbol_offset_m) == (100.0, 200.0)





def test_pet_patient_source_symbol_is_coincident_with_canonical_source_point():

    rendering = layout_rendering_for_modality("PET")



    assert rendering.show_patient_symbol is True

    assert rendering.patient_symbol_offset_m == 0.0

    assert rendering.patient_marker_label == ""

    assert nm_patient_point(100.0, 200.0, 80.0, offset_m=rendering.patient_symbol_offset_m) == (100.0, 200.0)





def test_legacy_patient_offset_remains_available_for_hybrid_layouts():

    x, y = nm_patient_point(100.0, 200.0, 80.0, scanner_rotation_deg=0.0)



    assert x == 140.0

    assert y == 200.0



def test_patient_canvas_label_uses_isotope_and_activity_when_present():
    label = _resolve_patient_canvas_label(
        {"patient_marker_label": "PET"},
        {"radionuclide": "F18", "injected_activity_mbq": 250},
    )

    assert label == "F-18 250 MBq"


def test_isotope_formatter_normalises_common_codes():
    assert _format_isotope_label("Tc99m") == "Tc-99m"
    assert _format_isotope_label("Ga68") == "Ga-68"


def test_geometry_source_sync_uses_plugin_owned_live_marker_metadata():
    from pathlib import Path

    source_sync = Path("geometry/source_sync.py").read_text(encoding="utf-8")
    pet_text = Path("modalities/pet.py").read_text(encoding="utf-8")
    spect_text = Path("modalities/spect.py").read_text(encoding="utf-8")

    assert "plugin.geometry_live_source_params(room)" in source_sync
    assert "get_room_pet_working_state(room)" in pet_text
    assert "get_room_spect_working_state(room)" in spect_text
    assert '"injected_activity_mbq": float(state.source.injected_activity_mbq)' in pet_text
    assert '"administered_activity_mbq": float(state.source.administered_activity_mbq)' in spect_text
    assert '"live_source_params": live_source_params' in source_sync
