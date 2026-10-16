from __future__ import annotations

from modalities.registry import geometry_ui_for_modality
from typing import Optional

from tkinter import messagebox

from models.shielding_models import Source
from engine.normalization import normalize_source_params
from engine.shielding_engine import auto_select_tvl_key

from services.ct_scanner_resolution import (
    central_ct_ksec_resolver,
    ct_model_values_for_source_type,
    ct_vendor_values_for_source_type,
    resolve_family_selection,
)
from geometry.barrier_sync import safe_refresh_barrier_schedule
from tabs.source_ct_audit import inject_ct_audit_params
from tabs.source_ct_state import populate_ct_model_combo_values
from modalities.registry import (
    ct_ksec_source_types,
    default_source_params_for_type,
    finalise_source_form_params_for_type,
    source_form_kind_for_type,
    source_type_options,
)


def update_ct_scatter_resolution_label(app, source_type: Optional[str] = None):
    if not hasattr(app, "ct_resolved_family_var"):
        return
    source_type = str(source_type or app.source_type_var.get().strip() or "ct_scatter")
    selection = resolve_family_selection(
        app.ct_scanner_resolution_context,
        source_type=source_type,
        vendor=app.ct_vars["scanner_vendor"].get(),
        model=app.ct_vars["scanner_model"].get(),
    )
    app.ct_vars["scanner_family"].set(selection.scanner_family)
    if selection.scanner_family and not app.ct_vars["scanner_phantom"].get().strip():
        app.ct_vars["scanner_phantom"].set(selection.scanner_phantom)
    app.ct_resolved_family_var.set(selection.display_text)


def ct_vendor_values(app, source_type: Optional[str] = None):
    stype = source_type or app.source_type_var.get().strip()

    # Prefer the JSON scatter database because it now carries the authoritative
    # metadata taxonomy used for UI filtering.
    values = ct_vendor_values_for_source_type(app.ct_scanner_resolution_context, stype)
    if values:
        return values

    return []


def populate_ct_vendor_combo_values(app, source_type: Optional[str] = None):
    if not hasattr(app, "ct_vendor_combo"):
        return

    values = ct_vendor_values(app, source_type or app.source_type_var.get().strip())

    try:
        if app.ct_vendor_combo.winfo_exists():
            app.ct_vendor_combo["values"] = values
    except Exception:
        return

    current = str(app.ct_vars["scanner_vendor"].get()).strip()
    if values and current not in values:
        app.ct_vars["scanner_vendor"].set(values[0])


def on_ct_vendor_change(app, event=None):
    if getattr(app, "_loading_source_form", False):
        return
    source_type = app.source_type_var.get().strip() or "ct_scatter"
    populate_ct_model_combo_values(app, source_type=source_type)
    selection = resolve_family_selection(
        app.ct_scanner_resolution_context,
        source_type=source_type,
        vendor=app.ct_vars["scanner_vendor"].get(),
        model=app.ct_vars["scanner_model"].get(),
    )
    app.ct_vars["scanner_family"].set(selection.scanner_family)
    app.ct_vars["scanner_phantom"].set(selection.scanner_phantom)
    update_ct_source_ksec_from_selector(app, source_type=source_type)
    app.on_source_input_change()


def on_ct_kvp_change(app, *args):
    if getattr(app, "_loading_source_form", False):
        return
    source_type = app.source_type_var.get().strip() or "ct_scatter"
    update_ct_source_ksec_from_selector(app, source_type=source_type)
    app.on_source_input_change()


def on_ct_model_change(app, event=None):
    if getattr(app, "_loading_source_form", False):
        return
    source_type = app.source_type_var.get().strip() or "ct_scatter"
    selection = resolve_family_selection(
        app.ct_scanner_resolution_context,
        source_type=source_type,
        vendor=app.ct_vars["scanner_vendor"].get(),
        model=app.ct_vars["scanner_model"].get(),
    )
    app.ct_vars["scanner_family"].set(selection.scanner_family)
    app.ct_vars["scanner_phantom"].set(selection.scanner_phantom)
    update_ct_source_ksec_from_selector(app, source_type=source_type)
    app.on_source_input_change()


