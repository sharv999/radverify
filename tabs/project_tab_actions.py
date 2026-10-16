from __future__ import annotations

import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

from engine.shielding_engine import build_example_project
from geometry.barrier_sync import safe_refresh_barrier_schedule
from modalities.registry import get_modality_spec, production_modalities, production_modality_names
from services.modality_working_state import initialise_active_modality_working_state
from services.project_io import load_project_from_file, save_project_to_file
from services.project_ui_state import apply_loaded_project_to_ui


def _single_room(app):
    rooms = list(getattr(app.project, "rooms", []) or [])
    return rooms[0] if rooms else None


def _default_room_name_for_modality(modality: str) -> str:
    spec = get_modality_spec(modality)
    if spec is not None and str(spec.default_room_name or "").strip():
        return str(spec.default_room_name).strip()
    return f"{str(modality or 'CT').strip() or 'CT'} Room 1"


def _rename_single_room(app, room, new_name: str) -> str:
    old_name = str(getattr(room, "name", "") or "").strip()
    new_name = str(new_name or "").strip() or old_name or "Room 1"
    room.name = new_name

    geometry = getattr(room, "geometry", None)
    if geometry is not None:
        geometry.room_name = new_name

    for source in getattr(room, "sources", []) or []:
        if hasattr(source, "room_name"):
            source.room_name = new_name

    for source in getattr(app.project, "sources", []) or []:
        if str(getattr(source, "room_name", "") or "").strip() == old_name:
            source.room_name = new_name

    return new_name


def _sync_single_room_selectors(app, room) -> None:
    room_name = str(getattr(room, "name", "") or "") if room is not None else ""
    values = [room_name] if room_name else []
    app.current_room_index = 0 if room is not None else None

    if hasattr(app, "sources_room_combo"):
        app.sources_room_combo["values"] = values
    if hasattr(app, "barriers_room_combo"):
        app.barriers_room_combo["values"] = values
    if hasattr(app, "sources_room_var"):
        app.sources_room_var.set(room_name)
    if hasattr(app, "barriers_room_var"):
        app.barriers_room_var.set(room_name)

    if hasattr(app, "geometry_tab"):
        try:
            app.geometry_tab.refresh_room_list(preferred_room_name=room_name or None)
        except Exception:
            pass


def refresh_single_room_state(app) -> None:
    """Refresh the one-room state formerly owned by the Rooms tab."""
    room = _single_room(app)
    if room is None:
        app.current_room_index = None
        app._loading_room_form = True
        try:
            app.room_name_var.set("")
            app.room_modality_var.set("")
        finally:
            app._loading_room_form = False
        _sync_single_room_selectors(app, None)
        app.refresh_sources_list()
        safe_refresh_barrier_schedule(app)
        return

    app.enforce_room_source_types(room)
    for barrier in getattr(room, "barriers", []) or []:
        app._coerce_barrier_schema(barrier)
    app._apply_room_constraint_defaults(room)

    app._loading_room_form = True
    try:
        app.room_name_var.set(room.name)
        app.room_modality_var.set(room.modality)
    finally:
        app._loading_room_form = False

    _sync_single_room_selectors(app, room)
    app.refresh_sources_list(preserve_index=0)
    safe_refresh_barrier_schedule(app)


def get_selected_room_index(app):
    """Compatibility helper for code that still asks for the selected room index."""
    return 0 if _single_room(app) is not None else None


def load_selected_room(app, _event=None):
    """Compatibility entry point: a project has exactly one selectable room."""
    room = _single_room(app)
    if room is None:
        return
    app.current_room_index = 0
    app._loading_room_form = True
    try:
        app.room_name_var.set(room.name)
        app.room_modality_var.set(room.modality)
    finally:
        app._loading_room_form = False
    _sync_single_room_selectors(app, room)
    app.set_status(app._room_constraint_text(room))


def on_room_form_change(app, *args):
    """Apply Project-tab Room Name/Modality edits to the sole project room."""
    if getattr(app, "_loading_room_form", False):
        return

    room = _single_room(app)
    if room is None:
        return

    requested_modality = str(app.room_modality_var.get() or "").strip()
    if not app._is_supported_modality(requested_modality):
        default_modality = production_modalities()[0].modality_id if production_modalities() else "CT"
        app._loading_room_form = True
        try:
            app.room_modality_var.set(default_modality)
        finally:
            app._loading_room_form = False
        requested_modality = default_modality

    modality_changed = requested_modality != str(getattr(room, "modality", "") or "").strip()
    if modality_changed:
        room.modality = requested_modality
        generated_name = _default_room_name_for_modality(requested_modality)
        _rename_single_room(app, room, generated_name)
        initialise_active_modality_working_state(room)
        if str(requested_modality or "").strip().upper() == "X-RAY":
            from services.room_defaults import (
                apply_new_xray_wall_defaults, apply_new_xray_geometry_defaults,
            )
            apply_new_xray_geometry_defaults(room)
            apply_new_xray_wall_defaults(room)
        app._loading_room_form = True
        try:
            app.room_name_var.set(generated_name)
        finally:
            app._loading_room_form = False
    else:
        requested_name = str(app.room_name_var.get() or "").strip()
        if requested_name and requested_name != str(getattr(room, "name", "") or "").strip():
            _rename_single_room(app, room, requested_name)

    app.enforce_room_source_types(room)
    app._apply_room_constraint_defaults(room)
    _sync_single_room_selectors(app, room)

    try:
        app.refresh_sources_list(preserve_index=0)
        app._reload_source_ui_from_model(room, 0, refresh_live=True)
    except Exception:
        pass
    safe_refresh_barrier_schedule(app)
    try:
        app.refresh_results_tab()
    except Exception:
        pass
    try:
        app.geometry_tab.refresh_room_list(preferred_room_name=room.name)
        app.geometry_tab.load_selected_room_geometry()
    except Exception:
        pass


