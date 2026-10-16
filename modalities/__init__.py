"""Modality plugin skeleton for RadShield."""

from modalities.base import (
    DeclarativeModalityPlugin,
    ModalityContractError,
    ModalityPlugin,
    ModalitySpec,
    SourceSpec,
    validate_modality_plugin,
)
from modalities.registry import (
    MODALITY_REGISTRY,
    coming_soon_modality_names,
    coming_soon_modalities,
    non_production_plugin_stub_names,
    expected_source_types_for_modality,
    get_modality_spec,
    is_production_modality,
    locked_source_mapping,
    production_modality_names,
    production_modalities,
    registered_modalities,
    require_modality_spec,
)

__all__ = [
    "MODALITY_REGISTRY",
    "DeclarativeModalityPlugin",
    "ModalityContractError",
    "ModalityPlugin",
    "ModalitySpec",
    "SourceSpec",
    "coming_soon_modality_names",
    "coming_soon_modalities",
    "non_production_plugin_stub_names",
    "expected_source_types_for_modality",
    "get_modality_spec",
    "is_production_modality",
    "locked_source_mapping",
    "production_modality_names",
    "production_modalities",
    "registered_modalities",
    "validate_modality_plugin",
    "require_modality_spec",
]