def ct_form_energy_to_kvp(app) -> int:
    """Return selected CT kVp from the source form, defaulting safely to 140."""
    ct_vars = getattr(app, "ct_vars", {}) or {}
    kvp_var = ct_vars.get("scanner_kvp")

    try:
        raw = kvp_var.get() if kvp_var is not None else "140"
        return int(float(str(raw).strip()))
    except Exception:
        return 140


def update_ct_source_ksec_from_selector(app, force: bool = False, source_type: Optional[str] = None):
    if not hasattr(app, "ct_vars"):
        return None

    use_auto = str(app.ct_vars["use_scanner_db"].get()).strip() == "1"
    manual_override = str(app.ct_vars["manual_ksec_override"].get()).strip() == "1"

    if not use_auto and not force:
        return None
    if manual_override and not force:
        return None

    # Public database-ksec boundary is services.ct_ksec_resolver.resolve_database_ct_ksec(...).
    resolution = central_ct_ksec_resolver(
        app.ct_scanner_resolution_context,
        source_type=source_type or app.source_type_var.get().strip(),
        vendor=app.ct_vars["scanner_vendor"].get(),
        model=app.ct_vars["scanner_model"].get(),
        kvp=ct_form_energy_to_kvp(app),
    )

    app.ct_vars["scanner_family"].set(resolution.scanner_family)
    app.ct_vars["scanner_phantom"].set(resolution.phantom)
    app.ct_vars["manual_ksec_override"].set("0")
    app.ct_vars["manual_ksec_entered_by"].set("")
    app.ct_vars["manual_ksec_reason"].set("")
    app.ct_vars["manual_ksec_reference"].set("")
    app.ct_vars["manual_ksec_last_updated"].set("")
    app.ct_vars["scanner_source"].set(resolution.scanner_source)
    app.ct_vars["scanner_debug"].set(resolution.scanner_debug)

    if resolution.requires_manual_override or resolution.ksec_mGy_per_100mAs_at_1m is None:
        # Keep the scanner selected, but clear ksec so downstream code cannot
        # accidentally use the old value or a conservative default.
        app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set("")
        return None

    ksec = float(resolution.ksec_mGy_per_100mAs_at_1m)
    app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set(f"{ksec:.6g}")
    return ksec


def on_source_type_change(app):
    if getattr(app, "_loading_source_form", False):
        return
    room = app.get_room_by_name(app.sources_room_var.get())
    if app._room_sources_are_locked(room):
        app.load_selected_source()
        return
    app.save_current_source_form_draft()
    stype = app.source_type_var.get().strip() or "manual"

    allowed_source_types = set(app._allowed_source_types_for_room(room))
    if stype not in allowed_source_types:
        fallback = next(iter(app._allowed_source_types_for_room(room)), "ct_scatter")
        app.source_type_var.set(fallback)
        stype = fallback

    app._loading_source_form = True
    try:
        app.refresh_source_form_by_type()
        app.load_source_form_draft(stype)
        app.update_auto_tvl_key_display()
    finally:
        app._loading_source_form = False
    app._source_dirty = True
    if stype in set(ct_ksec_source_types()):
        app.refresh_selected_source_resolution(force=True, source_type=stype)
    app.update_live_source_preview_from_form()
    app._update_sources_readonly_state()


# Remaining source-tab list/form/model actions extracted from app.py.
def refresh_sources_list(app, preserve_index: Optional[int] = None):
    app._repair_invalid_source_inventory()

    if not hasattr(app, "sources_list"):
        return

    room_name = app.sources_room_var.get().strip()
    room = app.get_room_by_name(room_name)

    app.sources_list.delete(0, "end")

    if not room:
        app.refresh_source_calculations()
        return

    app.enforce_room_source_types(room)
    app._configure_source_type_combo_for_room(room)

    room_sources = app.get_sources_for_room(room.name)

    # Safety migration: if old room.sources still has sources, move them to project.sources
    if not room_sources and getattr(room, "sources", None):
        if not hasattr(app.project, "sources") or app.project.sources is None:
            app.project.sources = []

        for src in getattr(room, "sources", []) or []:
            src.room_name = room.name
            app.project.sources.append(src)

        room.sources = []
        room_sources = app.get_sources_for_room(room.name)

    for src in room_sources:
        src.name = app._canonical_source_name_for_type(src.source_type)
        app.sources_list.insert("end", src.name)

    if preserve_index is None:
        preserve_index = app.current_source_index

    if preserve_index is not None and 0 <= preserve_index < len(room_sources):
        app.sources_list.selection_clear(0, "end")
        app.sources_list.selection_set(preserve_index)
        app.sources_list.activate(preserve_index)
        app.current_source_index = preserve_index
    elif room_sources:
        app.sources_list.selection_clear(0, "end")
        app.sources_list.selection_set(0)
        app.sources_list.activate(0)
        app.current_source_index = 0
    else:
        app.current_source_index = None

    app.refresh_source_calculations()
    app._update_sources_readonly_state()

