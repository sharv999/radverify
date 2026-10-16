from __future__ import annotations
from tkinter import ttk

from tabs.barrier_inline_values import (
    commercial_pb_thicknesses,
    material_family_values,
    xray_barrier_role_values,
)

def _save_inline_barrier_edit(app, item_id, column_name, value, apply_preset=False):
    from tabs.barriers_tab_actions import save_inline_barrier_edit

    return save_inline_barrier_edit(
        app,
        item_id,
        column_name,
        value,
        apply_preset=apply_preset,
    )

def _bind_combobox_save(combo, save_callback):
    """Bind combobox save safely without FocusOut destroying before selection."""
    def save_combo(event=None):
        value = combo.get()
        try:
            save_callback(value)
        finally:
            try:
                combo.destroy()
            except Exception:
                pass

    def cancel_combo(event=None):
        try:
            combo.destroy()
        except Exception:
            pass

    combo.bind("<<ComboboxSelected>>", save_combo)
    combo.bind("<Return>", save_combo)
    combo.bind("<Escape>", cancel_combo)


def commercial_pb_thicknesses(app):
    return [0.44, 0.88, 1.32, 1.76, 2.20, 2.64, 3.08, 3.52, 5.28, 7.04, 10.56, 14.08, 17.60]


def show_pb_thickness_dropdown(app, item_id, column_name, x, y, w, h, initial_value):
    allowed = commercial_pb_thicknesses(app)
    values = [f"{v:.2f}" for v in allowed]
    combo = ttk.Combobox(app.barrier_table, values=values, state="readonly")

    try:
        current = float(initial_value)
        if current in allowed:
            combo.set(f"{current:.2f}")
        else:
            combo.set(values[0])
    except Exception:
        combo.set(values[0])

    combo.place(x=x, y=y, width=w, height=h)
    combo.focus_set()

    _bind_combobox_save(
    combo,
        lambda value: _save_inline_barrier_edit(
            app,
            item_id,
            column_name,
            value,
            apply_preset=False,
        )
    )

def material_family_values():
    return ["Pb", "Concrete", "Pb glass"]


def show_material_dropdown(app, item_id, column_name, x, y, w, h, initial_value):
    import tkinter.ttk as ttk

    combo = ttk.Combobox(
        app.barrier_table,
        values=material_family_values(),
        state="readonly",
    )
    combo.set(initial_value if initial_value in material_family_values() else "Pb")
    combo.place(x=x, y=y, width=w, height=h)
    combo.focus_set()

    _bind_combobox_save(
        combo,
        lambda value: _save_inline_barrier_edit(
            app,
            item_id,
            column_name,
            value,
            apply_preset=False,
        ),
    )

def xray_barrier_role_values(app=None):
    return [
        "fig52_chest_bucky_wall",
        "fig52_cross_table_wall",
        "fig52_secondary_wall",
        "fig52_control_wall",
        "fig52_door",
        "fig52_darkroom_wall",
        "fig52_floor_under_table",
        "fig52_ceiling",
    ]


def show_xray_barrier_role_dropdown(app, item_id, column_name, x, y, w, h, initial_value):
    combo = ttk.Combobox(
        app.barrier_table,
        values=xray_barrier_role_values(app),
        state="readonly",
    )
    combo.set(initial_value if initial_value in xray_barrier_role_values(app) else "fig52_secondary_wall")
    combo.place(x=x, y=y, width=w, height=h)
    combo.focus_set()

    _bind_combobox_save(
    combo,
    lambda value: _save_inline_barrier_edit(
        app,
        item_id,
        column_name,
        value,
        apply_preset=False,
    ),
)

