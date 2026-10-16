from __future__ import annotations

from engine.normalization import normalize_source_params
from modalities.registry import sanitize_source_params_for_type, source_form_kind_for_type
from tabs.source_ct_audit import load_ct_audit_vars_from_params


def reload_source_ui_from_model(
    app,
    room=None,
    source_index: int | None = None,
    refresh_live: bool = True,
) -> None:
    """Reload the Sources tab form from the selected project source model."""
    if not hasattr(app, "sources_list"):
        return

    if room is None:
        room = app.get_room_by_name(app.sources_room_var.get())

    if not room:
        return

    app.enforce_room_source_types(room)
    app._configure_source_type_combo_for_room(room)

    room_sources = app.get_sources_for_room(room.name)

    if source_index is None:
        source_index = app.current_source_index

    if source_index is None:
        source_index = app.get_selected_source_index()

    if source_index is None or source_index < 0 or source_index >= len(room_sources):
        source_index = 0 if room_sources else None

    if source_index is None:
        app.clear_source_form()
        return

    src = room_sources[source_index]

    src.room_name = room.name
    src.name = app._canonical_source_name_for_type(src.source_type)

    if not isinstance(src.params, dict):
        src.params = {}

    src.params = sanitize_source_params_for_type(src.source_type, src.params)
    if source_form_kind_for_type(src.source_type) == "ct_ksec":
        src.params = normalize_source_params(src.source_type, src.params)

    src.radiation_type = app._safe_auto_select_tvl_key(
        src.source_type,
        src.params,
        getattr(src, "radiation_type", ""),
    )

    app.current_source_index = source_index
    app.last_selected_source_index = source_index
    app.last_selected_source_room_name = room.name

    app._loading_source_form = True
    try:
        app.source_name_var.set(src.name)
        app.source_type_var.set(src.source_type)
        app.radiation_type_var.set(src.radiation_type)

        app.refresh_source_form_by_type()
        app.load_source_params_into_form(src)
        if source_form_kind_for_type(src.source_type) == "ct_ksec":
            load_ct_audit_vars_from_params(app, getattr(src, "params", {}) or {})
        app.update_auto_tvl_key_display()

        try:
            app.sources_list.selection_clear(0, "end")
            app.sources_list.selection_set(source_index)
            app.sources_list.activate(source_index)
        except Exception:
            pass

        app._source_dirty = False
    finally:
        app._loading_source_form = False

    app._update_sources_readonly_state()

    if refresh_live:
        app.update_live_source_preview_from_form()