def get_selected_source_index(app) -> Optional[int]:
    sel = app.sources_list.curselection()
    if sel:
        return sel[0]

    room = app.get_room_by_name(app.sources_room_var.get())
    if not room:
        return None

    room_sources = app.get_sources_for_room(room.name)

    if (
        app.current_source_index is not None
        and 0 <= app.current_source_index < len(room_sources)
    ):
        return app.current_source_index

    return None

def on_sources_room_change(app):
    room = app.get_room_by_name(app.sources_room_var.get())

    if room:
        app.enforce_room_source_types(room)

    room_sources = app.get_sources_for_room(room.name) if room else []

    app.last_selected_source_index = None
    app.last_selected_source_room_name = None
    app.current_source_index = 0 if room_sources else None
    app._source_dirty = False

    app.refresh_sources_list(preserve_index=app.current_source_index)

    if room and room_sources:
        app._reload_source_ui_from_model(room, app.current_source_index, refresh_live=True)
    else:
        app.clear_source_form()
        app.update_live_source_preview_from_form()
        safe_refresh_barrier_schedule(app)

    app._update_sources_readonly_state()
    try:
        from tabs.pet_preview_panel import load_pet_working_state_into_preview, update_pet_preview
        load_pet_working_state_into_preview(app, room)
        update_pet_preview(app)
    except Exception:
        pass
    try:
        from tabs.spect_preview_panel import (
            load_spect_working_state_into_preview,
            refresh_spect_preview,
        )
        load_spect_working_state_into_preview(app, room)
        refresh_spect_preview(app, room)
    except Exception:
        pass

def clear_source_form(app):
    app._loading_source_form = True
    try:
        app.source_name_var.set("")
        room = app.get_room_by_name(app.sources_room_var.get()) if hasattr(app, "sources_room_var") else None
        app.source_type_var.set(app._primary_scatter_source_type_for_room(room))
        app.radiation_type_var.set("")
        app._configure_source_type_combo_for_room(room)
        app.refresh_source_form_by_type()
        app._source_dirty = False
    finally:
        app._loading_source_form = False
    app._update_sources_readonly_state()

def on_source_form_change(app, *args):
    if getattr(app, "_loading_source_form", False):
        return
    if not hasattr(app, "sources_list"):
        return

    room = app.get_room_by_name(app.sources_room_var.get())
    if app._room_sources_are_locked(room):
        # Locked modality sources are model-driven. Do not let stale UI StringVars
        # rewrite the source type or name.
        app._reload_source_ui_from_model(room, app.current_source_index, refresh_live=True)
        return

    idx = app.current_source_index
    room_sources = app.get_sources_for_room(room.name) if room else []

    if room and idx is not None and 0 <= idx < len(room_sources):
        src = room_sources[idx]
        new_name = app.source_name_var.get().strip() or src.name
        src.name = new_name

        app.sources_list.delete(idx)
        app.sources_list.insert(idx, new_name)
        app.sources_list.selection_clear(0, "end")
        app.sources_list.selection_set(idx)
        app.sources_list.activate(idx)

def persist_previous_selected_source(app):
    room_name = str(app.last_selected_source_room_name or "").strip()
    idx = app.last_selected_source_index

    if not room_name or idx is None:
        return

    room = app.get_room_by_name(room_name)
    if not room:
        return

    room_sources = app.get_sources_for_room(room.name)

    if idx < 0 or idx >= len(room_sources):
        return

    if app._room_sources_are_locked(room):
        app.enforce_room_source_types(room)
        return

    try:
        src = room_sources[idx]
        current_stype = app.source_type_var.get().strip() or src.source_type

        src.room_name = room.name
        src.name = app.source_name_var.get().strip() or src.name
        src.source_type = current_stype
        src.params = app.collect_source_params_from_form(current_stype)
        src.radiation_type = app._safe_auto_select_tvl_key(
            current_stype,
            src.params,
            app.radiation_type_var.get().strip(),
        )
    except Exception:
        pass

