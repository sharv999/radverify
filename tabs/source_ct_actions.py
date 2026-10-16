from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.shielding_models import Source
from services.ct_scanner_resolution import central_ct_ksec_resolver
from geometry.barrier_sync import safe_refresh_barrier_schedule
from modalities.registry import ct_ksec_source_types, source_type_options


def get_current_source(app) -> Optional[Source]:
    if not hasattr(app, "sources_room_var"):
        return None

    room_name = app.sources_room_var.get().strip()
    if not room_name:
        return None

    room = app.get_room_by_name(room_name)
    if not room:
        return None

    room_sources = app.get_sources_for_room(room.name)

    if not room_sources:
        return None

    idx = app.current_source_index

    if idx is None:
        try:
            idx = app.get_selected_source_index()
        except Exception:
            idx = None

    if idx is None or idx < 0 or idx >= len(room_sources):
        return None

    return room_sources[idx]


def update_sources_readonly_state(app) -> None:
    room = app.get_room_by_name(app.sources_room_var.get())
    locked = app._room_sources_are_locked(room)
    app._configure_source_type_combo_for_room(room)

    notice = (
        "Sources are automatically configured for this modality. Source type is locked to the room type."
        if locked else
        "Source editing is available for this room."
    )
    if hasattr(app, "sources_locked_notice_var"):
        app.sources_locked_notice_var.set(notice)

    if hasattr(app, "add_source_button"):
        app.add_source_button.configure(state="disabled")
    if hasattr(app, "delete_source_button"):
        app.delete_source_button.configure(state="disabled")

    if getattr(app, "apply_source_button", None) is not None:
        app.apply_source_button.configure(state="normal")

    if hasattr(app, "source_name_entry"):
        app.source_name_entry.configure(state="disabled" if locked else "normal")

    if hasattr(app, "source_type_combo"):
        app.source_type_combo.configure(state="disabled" if locked else "readonly")


def update_ct_source_ksec_from_selector(app, force: bool = False, source_type: str | None = None):
    if not hasattr(app, "ct_vars"):
        return None

    use_auto = str(app.ct_vars["use_scanner_db"].get()).strip() == "1"
    manual_override = str(app.ct_vars["manual_ksec_override"].get()).strip() == "1"

    if not use_auto and not force:
        return None
    if manual_override and not force:
        return None

 # CT ksec resolution is centralised through services.ct_scanner_resolution.central_ct_ksec_resolver(...).
    resolution = central_ct_ksec_resolver(
        app.ct_scanner_resolution_context,
        source_type=source_type or app.source_type_var.get().strip(),
        vendor=app.ct_vars["scanner_vendor"].get(),
        model=app.ct_vars["scanner_model"].get(),
        kvp=app._ct_form_energy_to_kvp(),
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


def mark_manual_ct_ksec_override(app, event=None):
    """
    Mark the CT ksec value as a deliberate manual override and stamp
    a lightweight audit trail. This is called only when the user edits
    the ksec entry, not merely when a NULL scanner is selected.
    """
    if not hasattr(app, "ct_vars"):
        return

    try:
        app.ct_vars["manual_ksec_override"].set("1")
    except Exception:
        pass

    try:
        app.ct_vars["manual_ksec_last_updated"].set(
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    except Exception:
        pass

    try:
        current_user = str(app.ct_vars["manual_ksec_entered_by"].get()).strip()
        if not current_user:
            assessor = ""
            try:
                assessor = str(app.project_vars.get("Assessor").get()).strip()
            except Exception:
                assessor = str(getattr(app.project, "assessor", "") or "").strip()
            if assessor:
                app.ct_vars["manual_ksec_entered_by"].set(assessor)
    except Exception:
        pass


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


def on_source_input_change(app, *args):
    if getattr(app, "_loading_source_form", False):
        return

    # CRITICAL: do NOT touch Ksec here. Only update non-Ksec dependent fields.
    app.save_current_source_form_draft()
    app.sync_current_source_to_model(ignore_errors=True)
    app.update_auto_tvl_key_display()
    app._source_dirty = True

    if hasattr(app, "source_calc_text"):
        app.update_live_source_preview_from_form()
    try:
        if hasattr(app, "geometry_tab"):
            app.geometry_tab._update_scanner_ksec_label()
            app.geometry_tab.draw_room_with_risk()
    except Exception:
        pass

    try:
        safe_refresh_barrier_schedule(app)
        app.refresh_results_tab()
        if hasattr(app, "geometry_tab"):
            app.geometry_tab.draw_room_with_risk()
    except Exception:
        pass