def apply_room_form(app):
    """Validate and apply the Project-tab room fields for the sole room."""
    room = _single_room(app)
    if room is None:
        return

    modality = str(app.room_modality_var.get() or "").strip()
    if not app._is_supported_modality(modality):
        supported = ", ".join(production_modality_names())
        messagebox.showerror(
            "Unsupported modality",
            f"Select a production-enabled modality: {supported}.",
            parent=app,
        )
        return

    previous_modality = str(getattr(room, "modality", "") or "").strip()
    room.modality = modality
    if modality != previous_modality:
        _rename_single_room(app, room, _default_room_name_for_modality(modality))
        initialise_active_modality_working_state(room)
        if str(modality or "").strip().upper() == "X-RAY":
            from services.room_defaults import (
                apply_new_xray_wall_defaults, apply_new_xray_geometry_defaults,
            )
            apply_new_xray_geometry_defaults(room)
            apply_new_xray_wall_defaults(room)
    else:
        _rename_single_room(app, room, str(app.room_name_var.get() or "").strip())

    app.enforce_room_source_types(room)
    app._apply_room_constraint_defaults(room)
    refresh_single_room_state(app)
    app.set_status("Project room updated.")


def new_project(app):
    app.project = build_example_project()
    app._prune_unsupported_rooms()
    app.current_file = None
    app.current_room_index = None
    app.current_source_index = None
    app.last_selected_source_index = None
    app.last_selected_source_room_name = None
    app.optimizer_last_recommendations = []
    app.refresh_all()
    app.set_status("New single-room shielding project created.")


def open_project(app):
    filename = filedialog.askopenfilename(
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not filename:
        return
    try:
        project = load_project_from_file(filename)
        if len(getattr(project, "rooms", []) or []) > 1:
            raise ValueError(
                "This version of RadShield supports one room per project. "
                "The selected project contains multiple rooms."
            )
        apply_loaded_project_to_ui(app, project, filename)
    except Exception as e:
        messagebox.showerror("Open failed", f"{e}\n\n{traceback.format_exc()}")


def save_project(app):
    if app.current_file is None:
        save_project_as(app)
        return

    try:
        save_project_to_file(app, app.current_file)
        app.set_status(f"Saved {app.current_file}")
    except Exception as e:
        messagebox.showerror("Save failed", f"{e}\n\n{traceback.format_exc()}")


def save_project_as(app):
    filename = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
    )
    if not filename:
        return
    app.current_file = Path(filename)
    save_project(app)


def apply_project_form(app):
    app.project.project_name = app.project_vars["Project Name"].get()
    app.project.project_type = (
        "refurbishment" if app.project_refurbishment_var.get() else "new_build"
    )
    app.project.client = app.project_vars["Client"].get()
    app.project.site = app.project_vars["Site"].get()
    app.project.assessor = app.project_vars["Assessor"].get()
    app.project.date = app.project_vars["Date"].get()
    app.project.notes = app.project_notes.get("1.0", "end").strip()
    apply_room_form(app)


def refresh_project_form(app):
    app.project_vars["Project Name"].set(app.project.project_name)
    app.project_refurbishment_var.set(
        str(getattr(app.project, "project_type", "new_build") or "new_build").strip().lower()
        == "refurbishment"
    )
    app.project_vars["Client"].set(app.project.client)
    from tabs.project_tab_layout import _refresh_client_combo
    _refresh_client_combo(app)
    app.project_vars["Site"].set(app.project.site)
    app.project_vars["Assessor"].set(app.project.assessor)
    app.project_vars["Date"].set(app.project.date)
    app.project_notes.delete("1.0", "end")
    app.project_notes.insert("1.0", app.project.notes)

    room = _single_room(app)
    app._loading_room_form = True
    try:
        app.room_name_var.set(str(getattr(room, "name", "") or "") if room else "")
        app.room_modality_var.set(str(getattr(room, "modality", "") or "") if room else "")
    finally:
        app._loading_room_form = False
    _sync_single_room_selectors(app, room)
