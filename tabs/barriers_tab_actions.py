"""Action handlers for the Barriers tab.

These functions are intentionally thin UI action functions.  They operate on the
desktop app instance but live outside app.py so app.py can remain an
orchestration shell.
"""

from __future__ import annotations

from typing import Any
from tkinter import messagebox

from models.shielding_models import Barrier
from engine.design_constraints import get_barrier_design_defaults
from engine.shielding_engine import AREA_PRESETS
from tabs.barriers_tab import BarrierInlineEditor
from geometry.barrier_sync import safe_refresh_barrier_schedule
from tabs.barrier_risk_ui import get_barrier_from_table_item

from tabs.barrier_inline_editors import (
    show_material_dropdown,
    show_pb_thickness_dropdown,
    show_xray_barrier_role_dropdown,
)

from tabs.barrier_inline_values import commercial_pb_thicknesses   
from tabs.barrier_live_results import get_barrier_live_result


def add_barrier(app):

    room = app.get_room_by_name(app.barriers_room_var.get())
    if not room:
        messagebox.showwarning("No room", "Create or select a room first.")
        return
    defaults = get_barrier_design_defaults(room.modality, "Office")
    room.barriers.append(
        Barrier(
            name=f"Barrier {len(room.barriers)+1}",
            adjacent_area="Office",
            distance_m=2.0,
            occupancy_factor=float(defaults["occupancy_factor"]),
            design_goal_uSv_per_week=float(defaults["design_goal_uSv_per_week"]),
            material="Pb",
            thickness_mm=0.88,
            material_legacy="Pb 0.88 mm (10 kg/m2)",
            barrier_role="secondary_wall",
            notes="",
        )
    )
    safe_refresh_barrier_schedule(app)
    app.refresh_results_tab()
    try:
        if hasattr(app, "geometry_tab"):
            app.geometry_tab.refresh_from_model()
    except Exception:
        pass


def delete_selected_barrier_from_table(app):
    room = app.get_room_by_name(app.barriers_room_var.get())
    if not room:
        return
    selected = app.barrier_table.selection()
    if not selected:
        return
    room, barrier, idx = get_barrier_from_table_item(app, selected[0])
    if barrier is None:
        return
    del room.barriers[idx]
    safe_refresh_barrier_schedule(app)
    app.refresh_results_tab()
    try:
        if hasattr(app, "geometry_tab"):
            app.geometry_tab.refresh_from_model()
    except Exception:
        pass


def apply_area_preset_to_selected_barrier(app):
    selected = app.barrier_table.selection()
    if not selected:
        messagebox.showwarning("No selection", "Select a barrier row first.")
        return

    room, barrier, idx = get_barrier_from_table_item(app, selected[0])
    if room is None or barrier is None:
        return

    preset_name = barrier.adjacent_area
    if preset_name not in AREA_PRESETS:
        messagebox.showwarning("No preset", f"No preset found for adjacent area '{preset_name}'.")
        return

    preset = AREA_PRESETS[preset_name]
    barrier.occupancy_factor = preset["occupancy_factor"]
    barrier.design_goal_uSv_per_week = preset["design_goal_uSv_per_week"]

    safe_refresh_barrier_schedule(app)
    app.set_status(f"Applied preset for {preset_name}.")


def on_barrier_table_double_click(app, event):
    region = app.barrier_table.identify("region", event.x, event.y)
    if region != "cell":
        return

    item_id = app.barrier_table.identify_row(event.y)
    column_id = app.barrier_table.identify_column(event.x)
    if not item_id or not column_id:
        return

    col_index = int(column_id.replace("#", "")) - 1
    column_name = app.BARRIER_COLUMNS[col_index]

    
    if column_name in app.BARRIER_RESULT_COLUMNS:
        return
    
    bbox = app.barrier_table.bbox(item_id, column_id)
    if not bbox:
        return

    x, y, w, h = bbox
    initial_value = app.barrier_table.set(item_id, column_name)

    room = app.get_room_by_name(app.barriers_room_var.get())
    if not room:
        return
    room, barrier, _ = get_barrier_from_table_item(app, item_id)
    if barrier is None:
        return

    if app.inline_editor is not None:
        app.inline_editor.destroy()
    if column_name == "adjacent_area":

        app.show_adjacent_area_dropdown(item_id, column_name, x, y, w, h, initial_value)
    elif column_name == "material":

        show_material_dropdown(app, item_id, column_name, x, y, w, h, initial_value)
    elif column_name == "barrier_role":

        show_xray_barrier_role_dropdown(app, item_id, column_name, x, y, w, h, initial_value)
    elif column_name == "thickness_mm":

        material = str(getattr(barrier, "material", "")).strip()
        if material == "Pb":
  
            show_pb_thickness_dropdown(app, item_id, column_name, x, y, w, h, initial_value)
        else:

            app.inline_editor = BarrierInlineEditor(app.barrier_table, app, item_id, column_name, initial_value)
            app.inline_editor.place(x=x, y=y, width=w, height=h)
    else:
        app.inline_editor = BarrierInlineEditor(app.barrier_table, app, item_id, column_name, initial_value)
        app.inline_editor.place(x=x, y=y, width=w, height=h)


