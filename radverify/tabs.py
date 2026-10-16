from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from geometry.geometry_canvas import GeometryCanvas, DESIGN_FIELD_WIDTH_M, DESIGN_FIELD_HEIGHT_M, CANVAS_MARGIN_PX
from geometry.geometry_model import Opening
from config.ui_constants import COLOUR_PASS, COLOUR_REVIEW_DARK, COLOUR_FAIL, COLOUR_TEXT
from radverify.models import RadVerifyProject, BarrierInspection, MeasurementPoint, STATUS_OPTIONS


ROOM_TYPES = ("CT", "General X-ray", "PET/CT", "SPECT/CT", "Nuclear Medicine", "Other")


def _float_or_none(value: str):
    text = str(value).strip()
    if not text:
        return None
    return float(text)


class RoomDetailsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.vars: dict[str, tk.Variable] = {}
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Room Details", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        fields = [
            ("Project ID", "project_id", "entry"),
            ("Site name", "site_name", "entry"),
            ("Building / level", "building", "entry"),
            ("Room name", "room_name", "entry"),
            ("Room number", "room_number", "entry"),
            ("Room type", "room_type", "combo"),
            ("Inspector", "inspector", "entry"),
            ("Inspection date", "inspection_date", "entry"),
            ("Drawing reference", "drawing_reference", "entry"),
        ]
        for row, (label, key, kind) in enumerate(fields, start=1):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            var = tk.StringVar()
            self.vars[key] = var
            if kind == "combo":
                w = ttk.Combobox(self, textvariable=var, values=ROOM_TYPES, state="readonly")
            else:
                w = ttk.Entry(self, textvariable=var)
            w.grid(row=row, column=1, sticky="ew", pady=4)
            var.trace_add("write", lambda *_: self.apply_to_model())

        drow = len(fields) + 2
        dims = ttk.LabelFrame(self, text="Room dimensions", padding=10)
        dims.grid(row=drow, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        for c in range(6):
            dims.columnconfigure(c, weight=1 if c in (1, 3, 5) else 0)
        for col, (label, key) in enumerate((("Length S–N (m)", "length_m"), ("Width W–E (m)", "width_m"), ("Height (m)", "height_m"))):
            ttk.Label(dims, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 5))
            var = tk.StringVar()
            self.vars[key] = var
            e = ttk.Entry(dims, textvariable=var, width=9)
            e.grid(row=0, column=col * 2 + 1, sticky="ew", padx=(0, 14))
            e.bind("<FocusOut>", lambda _e: self.apply_to_model())
            e.bind("<Return>", lambda _e: self.apply_to_model())

        nrow = drow + 1
        ttk.Label(self, text="Notes").grid(row=nrow, column=0, sticky="nw", padx=(0, 12), pady=4)
        self.notes = tk.Text(self, height=9, wrap="word")
        self.notes.grid(row=nrow, column=1, sticky="nsew", pady=4)
        self.rowconfigure(nrow, weight=1)
        self.notes.bind("<FocusOut>", lambda _e: self.apply_to_model())

    def load(self):
        d = self.app.project.details
        for key, var in self.vars.items():
            if key in {"length_m", "width_m", "height_m"}:
                var.set(f"{getattr(self.app.project.geometry, key):g}")
            else:
                var.set(str(getattr(d, key)))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", d.notes)

    def apply_to_model(self):
        if getattr(self.app, "_loading", False):
            return
        d = self.app.project.details
        for key, var in self.vars.items():
            if key in {"length_m", "width_m", "height_m"}:
                continue
            setattr(d, key, str(var.get()))
        d.notes = self.notes.get("1.0", "end-1c") if hasattr(self, "notes") else d.notes
        try:
            for key in ("length_m", "width_m", "height_m"):
                value = float(self.vars[key].get())
                if value > 0:
                    setattr(self.app.project.geometry, key, value)
            self.app.project.geometry.room_name = d.room_name or "Imaging Room"
            self.app.project.geometry.clamp_source_inside_room()
        except (ValueError, tk.TclError):
            pass
        self.app.mark_dirty()
        self.app.refresh_visuals()