def load_selected_source(app):
    room = app.get_room_by_name(app.sources_room_var.get())

    if not room:
        app.clear_source_form()
        return

    app.enforce_room_source_types(room)

    room_sources = app.get_sources_for_room(room.name)

    if not room_sources:
        app.clear_source_form()
        return

    selection = app.sources_list.curselection()

    if selection:
        idx = selection[0]
    else:
        idx = app.current_source_index if app.current_source_index is not None else 0

    if idx < 0 or idx >= len(room_sources):
        app.clear_source_form()
        return

    app._reload_source_ui_from_model(room, idx, refresh_live=True)

def add_source(app):
    room = app.get_room_by_name(app.sources_room_var.get())
    if not room:
        messagebox.showwarning("No room", "Create or select a room first.")
        return

    if app._room_sources_are_locked(room):
        app.set_status("Sources are locked to room modality.")
        return

    if not hasattr(app.project, "sources") or app.project.sources is None:
        app.project.sources = []

    room_sources = app.get_sources_for_room(room.name)

    src = Source(
        name=f"Source {len(room_sources) + 1}",
        source_type="manual",
        radiation_type=auto_select_tvl_key(
            "manual",
            {"dose_rate_uSv_h_at_1m": 100, "hours_per_week": 1},
            "xray_120kvp",
        ),
        params={"dose_rate_uSv_h_at_1m": 100, "hours_per_week": 1},
    )
    src.room_name = room.name

    app.project.sources.append(src)

    new_idx = len(room_sources)
    app.current_source_index = new_idx
    app.last_selected_source_index = new_idx
    app.last_selected_source_room_name = room.name

    app.refresh_sources_list(preserve_index=new_idx)
    app.load_selected_source()
    app._source_dirty = False
    app.refresh_source_calculations()

def delete_source(app):
    room = app.get_room_by_name(app.sources_room_var.get())

    if app._room_sources_are_locked(room):
        app.set_status("Sources are locked to room modality.")
        return

    idx = app.current_source_index
    if idx is None:
        idx = app.get_selected_source_index()

    if not room:
        return

    room_sources = app.get_sources_for_room(room.name)

    if idx is None or idx < 0 or idx >= len(room_sources):
        return

    src_to_delete = room_sources[idx]

    app._loading_source_form = True
    try:
        app.project.sources = [
            s for s in app.project.sources
            if s is not src_to_delete
        ]

        app.last_selected_source_index = None
        app.last_selected_source_room_name = None

        remaining = app.get_sources_for_room(room.name)

        if remaining:
            next_idx = min(idx, len(remaining) - 1)
            app.current_source_index = next_idx
            app.refresh_sources_list(preserve_index=next_idx)
        else:
            app.current_source_index = None
            app.refresh_sources_list()
            app.clear_source_form()
    finally:
        app._loading_source_form = False

    if app.get_sources_for_room(room.name) and app.current_source_index is not None:
        app.sources_list.selection_clear(0, "end")
        app.sources_list.selection_set(app.current_source_index)
        app.sources_list.activate(app.current_source_index)
        app.load_selected_source()
    else:
        app.update_live_source_preview_from_form()

    app.refresh_source_calculations()
    safe_refresh_barrier_schedule(app)

def update_source_options(app):
    modality_id = str(app.source_type_var.get() or "").strip()
    geometry_ui = geometry_ui_for_modality(modality_id)
    options = list(geometry_ui.static_options)
    app.source_option_combo["values"] = options
    if options:
        app.source_option_var.set(options[0])