def save_inline_barrier_edit(app, item_id: str, column_name: str, raw_value: str, apply_preset: bool = False):


    if not hasattr(app, "barrier_table"):
        return
 
    if not hasattr(app, "barrier_table"):
        return

    try:
        if item_id not in app.barrier_table.get_children():
            return
    except Exception:
        return

    room, barrier, idx = get_barrier_from_table_item(app, item_id)
    if room is None or barrier is None:
        return

    # Resolve the actual project barrier object by name. Some table rows may
    # be regenerated or represented by live/copy objects, but Geometry draws
    # from room.barriers.
    barrier_name = str(getattr(barrier, "name", "") or "").strip()
    if barrier_name:
        for candidate in getattr(room, "barriers", []) or []:
            if str(getattr(candidate, "name", "") or "").strip() == barrier_name:
                barrier = candidate
                break

    try:

        column_aliases = {
            "T": "occupancy_factor",
            "t": "occupancy_factor",
            "occupancy": "occupancy_factor",
            "Occupancy": "occupancy_factor",
            "P": "design_goal_uSv_per_week",
            "p": "design_goal_uSv_per_week",
            "Design": "design_goal_uSv_per_week",
            "design_goal": "design_goal_uSv_per_week",
            "Material": "material",
            "Thickness": "thickness_mm",
            "Provided": "thickness_mm",
            "provided": "thickness_mm",
        }
        column_name = column_aliases.get(column_name, column_name)

        if column_name in ("distance_m", "occupancy_factor", "design_goal_uSv_per_week", "thickness_mm"):
            value: Any = float(raw_value)
        else:
            value = str(raw_value)

        if column_name == "thickness_mm":
            material = str(getattr(barrier, "material", "")).strip()
            if material == "Pb":
                allowed = commercial_pb_thicknesses()
                if float(value) not in allowed:
                    raise ValueError(f"Pb thickness must be one of: {allowed}")
                barrier.thickness_mm = float(value)
            else:
                barrier.thickness_mm = float(value)
        else:
            setattr(barrier, column_name, value)

        if column_name == "material":
            if str(barrier.material).strip() == "Pb":
                allowed = commercial_pb_thicknesses()
                try:
                    current_t = float(getattr(barrier, "thickness_mm", allowed[0]))
                except Exception:
                    current_t = allowed[0]
                if current_t not in allowed:
                    barrier.thickness_mm = min(allowed, key=lambda x: abs(x - current_t))

        if apply_preset and barrier.adjacent_area in AREA_PRESETS:
            preset = AREA_PRESETS[barrier.adjacent_area]
            barrier.occupancy_factor = preset["occupancy_factor"]
            barrier.design_goal_uSv_per_week = preset["design_goal_uSv_per_week"]

        barrier_name = str(getattr(barrier, "name", "") or "").strip()

        _ = get_barrier_live_result(app, room, barrier)
        safe_refresh_barrier_schedule(app)

        # Re-select by barrier name, not stale Treeview item id
        target_item = None
        if hasattr(app, "barrier_table"):
            try:
                name_idx = app.BARRIER_COLUMNS.index("name")
                for row_id in app.barrier_table.get_children():
                    vals = app.barrier_table.item(row_id, "values")
                    if vals and str(vals[name_idx]).strip() == barrier_name:
                        target_item = row_id
                        break
            except Exception:
                target_item = None

        if target_item:
            try:
                app.barrier_table.focus(target_item)
                app.barrier_table.see(target_item)
            except Exception:
                pass

        app.set_status(f"Updated barrier {barrier.name}: {column_name}")

        try:
            safe_refresh_barrier_schedule(app)
        except Exception:
            pass

        try:
            app.refresh_results_tab()
        except Exception:
            pass

        refresh_geometry_canvas_after_barrier_edit(app, getattr(room, "name", None))

    except Exception as e:
        messagebox.showerror("Invalid value", str(e))


def refresh_geometry_canvas_after_barrier_edit(app, room_name: str | None = None) -> None:
    """Force Geometry tab to redraw after barrier material/thickness/P edits."""
    gt = getattr(app, "geometry_tab", None)
    if gt is None:
        return

    edited_room = None

    if room_name:
        try:
            for idx, room in enumerate(getattr(app.project, "rooms", []) or []):
                if getattr(room, "name", "") == room_name:
                    edited_room = room
                    app.current_room_index = idx
                    if hasattr(gt, "current_room_index"):
                        gt.current_room_index = idx
                    break
        except Exception:
            edited_room = None

    # Force Geometry tab to use the edited room geometry, not a stale cached object.
    if edited_room is not None:
        try:
            gt.geometry = getattr(edited_room, "geometry", None)
        except Exception:
            pass

    try:
        if hasattr(gt, "refresh_from_model"):
            gt.refresh_from_model()
    except Exception:
        pass

    try:
        if hasattr(gt, "draw_room_with_risk"):
            gt.draw_room_with_risk()
    except Exception:
        pass