class FloorPlanTab(ttk.Frame):
    """Primary field-workflow surface for RadVerify.

    V0.2 Step 1 keeps the RadShield GeometryCanvas as the renderer but adds a
    RadVerify-owned interaction layer.  The plan is now the place where an
    inspector selects a barrier, opens/updates its inspection record, and
    places/selects survey measurement points.
    """

    SELECTION_COLOUR = "#2563eb"
    WALL_HIT_TOLERANCE_PX = 28

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._placement_armed = False
        self.selected_barrier_id: str | None = None
        self.selected_measurement_id: str | None = None
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        controls = ttk.Frame(self, padding=12, width=320)
        controls.grid(row=0, column=0, sticky="ns")
        controls.grid_propagate(False)
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        canvas_frame = ttk.Frame(self, padding=10)
        canvas_frame.grid(row=0, column=1, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = GeometryCanvas(canvas_frame, width=900, height=650)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<Double-1>", self._canvas_double_click)

        row = 0
        ttk.Label(controls, text="Floor Plan", style="Title.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1
        ttk.Label(
            controls,
            text=(
                "Field workflow centre. Select barriers directly on the plan, "
                "open their inspection record, or place measurement points."
            ),
            justify="left",
            wraplength=290,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        workflow = ttk.LabelFrame(controls, text="Field workflow", padding=8)
        workflow.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        workflow.columnconfigure(0, weight=1)
        self.mode_var = tk.StringVar(value="inspect")
        ttk.Radiobutton(
            workflow,
            text="Inspect barriers",
            value="inspect",
            variable=self.mode_var,
            command=self._mode_changed,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            workflow,
            text="Place measurement point",
            value="measure",
            variable=self.mode_var,
            command=self._mode_changed,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.place_hint = tk.StringVar(value="Click a wall, door or viewing panel to select it.")
        ttk.Label(workflow, textvariable=self.place_hint, wraplength=275).grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        row += 1

        selected = ttk.LabelFrame(controls, text="Selected barrier", padding=8)
        selected.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        selected.columnconfigure(0, weight=1)
        selected.columnconfigure(1, weight=1)
        self.selected_barrier_var = tk.StringVar(value="None")
        self.selected_barrier_status_var = tk.StringVar(value="")
        ttk.Label(selected, textvariable=self.selected_barrier_var, style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(selected, textvariable=self.selected_barrier_status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 6)
        )
        self.edit_barrier_button = ttk.Button(
            selected, text="Open inspection…", command=self.open_selected_barrier
        )
        self.edit_barrier_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.pass_button = ttk.Button(
            selected, text="Pass", command=lambda: self.set_selected_barrier_status("Pass")
        )
        self.review_button = ttk.Button(
            selected, text="Review", command=lambda: self.set_selected_barrier_status("Review")
        )
        self.fail_button = ttk.Button(
            selected, text="Fail", command=lambda: self.set_selected_barrier_status("Fail")
        )
        self.pass_button.grid(row=3, column=0, sticky="ew", padx=(0, 2))
        self.review_button.grid(row=3, column=1, sticky="ew", padx=(2, 0))
        self.fail_button.grid(row=4, column=0, sticky="ew", padx=(0, 2), pady=(4, 0))
        self.not_inspected_button = ttk.Button(
            selected, text="Not inspected", command=lambda: self.set_selected_barrier_status("Not inspected")
        )
        self.not_inspected_button.grid(row=4, column=1, sticky="ew", padx=(2, 0), pady=(4, 0))
        floor_ceiling = ttk.Frame(selected)
        floor_ceiling.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        floor_ceiling.columnconfigure(0, weight=1)
        floor_ceiling.columnconfigure(1, weight=1)
        ttk.Button(floor_ceiling, text="Select Floor", command=lambda: self.set_selected_barrier("Floor")).grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Button(floor_ceiling, text="Select Ceiling", command=lambda: self.set_selected_barrier("Ceiling")).grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )
        row += 1

        point_frame = ttk.LabelFrame(controls, text="Selected measurement", padding=8)
        point_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        point_frame.columnconfigure(0, weight=1)
        self.selected_measurement_var = tk.StringVar(value="None")
        ttk.Label(point_frame, textvariable=self.selected_measurement_var).grid(row=0, column=0, sticky="w")
        self.edit_measurement_button = ttk.Button(
            point_frame, text="Open measurement…", command=self.open_selected_measurement
        )
        self.edit_measurement_button.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        row += 1

        openings = ttk.LabelFrame(controls, text="Openings", padding=8)
        openings.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        openings.columnconfigure(0, weight=1)
        openings.columnconfigure(1, weight=1)
        self.wall_var = tk.StringVar(value="S")
        self.kind_var = tk.StringVar(value="door")
        self.offset_var = tk.StringVar(value="1.0")
        self.width_var = tk.StringVar(value="0.9")
        self.label_var = tk.StringVar(value="Door 1")
        self.material_var = tk.StringVar(value="Lead-lined door")
        self.pb_var = tk.StringVar(value="0.88")
        self.opening_list = tk.Listbox(openings, height=4, exportselection=False)
        self.opening_list.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.opening_list.bind("<<ListboxSelect>>", self._opening_list_selected)
        self.opening_list.bind("<Double-1>", lambda _e: self.open_selected_barrier())
        ttk.Button(openings, text="Add opening…", command=self.add_opening).grid(
            row=1, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Button(openings, text="Remove selected", command=self.remove_opening).grid(
            row=1, column=1, sticky="ew", padx=(2, 0)
        )
        row += 1

        self._update_selected_controls()

    # ------------------------------------------------------------------
    # Selection / workflow state
    # ------------------------------------------------------------------
    def reset_selection(self):
        self.selected_barrier_id = None
        self.selected_measurement_id = None
        if hasattr(self, "mode_var"):
            self.mode_var.set("inspect")
        self._placement_armed = False
        self._update_selected_controls()
        self._mode_changed()

    def _mode_changed(self):
        mode = self.mode_var.get() if hasattr(self, "mode_var") else "inspect"
        self._placement_armed = mode == "measure"
        if not hasattr(self, "canvas"):
            return
        if self._placement_armed:
            self.canvas.configure(cursor="crosshair")
            self.place_hint.set("Measurement placement active — click inside the room. Click an existing point to select it.")
        else:
            self.canvas.configure(cursor="arrow")
            self.place_hint.set("Click a wall, door or viewing panel to select it. Double-click to open its record.")

    def arm_point_placement(self):
        self.mode_var.set("measure")
        self._mode_changed()
        try:
            self.canvas.focus_set()
        except Exception:
            pass

    def _barrier_by_id(self, barrier_id: str | None):
        if not barrier_id:
            return None
        for barrier in self.app.project.barriers:
            if barrier.barrier_id == barrier_id:
                return barrier
        return None

    def _measurement_by_id(self, point_id: str | None):
        if not point_id:
            return None
        for point in self.app.project.measurements:
            if point.point_id == point_id:
                return point
        return None

    def set_selected_barrier(self, barrier_id: str | None, *, sync_table: bool = True, redraw: bool = True):
        if barrier_id is not None and self._barrier_by_id(barrier_id) is None:
            return False
        self.selected_barrier_id = barrier_id
        if barrier_id is not None:
            self.selected_measurement_id = None
            if hasattr(self.app, "measurement_tab"):
                self.app.measurement_tab.clear_selection(sync_floor=False)
        self._update_selected_controls()
        if sync_table and barrier_id and hasattr(self.app, "barrier_tab"):
            self.app.barrier_tab.select_barrier(barrier_id, focus_tab=False, sync_floor=False)
        if redraw:
            self.redraw()
        return True

    def set_selected_measurement(self, point_id: str | None, *, sync_table: bool = True, redraw: bool = True):
        if point_id is not None and self._measurement_by_id(point_id) is None:
            return False
        self.selected_measurement_id = point_id
        if point_id is not None:
            self.selected_barrier_id = None
            if hasattr(self.app, "barrier_tab"):
                self.app.barrier_tab.clear_selection(sync_floor=False)
        self._update_selected_controls()
        if sync_table and point_id and hasattr(self.app, "measurement_tab"):
            self.app.measurement_tab.select_point(point_id, focus_tab=False, sync_floor=False)
        if redraw:
            self.redraw()
        return True

    def _update_selected_controls(self):
        barrier = self._barrier_by_id(self.selected_barrier_id)
        point = self._measurement_by_id(self.selected_measurement_id)
        if hasattr(self, "selected_barrier_var"):
            self.selected_barrier_var.set(barrier.barrier_id if barrier else "None")
            self.selected_barrier_status_var.set(f"Status: {barrier.status}" if barrier else "")
            state = "normal" if barrier else "disabled"
            for button in (self.edit_barrier_button, self.pass_button, self.review_button, self.fail_button, self.not_inspected_button):
                button.configure(state=state)
        if hasattr(self, "selected_measurement_var"):
            if point:
                corrected = "" if point.corrected_uSv_h is None else f" — {point.corrected_uSv_h:g} µSv/h corrected"
                self.selected_measurement_var.set(f"{point.point_id}{corrected}")
                self.edit_measurement_button.configure(state="normal")
            else:
                self.selected_measurement_var.set("None")
                self.edit_measurement_button.configure(state="disabled")

    def set_selected_barrier_status(self, status: str):
        barrier = self._barrier_by_id(self.selected_barrier_id)
        if barrier is None:
            return
        barrier.status = status
        self.app.barrier_tab.refresh(select_id=barrier.barrier_id)
        self._update_selected_controls()
        self.app.mark_dirty()
        self.redraw()
        self.app.set_status(f"{barrier.barrier_id}: {status}")

    def open_selected_barrier(self):
        if not self.selected_barrier_id:
            return
        self.app.barrier_tab.edit_barrier(self.selected_barrier_id)

    def open_selected_measurement(self):
        if not self.selected_measurement_id:
            return
        self.app.measurement_tab.edit_point(self.selected_measurement_id)

    # ------------------------------------------------------------------
    # Opening management
    # ------------------------------------------------------------------
    def refresh_openings(self):
        if not hasattr(self, "opening_list"):
            return
        previous_id = None
        sel = self.opening_list.curselection()
        if sel:
            try:
                previous_id = self._opening_id_for_index(sel[0])
            except Exception:
                previous_id = None
        self.opening_list.delete(0, "end")
        selected_index = None
        for i, op in enumerate(self.app.project.geometry.openings, start=1):
            oid = op.id or f"{op.wall}-{op.opening_type}-{i}"
            self.opening_list.insert("end", f"{oid} | {op.wall} | {op.opening_type}")
            if oid == previous_id:
                selected_index = i - 1
        if selected_index is not None:
            self.opening_list.selection_set(selected_index)

    def _opening_id_for_index(self, index: int):
        op = self.app.project.geometry.openings[index]
        return op.id or f"{op.wall}-{op.opening_type}-{index + 1}"

    def _opening_list_selected(self, _event=None):
        sel = self.opening_list.curselection()
        if not sel:
            return
        self.set_selected_barrier(self._opening_id_for_index(sel[0]))

    def add_opening(self):
        win = tk.Toplevel(self)
        win.title("Add opening")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.columnconfigure(1, weight=1)

        local = {
            "wall": tk.StringVar(value=self.wall_var.get()),
            "kind": tk.StringVar(value=self.kind_var.get()),
            "offset": tk.StringVar(value=self.offset_var.get()),
            "width": tk.StringVar(value=self.width_var.get()),
            "label": tk.StringVar(value=self.label_var.get()),
            "material": tk.StringVar(value=self.material_var.get()),
            "pb": tk.StringVar(value=self.pb_var.get()),
        }
        row = 0
        ttk.Label(win, text="Wall").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Combobox(win, textvariable=local["wall"], values=("N", "E", "S", "W"), state="readonly", width=24).grid(
            row=row, column=1, sticky="ew", padx=12, pady=4
        )
        row += 1
        ttk.Label(win, text="Type").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Combobox(win, textvariable=local["kind"], values=("door", "viewing_panel"), state="readonly", width=24).grid(
            row=row, column=1, sticky="ew", padx=12, pady=4
        )
        row += 1
        for label, key in (
            ("Offset from wall origin (m)", "offset"),
            ("Width (m)", "width"),
            ("Label / ID", "label"),
            ("Material", "material"),
            ("Pb equivalence (mm)", "pb"),
        ):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Entry(win, textvariable=local[key], width=28).grid(row=row, column=1, sticky="ew", padx=12, pady=4)
            row += 1

        def save():
            try:
                offset = float(local["offset"].get())
                width = float(local["width"].get())
                pb = float(local["pb"].get() or 0.0)
            except ValueError:
                messagebox.showerror("Opening", "Offset, width and Pb equivalence must be numeric.", parent=win)
                return
            if width <= 0:
                messagebox.showerror("Opening", "Opening width must be greater than zero.", parent=win)
                return
            wall = local["wall"].get()
            wall_length = self.app.project.geometry.width_m if wall in {"N", "S"} else self.app.project.geometry.length_m
            half = width / 2.0
            if width > wall_length or not (half <= offset <= wall_length - half):
                messagebox.showerror(
                    "Opening",
                    f"Opening must fit on the {wall} wall. Offset is measured to the opening centre.",
                    parent=win,
                )
                return
            label = local["label"].get().strip() or f"Opening {len(self.app.project.geometry.openings)+1}"
            if any(b.barrier_id == label for b in self.app.project.barriers):
                messagebox.showerror("Opening", f"Barrier/opening ID {label!r} is already in use.", parent=win)
                return
            op = Opening(
                wall=wall,
                opening_type=local["kind"].get(),
                offset_m=offset,
                width_m=width,
                label=label,
                material=local["material"].get().strip(),
                pb_equiv_mm=pb,
                id=label,
            )
            self.wall_var.set(wall)
            self.kind_var.set(local["kind"].get())
            self.offset_var.set(local["offset"].get())
            self.width_var.set(local["width"].get())
            self.label_var.set(label)
            self.material_var.set(local["material"].get())
            self.pb_var.set(local["pb"].get())
            self.app.project.geometry.openings.append(op)
            self.app.project.sync_opening_inspections()
            self.app.barrier_tab.refresh(select_id=label)
            win.destroy()
            self.refresh_openings()
            self.set_selected_barrier(label, sync_table=True, redraw=False)
            self.redraw()
            self.app.mark_dirty()
            self.app.set_status(f"Added opening {label}")

        ttk.Button(win, text="Add opening", command=save).grid(row=row, column=1, sticky="e", padx=12, pady=12)

    def remove_opening(self):
        sel = self.opening_list.curselection()
        if not sel:
            return
        removed_id = self._opening_id_for_index(sel[0])
        del self.app.project.geometry.openings[sel[0]]
        self.app.project.sync_opening_inspections()
        if self.selected_barrier_id == removed_id:
            self.selected_barrier_id = None
        self.app.barrier_tab.refresh()
        self.refresh_openings()
        self._update_selected_controls()
        self.redraw()
        self.app.mark_dirty()
        self.app.set_status(f"Removed opening {removed_id}")

    # ------------------------------------------------------------------
    # Canvas coordinate helpers / hit testing
    # ------------------------------------------------------------------
    def _layout_metrics(self):
        g = self.app.project.geometry
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        usable_w = max(cw - CANVAS_MARGIN_PX * 2, 1)
        usable_h = max(ch - CANVAS_MARGIN_PX * 2, 1)
        scale = min(usable_w / DESIGN_FIELD_WIDTH_M, usable_h / DESIGN_FIELD_HEIGHT_M)
        field_w = DESIGN_FIELD_WIDTH_M * scale
        field_h = DESIGN_FIELD_HEIGHT_M * scale
        field_x0 = (cw - field_w) / 2
        field_y0 = (ch - field_h) / 2
        room_w = g.width_m * scale
        room_h = g.length_m * scale
        x0 = field_x0 + (field_w - room_w) / 2
        y0 = field_y0 + (field_h - room_h) / 2
        return {
            "scale": scale,
            "field_x0": field_x0,
            "field_y0": field_y0,
            "field_w": field_w,
            "field_h": field_h,
            "x0": x0,
            "y0": y0,
            "x1": x0 + room_w,
            "y1": y0 + room_h,
        }

    def canvas_to_room(self, x_px: float, y_px: float):
        m = self._layout_metrics()
        if not (m["x0"] <= x_px <= m["x1"] and m["y0"] <= y_px <= m["y1"]):
            return None
        return (
            (x_px - m["x0"]) / m["scale"],
            (m["y1"] - y_px) / m["scale"],
        )

    def room_to_canvas(self, x_m: float, y_m: float):
        m = self._layout_metrics()
        return m["x0"] + x_m * m["scale"], m["y1"] - y_m * m["scale"]

    def _tagged_target_at(self, x_px: float, y_px: float):
        measurement_ids = {m.point_id for m in self.app.project.measurements}
        barrier_ids = {b.barrier_id for b in self.app.project.barriers}
        items = self.canvas.find_overlapping(x_px - 4, y_px - 4, x_px + 4, y_px + 4)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag in measurement_ids:
                    return "measurement", tag
            for tag in tags:
                if tag in barrier_ids:
                    return "barrier", tag
        return None, None

    def _wall_target_at(self, x_px: float, y_px: float):
        m = self._layout_metrics()
        tol = self.WALL_HIT_TOLERANCE_PX
        if not (m["x0"] - tol <= x_px <= m["x1"] + tol and m["y0"] - tol <= y_px <= m["y1"] + tol):
            return None
        distances = {
            "N wall": abs(y_px - m["y0"]),
            "S wall": abs(y_px - m["y1"]),
            "W wall": abs(x_px - m["x0"]),
            "E wall": abs(x_px - m["x1"]),
        }
        barrier_id, distance = min(distances.items(), key=lambda item: item[1])
        return barrier_id if distance <= tol else None

    def barrier_target_at(self, x_px: float, y_px: float):
        kind, target_id = self._tagged_target_at(x_px, y_px)
        if kind == "barrier":
            return target_id
        return self._wall_target_at(x_px, y_px)

    def _canvas_click(self, event):
        kind, target_id = self._tagged_target_at(event.x, event.y)
        if kind == "measurement":
            self.set_selected_measurement(target_id)
            self.app.set_status(f"Selected measurement {target_id}")
            return

        if self.mode_var.get() == "measure":
            xy = self.canvas_to_room(event.x, event.y)
            if xy is None:
                self.place_hint.set("Measurement placement active — click inside the room boundary.")
                return
            x_m, y_m = xy
            point = self.app.measurement_tab.add_point_at(x_m, y_m)
            self.mode_var.set("inspect")
            self._mode_changed()
            if point is not None and point in self.app.project.measurements:
                self.set_selected_measurement(point.point_id, redraw=False)
            self.redraw()
            return

        barrier_id = target_id if kind == "barrier" else self._wall_target_at(event.x, event.y)
        if barrier_id:
            self.set_selected_barrier(barrier_id)
            self.app.set_status(f"Selected barrier {barrier_id}")

    def _canvas_double_click(self, event):
        kind, target_id = self._tagged_target_at(event.x, event.y)
        if kind == "measurement":
            self.set_selected_measurement(target_id)
            self.open_selected_measurement()
            return
        barrier_id = target_id if kind == "barrier" else self._wall_target_at(event.x, event.y)
        if barrier_id:
            self.set_selected_barrier(barrier_id)
            self.open_selected_barrier()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def redraw(self):
        if not hasattr(self, "canvas"):
            return
        g = self.app.project.geometry
        self.app.project.sync_opening_inspections()
        if self.selected_barrier_id and self._barrier_by_id(self.selected_barrier_id) is None:
            self.selected_barrier_id = None
        if self.selected_measurement_id and self._measurement_by_id(self.selected_measurement_id) is None:
            self.selected_measurement_id = None

        risk = {}
        material = {}
        for b in self.app.project.barriers:
            state = b.risk_state()
            if state:
                risk[b.barrier_id] = state
            construction = b.observed_construction.strip() or b.expected_construction.strip()
            if construction:
                material[b.barrier_id] = construction
        g.barrier_risk_map = risk
        g.wall_material_labels = material
        g.wall_p_values = {}
        g.wall_distance_values = {}
        g.wall_role_labels = {}
        g.barrier_dose_label_map = {}
        self.canvas.draw_room(
            g,
            source_type="",
            layout_rendering={
                "show_radiation_symbol": False,
                "show_patient_symbol": False,
                "show_one_m_circle": False,
                "show_barrier_status_text": True,
            },
        )
        self._draw_measurement_points()
        self._draw_selection_overlay()
        self.refresh_openings()
        self._update_selected_controls()

    def _draw_measurement_points(self):
        for mp in self.app.project.measurements:
            x, y = self.room_to_canvas(mp.x_m, mp.y_m)
            r = 9
            status = mp.status.strip().lower()
            fill = COLOUR_TEXT
            if status == "pass":
                fill = COLOUR_PASS
            elif status == "review":
                fill = COLOUR_REVIEW_DARK
            elif status == "fail":
                fill = COLOUR_FAIL
            self.canvas.create_oval(
                x-r, y-r, x+r, y+r,
                fill="white", outline=fill, width=3,
                tags=("measurement_point", mp.point_id),
            )
            self.canvas.create_text(
                x+12, y-12, text=mp.point_id, anchor="sw", fill=fill,
                font=("Bahnschrift", 8, "bold"),
                tags=("measurement_point", mp.point_id),
            )

    def _draw_selection_overlay(self):
        m = self._layout_metrics()
        colour = self.SELECTION_COLOUR
        barrier_id = self.selected_barrier_id
        if barrier_id in {"N wall", "S wall", "E wall", "W wall"}:
            coords = {
                "N wall": (m["x0"], m["y0"], m["x1"], m["y0"]),
                "S wall": (m["x0"], m["y1"], m["x1"], m["y1"]),
                "W wall": (m["x0"], m["y0"], m["x0"], m["y1"]),
                "E wall": (m["x1"], m["y0"], m["x1"], m["y1"]),
            }[barrier_id]
            self.canvas.create_line(*coords, fill=colour, width=6, tags=("radverify_selection",))
        elif barrier_id in {"Floor", "Ceiling"}:
            inset = 10 if barrier_id == "Floor" else 18
            self.canvas.create_rectangle(
                m["x0"] + inset,
                m["y0"] + inset,
                m["x1"] - inset,
                m["y1"] - inset,
                outline=colour,
                width=3,
                dash=(7, 4),
                tags=("radverify_selection",),
            )
            self.canvas.create_text(
                (m["x0"] + m["x1"]) / 2,
                m["y0"] + inset + 14,
                text=f"{barrier_id} selected",
                fill=colour,
                font=("Bahnschrift", 9, "bold"),
                tags=("radverify_selection",),
            )
        elif barrier_id:
            bbox = self.canvas.bbox(barrier_id)
            if bbox:
                pad = 7
                self.canvas.create_rectangle(
                    bbox[0] - pad,
                    bbox[1] - pad,
                    bbox[2] + pad,
                    bbox[3] + pad,
                    outline=colour,
                    width=3,
                    dash=(6, 3),
                    tags=("radverify_selection",),
                )

        point = self._measurement_by_id(self.selected_measurement_id)
        if point is not None:
            x, y = self.room_to_canvas(point.x_m, point.y_m)
            r = 14
            self.canvas.create_oval(
                x-r, y-r, x+r, y+r,
                outline=colour, width=3, dash=(5, 3),
                tags=("radverify_selection",),
            )


class BarrierInspectionTab(ttk.Frame):
    COLUMNS = ("barrier_id", "type", "expected", "observed", "pb", "status", "evidence", "notes")

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._suppress_floor_sync = False
        self._build()

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Barrier Inspection", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show="headings", selectmode="browse")
        headings = {
            "barrier_id": "Barrier", "type": "Type", "expected": "Expected construction",
            "observed": "Observed construction", "pb": "Observed Pb mm", "status": "Status",
            "evidence": "Evidence ref", "notes": "Notes",
        }
        widths = {"barrier_id":120, "type":90, "expected":180, "observed":210, "pb":95, "status":95, "evidence":120, "notes":230}
        for c in self.COLUMNS:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], minwidth=70, stretch=c in {"expected", "observed", "notes"})
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._tree_selection_changed)
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="w", pady=8)
        ttk.Button(buttons, text="Edit selected", command=self.edit_selected).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Mark Pass", command=lambda: self.set_status("Pass")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Review", command=lambda: self.set_status("Review")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Fail", command=lambda: self.set_status("Fail")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Show on Floor Plan", command=self.show_selected_on_floor_plan).pack(side="left", padx=(14, 3))

    def _selected_barrier_id(self):
        b = self._selected()
        return b.barrier_id if b else None

    def refresh(self, select_id: str | None = None):
        self.app.project.sync_opening_inspections()
        preserve_id = select_id or self._selected_barrier_id()
        self._suppress_floor_sync = True
        try:
            self.tree.delete(*self.tree.get_children())
            selected_iid = None
            for idx, b in enumerate(self.app.project.barriers):
                iid = str(idx)
                self.tree.insert("", "end", iid=iid, values=(
                    b.barrier_id, b.barrier_type, b.expected_construction, b.observed_construction,
                    "" if b.observed_pb_mm is None else f"{b.observed_pb_mm:g}", b.status, b.evidence_ref, b.notes,
                ))
                if b.barrier_id == preserve_id:
                    selected_iid = iid
            if selected_iid is not None:
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.tree.see(selected_iid)
        finally:
            self._suppress_floor_sync = False

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except (TypeError, ValueError):
            return None
        if idx >= len(self.app.project.barriers):
            return None
        return self.app.project.barriers[idx]

    def _find_barrier(self, barrier_id: str):
        for barrier in self.app.project.barriers:
            if barrier.barrier_id == barrier_id:
                return barrier
        return None

    def _tree_selection_changed(self, _event=None):
        if self._suppress_floor_sync:
            return
        barrier = self._selected()
        if barrier is not None and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(barrier.barrier_id, sync_table=False)

    def clear_selection(self, *, sync_floor: bool = False):
        self._suppress_floor_sync = True
        try:
            for iid in self.tree.selection():
                self.tree.selection_remove(iid)
        finally:
            self._suppress_floor_sync = False
        if sync_floor and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(None, sync_table=False)

    def select_barrier(self, barrier_id: str, *, focus_tab: bool = False, sync_floor: bool = True):
        match_iid = None
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if values and str(values[0]) == barrier_id:
                match_iid = iid
                break
        if match_iid is None:
            self.refresh(select_id=barrier_id)
            for iid in self.tree.get_children():
                values = self.tree.item(iid, "values")
                if values and str(values[0]) == barrier_id:
                    match_iid = iid
                    break
        if match_iid is None:
            return False
        self._suppress_floor_sync = True
        try:
            self.tree.selection_set(match_iid)
            self.tree.focus(match_iid)
            self.tree.see(match_iid)
        finally:
            self._suppress_floor_sync = False
        if sync_floor and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(barrier_id, sync_table=False)
        if focus_tab:
            self.app.notebook.select(self)
        return True

    def show_selected_on_floor_plan(self):
        barrier = self._selected()
        if barrier is None:
            return
        self.app.floor_tab.set_selected_barrier(barrier.barrier_id, sync_table=False)
        self.app.notebook.select(self.app.floor_tab)
        self.app.set_status(f"Selected barrier {barrier.barrier_id} on Floor Plan")

    def set_status_for_id(self, barrier_id: str, status: str):
        barrier = self._find_barrier(barrier_id)
        if barrier is None:
            return False
        barrier.status = status
        self.refresh(select_id=barrier_id)
        self.app.mark_dirty()
        self.app.floor_tab.set_selected_barrier(barrier_id, sync_table=False, redraw=True)
        return True

    def set_status(self, status):
        barrier = self._selected()
        if barrier is None:
            return
        self.set_status_for_id(barrier.barrier_id, status)

    def edit_barrier(self, barrier_id: str):
        if not self.select_barrier(barrier_id, sync_floor=True):
            return
        self.edit_selected()

    def edit_selected(self):
        b = self._selected()
        if not b:
            return
        win = tk.Toplevel(self)
        win.title(f"Barrier Inspection — {b.barrier_id}")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        vars_ = {
            "expected_construction": tk.StringVar(value=b.expected_construction),
            "observed_construction": tk.StringVar(value=b.observed_construction),
            "expected_pb_mm": tk.StringVar(value="" if b.expected_pb_mm is None else str(b.expected_pb_mm)),
            "observed_pb_mm": tk.StringVar(value="" if b.observed_pb_mm is None else str(b.observed_pb_mm)),
            "status": tk.StringVar(value=b.status),
            "evidence_ref": tk.StringVar(value=b.evidence_ref),
        }
        row = 0
        ttk.Label(win, text=b.barrier_id, style="Title.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(12,8)); row += 1
        for label, key in (("Expected construction", "expected_construction"), ("Observed construction", "observed_construction"), ("Expected Pb (mm)", "expected_pb_mm"), ("Observed Pb (mm)", "observed_pb_mm"), ("Evidence / photo ref", "evidence_ref")):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Entry(win, textvariable=vars_[key], width=42).grid(row=row, column=1, sticky="ew", padx=12, pady=4); row += 1
        ttk.Label(win, text="Status").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Combobox(win, textvariable=vars_["status"], values=STATUS_OPTIONS, state="readonly", width=39).grid(row=row, column=1, sticky="ew", padx=12, pady=4); row += 1
        ttk.Label(win, text="Notes").grid(row=row, column=0, sticky="nw", padx=12, pady=4)
        notes = tk.Text(win, height=6, width=42); notes.insert("1.0", b.notes); notes.grid(row=row, column=1, sticky="ew", padx=12, pady=4); row += 1

        def save():
            try:
                b.expected_pb_mm = _float_or_none(vars_["expected_pb_mm"].get())
                b.observed_pb_mm = _float_or_none(vars_["observed_pb_mm"].get())
            except ValueError:
                messagebox.showerror("Barrier", "Pb equivalence must be numeric or blank.", parent=win); return
            b.expected_construction = vars_["expected_construction"].get().strip()
            b.observed_construction = vars_["observed_construction"].get().strip()
            b.status = vars_["status"].get()
            b.evidence_ref = vars_["evidence_ref"].get().strip()
            b.notes = notes.get("1.0", "end-1c").strip()
            win.destroy()
            self.refresh(select_id=b.barrier_id)
            self.app.mark_dirty()
            self.app.floor_tab.set_selected_barrier(b.barrier_id, sync_table=False, redraw=True)
            self.app.set_status(f"Updated barrier inspection: {b.barrier_id}")
        ttk.Button(win, text="Save", command=save).grid(row=row, column=1, sticky="e", padx=12, pady=12)


class MeasurementPointsTab(ttk.Frame):
    COLUMNS = ("id", "x", "y", "h", "location", "instrument", "reading", "background", "corrected", "status", "notes")

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._suppress_floor_sync = False
        self._build()

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Measurement Points", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0,8))
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show="headings", selectmode="browse")
        labels = ("Point", "X m", "Y m", "Height m", "Location", "Instrument", "Reading µSv/h", "BG µSv/h", "Corrected µSv/h", "Status", "Notes")
        widths = (70, 65, 65, 75, 150, 140, 100, 85, 110, 90, 220)
        for c, label, width in zip(self.COLUMNS, labels, widths):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width, minwidth=55, stretch=c in {"location", "instrument", "notes"})
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._tree_selection_changed)
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="w", pady=8)
        ttk.Button(buttons, text="Add point", command=self.add_point_dialog).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="Edit selected", command=self.edit_selected).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete selected", command=self.delete_selected).pack(side="left", padx=3)
        ttk.Button(buttons, text="Show on Floor Plan", command=self.show_selected_on_floor_plan).pack(side="left", padx=(14, 3))
        ttk.Label(buttons, text="Tip: use Floor Plan → Place measurement point on plan for rapid field entry.").pack(side="left", padx=(18,0))

    def _selected_point_id(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.app.project.measurements):
            return None
        return self.app.project.measurements[idx].point_id

    def refresh(self, select_id: str | None = None):
        preserve_id = select_id or self._selected_point_id()
        self._suppress_floor_sync = True
        try:
            self.tree.delete(*self.tree.get_children())
            selected_iid = None
            for idx, m in enumerate(self.app.project.measurements):
                m.recalculate()
                fmt = lambda v: "" if v is None else f"{v:g}"
                iid = str(idx)
                self.tree.insert("", "end", iid=iid, values=(
                    m.point_id, f"{m.x_m:.2f}", f"{m.y_m:.2f}", f"{m.height_m:.2f}",
                    m.location, m.instrument, fmt(m.reading_uSv_h), fmt(m.background_uSv_h),
                    fmt(m.corrected_uSv_h), m.status, m.notes,
                ))
                if m.point_id == preserve_id:
                    selected_iid = iid
            if selected_iid is not None:
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.tree.see(selected_iid)
        finally:
            self._suppress_floor_sync = False

    def next_id(self):
        used = {m.point_id for m in self.app.project.measurements}
        i = 1
        while f"MP{i:02d}" in used:
            i += 1
        return f"MP{i:02d}"

    def add_point_at(self, x_m, y_m):
        mp = MeasurementPoint(point_id=self.next_id(), x_m=round(x_m, 2), y_m=round(y_m, 2))
        self.app.project.measurements.append(mp)
        self.refresh(select_id=mp.point_id)
        self.app.mark_dirty()
        self.app.floor_tab.set_selected_measurement(mp.point_id, sync_table=False, redraw=True)
        self._edit(mp, is_new=True)
        return mp

    def add_point_dialog(self):
        g = self.app.project.geometry
        mp = MeasurementPoint(point_id=self.next_id(), x_m=g.width_m/2, y_m=g.length_m/2)
        self.app.project.measurements.append(mp)
        self.refresh(select_id=mp.point_id)
        self.app.floor_tab.set_selected_measurement(mp.point_id, sync_table=False, redraw=True)
        self._edit(mp, is_new=True)

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _tree_selection_changed(self, _event=None):
        if self._suppress_floor_sync:
            return
        point_id = self._selected_point_id()
        if point_id and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_measurement(point_id, sync_table=False)

    def clear_selection(self, *, sync_floor: bool = False):
        self._suppress_floor_sync = True
        try:
            for iid in self.tree.selection():
                self.tree.selection_remove(iid)
        finally:
            self._suppress_floor_sync = False
        if sync_floor and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_measurement(None, sync_table=False)

    def select_point(self, point_id: str, *, focus_tab: bool = False, sync_floor: bool = True):
        match_iid = None
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if values and str(values[0]) == point_id:
                match_iid = iid
                break
        if match_iid is None:
            self.refresh(select_id=point_id)
            for iid in self.tree.get_children():
                values = self.tree.item(iid, "values")
                if values and str(values[0]) == point_id:
                    match_iid = iid
                    break
        if match_iid is None:
            return False
        self._suppress_floor_sync = True
        try:
            self.tree.selection_set(match_iid)
            self.tree.focus(match_iid)
            self.tree.see(match_iid)
        finally:
            self._suppress_floor_sync = False
        if sync_floor and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_measurement(point_id, sync_table=False)
        if focus_tab:
            self.app.notebook.select(self)
        return True

    def show_selected_on_floor_plan(self):
        point_id = self._selected_point_id()
        if not point_id:
            return
        self.app.floor_tab.set_selected_measurement(point_id, sync_table=False)
        self.app.notebook.select(self.app.floor_tab)
        self.app.set_status(f"Selected measurement {point_id} on Floor Plan")

    def edit_point(self, point_id: str):
        for mp in self.app.project.measurements:
            if mp.point_id == point_id:
                self.select_point(point_id, sync_floor=True)
                self._edit(mp)
                return

    def edit_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.app.project.measurements):
            return
        self._edit(self.app.project.measurements[idx])

    def delete_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.app.project.measurements):
            return
        point_id = self.app.project.measurements[idx].point_id
        del self.app.project.measurements[idx]
        if self.app.floor_tab.selected_measurement_id == point_id:
            self.app.floor_tab.selected_measurement_id = None
        self.refresh()
        self.app.mark_dirty()
        self.app.floor_tab.redraw()
        self.app.set_status(f"Deleted measurement {point_id}")

    def _edit(self, mp, is_new=False):
        original_id = mp.point_id
        win = tk.Toplevel(self)
        win.title(f"Measurement Point — {mp.point_id}")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        values = {
            "point_id": mp.point_id,
            "x_m": str(mp.x_m),
            "y_m": str(mp.y_m),
            "height_m": str(mp.height_m),
            "location": mp.location,
            "instrument": mp.instrument,
            "reading_uSv_h": "" if mp.reading_uSv_h is None else str(mp.reading_uSv_h),
            "background_uSv_h": "" if mp.background_uSv_h is None else str(mp.background_uSv_h),
            "status": mp.status,
            "notes": mp.notes,
        }
        vars_ = {k: tk.StringVar(value=v) for k,v in values.items() if k != "notes"}
        row = 0
        fields = (
            ("Point ID", "point_id"),
            ("X from West wall (m)", "x_m"),
            ("Y from South wall (m)", "y_m"),
            ("Height above FFL (m)", "height_m"),
            ("Location / description", "location"),
            ("Instrument", "instrument"),
            ("Reading (µSv/h)", "reading_uSv_h"),
            ("Background (µSv/h)", "background_uSv_h"),
        )
        for label, key in fields:
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Entry(win, textvariable=vars_[key], width=42).grid(row=row, column=1, sticky="ew", padx=12, pady=4)
            row += 1
        ttk.Label(win, text="Status").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Combobox(win, textvariable=vars_["status"], values=("Not assessed", "Pass", "Review", "Fail"), state="readonly", width=39).grid(row=row, column=1, sticky="ew", padx=12, pady=4)
        row += 1
        ttk.Label(win, text="Notes").grid(row=row, column=0, sticky="nw", padx=12, pady=4)
        notes = tk.Text(win, height=5, width=42)
        notes.insert("1.0", mp.notes)
        notes.grid(row=row, column=1, sticky="ew", padx=12, pady=4)
        row += 1
        corrected_var = tk.StringVar(value="")
        ttk.Label(win, text="Corrected reading").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Label(win, textvariable=corrected_var).grid(row=row, column=1, sticky="w", padx=12, pady=4)
        row += 1

        def preview(*_):
            try:
                reading = _float_or_none(vars_["reading_uSv_h"].get())
                bg = _float_or_none(vars_["background_uSv_h"].get()) or 0.0
                corrected_var.set("" if reading is None else f"{max(0.0, reading-bg):g} µSv/h")
            except ValueError:
                corrected_var.set("Invalid numeric value")

        vars_["reading_uSv_h"].trace_add("write", preview)
        vars_["background_uSv_h"].trace_add("write", preview)
        preview()

        def save():
            try:
                x = float(vars_["x_m"].get())
                y = float(vars_["y_m"].get())
                h = float(vars_["height_m"].get())
                reading = _float_or_none(vars_["reading_uSv_h"].get())
                bg = _float_or_none(vars_["background_uSv_h"].get())
            except ValueError:
                messagebox.showerror("Measurement", "Coordinates, height and readings must be numeric or blank where permitted.", parent=win)
                return
            g = self.app.project.geometry
            if not (0 <= x <= g.width_m and 0 <= y <= g.length_m):
                messagebox.showerror("Measurement", "Point coordinates must be inside the room.", parent=win)
                return
            new_id = vars_["point_id"].get().strip() or mp.point_id
            duplicate = any(other is not mp and other.point_id == new_id for other in self.app.project.measurements)
            if duplicate:
                messagebox.showerror("Measurement", f"Point ID {new_id!r} is already in use.", parent=win)
                return
            mp.point_id = new_id
            mp.x_m = x
            mp.y_m = y
            mp.height_m = h
            mp.location = vars_["location"].get().strip()
            mp.instrument = vars_["instrument"].get().strip()
            mp.reading_uSv_h = reading
            mp.background_uSv_h = bg
            mp.status = vars_["status"].get()
            mp.notes = notes.get("1.0", "end-1c").strip()
            mp.recalculate()
            win.destroy()
            self.refresh(select_id=mp.point_id)
            self.app.mark_dirty()
            if self.app.floor_tab.selected_measurement_id == original_id or is_new:
                self.app.floor_tab.selected_measurement_id = mp.point_id
            self.app.floor_tab.set_selected_measurement(mp.point_id, sync_table=False, redraw=True)
            self.app.set_status(f"Updated measurement {mp.point_id}")

        ttk.Button(win, text="Save", command=save).grid(row=row, column=1, sticky="e", padx=12, pady=12)

        if is_new:
            def on_close():
                if mp in self.app.project.measurements and not mp.location and mp.reading_uSv_h is None:
                    self.app.project.measurements.remove(mp)
                    self.refresh()
                    if self.app.floor_tab.selected_measurement_id == mp.point_id:
                        self.app.floor_tab.selected_measurement_id = None
                    self.app.floor_tab.redraw()
                win.destroy()
            win.protocol("WM_DELETE_WINDOW", on_close)
