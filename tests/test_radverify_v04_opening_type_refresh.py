"""RadVerify opening editor: switching door/viewing panel refreshes dependent fields."""
import tkinter as tk
from tkinter import ttk

import pytest

from app import RadVerifyApp
from radverify.models import RadVerifyProject
from radverify.radtwin import project_to_radtwin
from radverify.tabs import opening_editor_defaults, switched_opening_fields


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.withdraw()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset(app):
    app.project = RadVerifyProject()
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.floor_tab.kind_var.set("door")
    app.floor_tab.wall_var.set("S")
    app.floor_tab.label_var.set("Door 1")
    app.floor_tab.material_var.set("Lead-lined door")
    app.floor_tab.pb_var.set("0.88")
    app.floor_tab.width_var.set("0.9")
    app.floor_tab.offset_var.set("1.0")
    app.update_idletasks()
    yield
    for child in app.floor_tab.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()


def _dialog(app):
    app.floor_tab.add_opening()
    app.update_idletasks()
    return next(child for child in app.floor_tab.winfo_children() if isinstance(child, tk.Toplevel))


def _field(win, row):
    return next(w for w in win.winfo_children() if int(w.grid_info().get("row", -1)) == row and int(w.grid_info().get("column", -1)) == 1)


def _select_type(app, win, value):
    kind = _field(win, 1)
    kind.set(value)
    kind.event_generate("<<ComboboxSelected>>")
    app.update_idletasks()


def test_doors_and_viewing_panels_have_distinct_defaults():
    d = opening_editor_defaults("door", "CT")
    p = opening_editor_defaults("viewing_panel", "CT")
    assert d["pb"] == "0.88"
    assert p["pb"] == "2.2"
    assert p["material"] == "Pb equivalent glass"
    assert (d["sill"], d["head"]) == ("0", "2.1")
    assert (p["sill"], p["head"]) == ("0.9", "1.8")


def test_type_change_updates_material_pb_label_dimensions_and_heights(app):
    win = _dialog(app)
    assert _field(win, 5).get() == "Lead-lined door"
    _select_type(app, win, "viewing_panel")
    assert _field(win, 3).get() == "1.2"  # default opening width
    assert _field(win, 4).get() == "Viewing Panel 1"  # generated ID
    assert _field(win, 5).get() == "Pb equivalent glass"
    assert _field(win, 6).get() == "2.2"
    assert _field(win, 7).get() == "0.9"
    assert _field(win, 8).get() == "1.8"
    assert tuple(_field(win, 5)["values"]) == ("Pb equivalent glass", "Pb glass", "Lead acrylic")
    _select_type(app, win, "door")
    assert _field(win, 4).get() == "Door 1"
    assert _field(win, 5).get() == "Lead-lined door"
    assert _field(win, 6).get() == "0.88"


def test_type_change_preserves_custom_pb_width_and_user_id(app):
    win = _dialog(app)
    _field(win, 3).delete(0, "end")
    _field(win, 3).insert(0, "1.05")
    _field(win, 4).delete(0, "end")
    _field(win, 4).insert(0, "SOUTH-WINDOW-A")
    _field(win, 6).delete(0, "end")
    _field(win, 6).insert(0, "1.7")
    _select_type(app, win, "viewing_panel")
    assert _field(win, 3).get() == "1.05"
    assert _field(win, 4).get() == "SOUTH-WINDOW-A"
    assert _field(win, 6).get() == "1.7"
    assert _field(win, 5).get() == "Pb equivalent glass"


def test_saved_viewing_panel_has_physical_specification_and_digital_twin(app):
    win = _dialog(app)
    _select_type(app, win, "viewing_panel")
    _field(win, 2).delete(0, "end")
    _field(win, 2).insert(0, "2.0")
    button = next(w for w in win.winfo_children() if isinstance(w, ttk.Button) and w.cget("text") == "Add opening")
    button.invoke()
    assert not win.winfo_exists()
    op = app.project.geometry.openings[-1]
    assert op.opening_type == "viewing_panel"
    assert op.material == "Pb equivalent glass"
    assert (op.width_m, op.pb_equiv_mm) == pytest.approx((1.2, 2.2))
    assert (op.sill_height_above_ffl_m, op.head_height_above_ffl_m) == pytest.approx((0.9, 1.8))
    twin = project_to_radtwin(app.project)
    assert twin["geometry"]["openings"][0]["opening_type"] == "viewing_panel"


def test_duplicate_auto_label_advances_on_next_dialog(app):
    win = _dialog(app)
    button = next(w for w in win.winfo_children() if isinstance(w, ttk.Button) and w.cget("text") == "Add opening")
    button.invoke()
    assert len(app.project.geometry.openings) == 1
    second = _dialog(app)
    assert _field(second, 4).get() == "Door 2"
