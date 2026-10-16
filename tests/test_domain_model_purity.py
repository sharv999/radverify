from dataclasses import fields

from geometry.geometry_model import RadiationSourceGeometry
from models.shielding_models import Barrier, Project, Room, Source


MODALITY_FIELD_NAMES = {
    "scanner_vendor",
    "scanner_model",
    "scanner_family",
    "scanner_kvp",
    "ksec_mgy_per_100mas_at_1m",
    "workload_mas_per_scan",
    "radionuclide",
    "activity_mbq",
    "administered_activity_mbq",
}
MODALITY_FIELD_PREFIXES = ("ct_", "pet_", "spect_", "xray_", "x_ray_")


def _assert_no_modality_fields(model_type) -> None:
    field_names = {field.name.lower() for field in fields(model_type)}
    leaked = {
        name
        for name in field_names
        if name in MODALITY_FIELD_NAMES or name.startswith(MODALITY_FIELD_PREFIXES)
    }
    assert leaked == set(), f"{model_type.__name__} contains modality-owned fields: {sorted(leaked)}"


def test_shared_project_room_barrier_models_have_no_modality_owned_fields():
    # ``modality`` and ``source_type`` are generic routing identifiers.  The
    # actual modality values belong in Source.params / plugin-owned metadata.
    for model_type in (Project, Room, Barrier):
        _assert_no_modality_fields(model_type)


def test_source_keeps_modality_specific_values_in_params():
    _assert_no_modality_fields(Source)
    source = Source(
        source_type="ct_scatter",
        params={
            "scanner_model": "Example CT",
            "ksec_mGy_per_100mAs_at_1m": 0.005,
            "radionuclide": "F-18",
            "activity_mbq": 250.0,
        },
    )

    assert source.params["scanner_model"] == "Example CT"
    assert source.params["radionuclide"] == "F-18"
    assert not hasattr(source, "scanner_model")
    assert not hasattr(source, "radionuclide")


def test_geometry_render_metadata_is_generic_transient_and_not_serialized():
    geometry_source = RadiationSourceGeometry()
    geometry_source.render_metadata.update(
        {
            "scanner_model": "Example CT",
            "ksec_mGy_per_100mAs_at_1m": 0.005,
        }
    )

    serialized = geometry_source.to_dict()

    assert "render_metadata" not in serialized
    assert "scanner_model" not in serialized
    assert "ksec_mGy_per_100mAs_at_1m" not in serialized
    assert not hasattr(geometry_source, "scanner_model")
    assert not hasattr(geometry_source, "ksec_mGy_per_100mAs_at_1m")
