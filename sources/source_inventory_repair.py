from __future__ import annotations

from modalities.registry import (
    default_source_type_for_modality,
    source_type_options,
)


def repair_invalid_source_inventory(app) -> None:
    """
    Ensure all sources are valid for the reduced-modality app:
    CT, SPECT/CT, X-ray only.
    """
    for room in getattr(app.project, "rooms", []) or []:
        # Enforce correct sources per modality
        app.enforce_room_source_types(room)

        for src in getattr(room, "sources", []) or []:
            if not isinstance(src.params, dict):
                src.params = {}

            # Only keep source types registered for current or future modalities.
            if src.source_type not in set(source_type_options(production_only=False)):
                # Replace with a safe default for the actual room modality.
                replacement_type = default_source_type_for_modality(room.modality) or "ct_scatter"
                new_src = app._default_source_for_type(replacement_type, src.name)
                src.source_type = new_src.source_type
                src.params = new_src.params