def sync_current_source_to_model(app, ignore_errors: bool = False):
    room = app.get_room_by_name(app.sources_room_var.get())

    if not room:
        return False

    idx = app.current_source_index

    if idx is None:
        idx = app.get_selected_source_index()

    room_sources = app.get_sources_for_room(room.name)

    if idx is None or idx < 0 or idx >= len(room_sources):
        return False

    try:
        app.enforce_room_source_types(room)

        room_sources = app.get_sources_for_room(room.name)

        if idx < 0 or idx >= len(room_sources):
            return False

        src = room_sources[idx]
        src.room_name = room.name

        if app._room_sources_are_locked(room):
            src.name = app._canonical_source_name_for_type(src.source_type)
        else:
            src.name = app.source_name_var.get().strip() or src.name
            src.source_type = app.source_type_var.get().strip() or src.source_type

        collected = app.collect_source_params_from_form(src.source_type)
        if collected is None:
            collected = getattr(src, "params", {}) or {}
        src.params = finalise_source_form_params_for_type(
            app,
            src.source_type,
            collected,
        )

        src.radiation_type = app._safe_auto_select_tvl_key(
            src.source_type,
            src.params,
            app.radiation_type_var.get().strip(),
        )

        app.radiation_type_var.set(src.radiation_type)

        app.current_source_index = idx
        app.last_selected_source_index = idx
        app.last_selected_source_room_name = room.name
        app._source_dirty = False

        return True

    except Exception:
        if ignore_errors:
            return False
        raise

def apply_source_form(app):
    app._suppress_geometry_source_sync = True

    try:
        app._repair_invalid_source_inventory()

        room = app.get_room_by_name(app.sources_room_var.get())
        if not room:
            return

        src = app._get_current_source()
        if not src:
            return

        if not isinstance(src.params, dict):
            src.params = {}

        collected = app.collect_source_params_from_form(src.source_type)
        if collected is None:
            collected = src.params
        src.params = finalise_source_form_params_for_type(
            app,
            src.source_type,
            collected,
        )

        src.radiation_type = app._safe_auto_select_tvl_key(
            src.source_type,
            src.params,
            app.radiation_type_var.get().strip(),
        )
        app.radiation_type_var.set(src.radiation_type)

        idx = app.current_source_index
        if idx is None:
            idx = app.get_selected_source_index()
        if idx is None:
            idx = 0

        app._source_dirty = False
        app.optimizer_last_recommendations = []

        app.refresh_sources_list(preserve_index=idx)
        app._reload_source_ui_from_model(room, idx, refresh_live=True)
        safe_refresh_barrier_schedule(app)
        app.refresh_results_tab()

        try:
            if hasattr(app, "geometry_tab"):
                app.geometry_tab.draw_room_with_risk()
        except Exception:
            pass

        app.set_status("Source workload updated.")

    except Exception as e:
        messagebox.showerror("Invalid source values", str(e))

    finally:
        app._suppress_geometry_source_sync = False

def refresh_source_calculations(app):
    """
    Recompute source-derived outputs for the currently selected room.

    Uses project-level sources filtered via get_sources_for_room().
    Fully replaces any legacy room.sources usage.
    """

    room = app.get_room_by_name(app.sources_room_var.get())

    if not room:
        return

    # --- Correct source retrieval (NEW ARCHITECTURE) ---
    room_sources = app.get_sources_for_room(room.name)

    # --- If no sources, clear outputs ---
    if not room_sources:
        try:
            app.source_summary_text.set("No sources defined")
        except Exception:
            pass
        return

    # --- Aggregate metrics ---
    total_workload = 0.0
    total_dose_rate = 0.0

    for src in room_sources:
        try:
            params = getattr(src, "params", {}) or {}

            # --- Example workload extraction ---
            hours = float(params.get("hours_per_week", 0.0))

            # modality-specific inputs
            dose_rate = float(
                params.get("dose_rate_uSv_h_at_1m",
                params.get("dose_rate_uGy_h_at_1m", 0.0))
            )

            total_workload += hours
            total_dose_rate += dose_rate

        except Exception:
            continue

    # --- Update UI summary (safe) ---
    try:
        summary = f"{len(room_sources)} source(s) | Workload: {total_workload:.2f} h/wk"
        app.source_summary_text.set(summary)
    except Exception:
        pass

    # --- Update live preview ---
    try:
        app.update_live_source_preview_from_form()
    except Exception:
        pass

    # --- Trigger downstream recalculations ---
    try:
       safe_refresh_barrier_schedule(app)
    except Exception:
        pass

