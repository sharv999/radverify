"""Room modality -> source inventory enforcement helpers."""

from __future__ import annotations

from engine.normalization import normalize_source_params
from modalities.registry import ct_ksec_source_types, sanitize_source_params_for_type
from services.ct_scanner_resolution import repair_ct_family_params_for_source_type


def enforce_room_source_types(app, room) -> None:
    """Hard-lock a room's source inventory to its modality profile.

    This preserves the behaviour formerly implemented on ShieldingDesktopApp
    while keeping source/profile repair logic outside app.py.
    """
    modality = str(getattr(room, "modality", "") or "").strip()
    mapping = app.LOCKED_MODALITY_SOURCES.get(modality)
    if not mapping:
        return

    existing_sources = list(app.get_sources_for_room(room.name))
    existing_sources.extend(list(getattr(room, "sources", []) or []))

    existing_by_type = {str(src.source_type): src for src in existing_sources}
    ct_like_source_types = set(ct_ksec_source_types())
    existing_ct_like = [
        src
        for src in existing_sources
        if str(getattr(src, "source_type", "")) in ct_like_source_types
    ]

    new_sources = []
    used_object_ids = set()

    for source_type, label in mapping:
        src = existing_by_type.get(source_type)

        # Bidirectional migration of stale CT-like source objects.
        # This repairs CT <-> SPECT/CT rooms carrying the wrong CT-like source.
        if src is None and source_type in ct_like_source_types:
            for candidate in existing_ct_like:
                if id(candidate) not in used_object_ids:
                    src = candidate
                    break

        if src is None:
            src = app._default_source_for_type(source_type, label)
        else:
            used_object_ids.add(id(src))
            src.name = label
            src.source_type = source_type
            if not isinstance(src.params, dict):
                src.params = {}

        if source_type in ct_like_source_types:
            saved_scans = None
            saved_mas = None

            if isinstance(src.params, dict):
                saved_scans = src.params.get("scans_per_week")
                saved_mas = src.params.get("workload_mAs_per_scan")

            src.params = normalize_source_params(source_type, src.params)

            if saved_scans not in (None, ""):
                src.params["scans_per_week"] = saved_scans
            if saved_mas not in (None, ""):
                src.params["workload_mAs_per_scan"] = saved_mas

            # Guarantee the resolved family belongs to the correct metadata bucket.
            repaired = repair_ct_family_params_for_source_type(
                app.ct_scanner_resolution_context,
                src.params,
                source_type,
            )
            if repaired.get("scanner_family") != str(src.params.get("scanner_family", "") or "").strip():
                src.params.update(repaired)

            saved_scans = None
            saved_mas = None

            if isinstance(src.params, dict):
                saved_scans = src.params.get("scans_per_week")
                saved_mas = src.params.get("workload_mAs_per_scan")

            src.params = normalize_source_params(source_type, src.params)

            if saved_scans not in (None, ""):
                src.params["scans_per_week"] = saved_scans
            if saved_mas not in (None, ""):
                src.params["workload_mAs_per_scan"] = saved_mas

        src.params = sanitize_source_params_for_type(source_type, src.params)

        src.radiation_type = app._safe_auto_select_tvl_key(
            source_type,
            src.params,
            getattr(src, "radiation_type", ""),
        )
        new_sources.append(src)

    if not hasattr(app.project, "sources") or app.project.sources is None:
        app.project.sources = []

    # Remove existing project-level sources for this room.
    app.project.sources = [
        s
        for s in app.project.sources
        if str(getattr(s, "room_name", "")).strip() != room.name
    ]

    for src in new_sources:
        src.room_name = room.name
        app.project.sources.append(src)

    room.sources = list(new_sources)
