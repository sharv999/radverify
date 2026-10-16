from geometry.source_marker_layout import resolve_source_marker_points

from modalities.registry import layout_rendering_for_modality





def test_pet_and_spect_marker_descriptor_resolves_all_anchors_to_canonical_source():

    for modality in ("PET", "SPECT"):

        rendering = layout_rendering_for_modality(modality).as_dict()

        points = resolve_source_marker_points(100.0, 200.0, 80.0, 0.0, rendering)



        assert points.source == (100.0, 200.0)

        assert points.radiation == points.source

        assert points.patient == points.source

        assert points.reference_circle == points.source

        assert rendering["reference_circle_anchor"] == "source"

        assert rendering["reference_circle_radius_m"] == 1.0

        assert rendering["patient_label_offset_px"] == 42.0

        assert rendering["patient_marker_label"] == ""

        assert rendering["reference_circle_label_gap_px"] == 10.0

        assert rendering["preview_source_label_gap_px"] == 6.0





def test_hybrid_patient_offset_no_longer_implicitly_moves_reference_circle():

    rendering = layout_rendering_for_modality("SPECT/CT").as_dict()

    points = resolve_source_marker_points(100.0, 200.0, 80.0, 0.0, rendering)



    assert points.patient == (140.0, 200.0)

    assert points.reference_circle == points.source == (100.0, 200.0)





def test_reference_circle_anchor_can_explicitly_follow_patient_when_requested():

    rendering = {

        "patient_symbol_offset_m": 0.5,

        "reference_circle_anchor": "patient",

    }

    points = resolve_source_marker_points(100.0, 200.0, 80.0, 90.0, rendering)



    assert points.patient[0] == 100.0

    assert points.patient[1] == 240.0

    assert points.reference_circle == points.patient



def test_pet_and_spect_live_geometry_params_are_plugin_owned():
    from modalities.registry import get_modality_plugin

    for modality in ("PET", "SPECT"):
        plugin = get_modality_plugin(modality)
        assert plugin is not None
        assert callable(plugin.spec.geometry_live_source_params_builder)
