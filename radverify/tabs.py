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
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        controls = ttk.Frame(self, padding=12)
        controls.grid(row=0, column=0, sticky="ns")
        canvas_frame = ttk.Frame(self, padding=10)
        canvas_frame.grid(row=0, column=1, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = GeometryCanvas(canvas_frame, width=900, height=650)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Button-1>", self._canvas_click)

        ttk.Label(controls, text="Floor Plan", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(controls, text="Uses the RadShield room/floor-plan renderer.\nClick the plan while point-placement is armed\nto add a measurement point.", justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Separator(controls).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(controls, text="Openings", style="Section.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        self.wall_var = tk.StringVar(value="S")
        self.kind_var = tk.StringVar(value="door")
        self.offset_var = tk.StringVar(value="1.0")
        self.width_var = tk.StringVar(value="0.9")
        self.label_var = tk.StringVar(value="Door 1")
        self.material_var = tk.StringVar(value="Lead-lined door")
        self.pb_var = tk.StringVar(value="0.88")
        fields = [
            ("Wall", self.wall_var, ("N", "E", "S", "W")),
            ("Type", self.kind_var, ("door", "viewing_panel")),
        ]
        row = 4
        for label, var, values in fields:
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Combobox(controls, textvariable=var, values=values, state="readonly", width=17).grid(row=row, column=1, sticky="ew", pady=3)
            row += 1
        for label, var in (("Offset (m)", self.offset_var), ("Width (m)", self.width_var), ("Label / ID", self.label_var), ("Material", self.material_var), ("Pb equiv. (mm)", self.pb_var)):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(controls, textvariable=var, width=19).grid(row=row, column=1, sticky="ew", pady=3)
            row += 1
        ttk.Button(controls, text="Add opening", command=self.add_opening).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 3))
        row += 1
        ttk.Button(controls, text="Remove selected opening", command=self.remove_opening).grid(row=row, column=0, columnspan=2, sticky="ew", pady=3)
        row += 1
        self.opening_list = tk.Listbox(controls, height=7, exportselection=False)
        self.opening_list.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 10))
        row += 1
        ttk.Separator(controls).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1
        self.place_button = ttk.Button(controls, text="Place measurement point on plan", command=self.arm_point_placement)
        self.place_button.grid(row=row, column=0, columnspan=2, sticky="ew", pady=3)
        row += 1
        self.place_hint = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self.place_hint, wraplength=260).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        self._placement_armed = False

    def refresh_openings(self):
        self.opening_list.delete(0, "end")
        for i, op in enumerate(self.app.project.geometry.openings, start=1):
            oid = op.id or f"{op.wall}-{op.opening_type}-{i}"
            self.opening_list.insert("end", f"{oid} | {op.wall} | {op.opening_type}")

    def add_opening(self):
        try:
            offset = float(self.offset_var.get())
            width = float(self.width_var.get())
            pb = float(self.pb_var.get() or 0.0)
        except ValueError:
            messagebox.showerror("Opening", "Offset, width and Pb equivalence must be numeric.")
            return
        label = self.label_var.get().strip() or f"Opening {len(self.app.project.geometry.openings)+1}"
        op = Opening(
            wall=self.wall_var.get(), opening_type=self.kind_var.get(), offset_m=offset, width_m=width,
            label=label, material=self.material_var.get().strip(), pb_equiv_mm=pb, id=label,
        )
        self.app.project.geometry.openings.append(op)
        self.app.project.sync_opening_inspections()
        self.app.barrier_tab.refresh()
        self.refresh_openings()
        self.redraw()
        self.app.mark_dirty()

    def remove_opening(self):
        sel = self.opening_list.curselection()
        if not sel:
            return
        del self.app.project.geometry.openings[sel[0]]
        self.app.project.sync_opening_inspections()
        self.app.barrier_tab.refresh()
        self.refresh_openings()
        self.redraw()
        self.app.mark_dirty()

    def arm_point_placement(self):
        self._placement_armed = True
        self.place_hint.set("Placement armed — click inside the room on the floor plan.")

    def _canvas_click(self, event):
        if not self._placement_armed:
            return
        xy = self.canvas_to_room(event.x, event.y)
        if xy is None:
            self.place_hint.set("Click inside the room boundary.")
            return
        self._placement_armed = False
        self.place_hint.set("")
        x_m, y_m = xy
        self.app.measurement_tab.add_point_at(x_m, y_m)
        self.redraw()

    def canvas_to_room(self, x_px: float, y_px: float):
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
        x1, y1 = x0 + room_w, y0 + room_h
        if not (x0 <= x_px <= x1 and y0 <= y_px <= y1):
            return None
        return ((x_px - x0) / scale, (y1 - y_px) / scale)

    def room_to_canvas(self, x_m: float, y_m: float):
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
        y1 = y0 + room_h
        return x0 + x_m * scale, y1 - y_m * scale

    def redraw(self):
        if not hasattr(self, "canvas"):
            return
        g = self.app.project.geometry
        self.app.project.sync_opening_inspections()
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
        self.refresh_openings()

    def _draw_measurement_points(self):
        for mp in self.app.project.measurements:
            x, y = self.room_to_canvas(mp.x_m, mp.y_m)
            r = 9
            status = mp.status.strip().lower()
            fill = COLOUR_TEXT
            if status == "pass": fill = COLOUR_PASS
            elif status == "review": fill = COLOUR_REVIEW_DARK
            elif status == "fail": fill = COLOUR_FAIL
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="white", outline=fill, width=3, tags=("measurement_point", mp.point_id))
            self.canvas.create_text(x+12, y-12, text=mp.point_id, anchor="sw", fill=fill, font=("Bahnschrift", 8, "bold"), tags=("measurement_point", mp.point_id))


class BarrierInspectionTab(ttk.Frame):
    COLUMNS = ("barrier_id", "type", "expected", "observed", "pb", "status", "evidence", "notes")

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
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
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="w", pady=8)
        ttk.Button(buttons, text="Edit selected", command=self.edit_selected).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Mark Pass", command=lambda: self.set_status("Pass")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Review", command=lambda: self.set_status("Review")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Fail", command=lambda: self.set_status("Fail")).pack(side="left", padx=3)

    def refresh(self):
        self.app.project.sync_opening_inspections()
        self.tree.delete(*self.tree.get_children())
        for idx, b in enumerate(self.app.project.barriers):
            self.tree.insert("", "end", iid=str(idx), values=(
                b.barrier_id, b.barrier_type, b.expected_construction, b.observed_construction,
                "" if b.observed_pb_mm is None else f"{b.observed_pb_mm:g}", b.status, b.evidence_ref, b.notes,
            ))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        if idx >= len(self.app.project.barriers):
            return None
        return self.app.project.barriers[idx]

    def set_status(self, status):
        b = self._selected()
        if not b:
            return
        b.status = status
        self.refresh()
        self.app.mark_dirty()
        self.app.floor_tab.redraw()

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
            win.destroy(); self.refresh(); self.app.mark_dirty(); self.app.floor_tab.redraw()
        ttk.Button(win, text="Save", command=save).grid(row=row, column=1, sticky="e", padx=12, pady=12)


class MeasurementPointsTab(ttk.Frame):
    COLUMNS = ("id", "x", "y", "h", "location", "instrument", "reading", "background", "corrected", "status", "notes")

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._build()

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Measurement Points", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0,8))
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show="headings", selectmode="browse")
        labels = ("Point", "X m", "Y m", "Height m", "Location", "Instrument", "Reading µSv/h", "BG µSv/h", "Corrected µSv/h", "Status", "Notes")
        widths = (70, 65, 65, 75, 150, 140, 100, 85, 110, 90, 220)
        for c, label, width in zip(self.COLUMNS, labels, widths):
            self.tree.heading(c, text=label); self.tree.column(c, width=width, minwidth=55, stretch=c in {"location", "instrument", "notes"})
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview); sb.grid(row=1, column=1, sticky="ns"); self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        buttons = ttk.Frame(self); buttons.grid(row=2, column=0, sticky="w", pady=8)
        ttk.Button(buttons, text="Add point", command=self.add_point_dialog).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="Edit selected", command=self.edit_selected).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete selected", command=self.delete_selected).pack(side="left", padx=3)
        ttk.Label(buttons, text="Tip: use Floor Plan → Place measurement point on plan for rapid field entry.").pack(side="left", padx=(18,0))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for idx, m in enumerate(self.app.project.measurements):
            m.recalculate()
            fmt = lambda v: "" if v is None else f"{v:g}"
            self.tree.insert("", "end", iid=str(idx), values=(m.point_id, f"{m.x_m:.2f}", f"{m.y_m:.2f}", f"{m.height_m:.2f}", m.location, m.instrument, fmt(m.reading_uSv_h), fmt(m.background_uSv_h), fmt(m.corrected_uSv_h), m.status, m.notes))

    def next_id(self):
        used = {m.point_id for m in self.app.project.measurements}
        i = 1
        while f"MP{i:02d}" in used: i += 1
        return f"MP{i:02d}"

    def add_point_at(self, x_m, y_m):
        mp = MeasurementPoint(point_id=self.next_id(), x_m=round(x_m, 2), y_m=round(y_m, 2))
        self.app.project.measurements.append(mp)
        self.refresh(); self.app.mark_dirty(); self._edit(mp)

    def add_point_dialog(self):
        g = self.app.project.geometry
        mp = MeasurementPoint(point_id=self.next_id(), x_m=g.width_m/2, y_m=g.length_m/2)
        self.app.project.measurements.append(mp)
        self.refresh(); self._edit(mp, is_new=True)

    def _selected_index(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def edit_selected(self):
        idx = self._selected_index()
        if idx is None: return
        self._edit(self.app.project.measurements[idx])

    def delete_selected(self):
        idx = self._selected_index()
        if idx is None: return
        del self.app.project.measurements[idx]
        self.refresh(); self.app.mark_dirty(); self.app.floor_tab.redraw()

    def _edit(self, mp, is_new=False):
        win = tk.Toplevel(self); win.title(f"Measurement Point — {mp.point_id}"); win.transient(self.winfo_toplevel()); win.grab_set()
        values = {
            "point_id": mp.point_id, "x_m": str(mp.x_m), "y_m": str(mp.y_m), "height_m": str(mp.height_m),
            "location": mp.location, "instrument": mp.instrument,
            "reading_uSv_h": "" if mp.reading_uSv_h is None else str(mp.reading_uSv_h),
            "background_uSv_h": "" if mp.background_uSv_h is None else str(mp.background_uSv_h),
            "status": mp.status, "notes": mp.notes,
        }
        vars_ = {k: tk.StringVar(value=v) for k,v in values.items() if k != "notes"}
        row=0
        fields=(("Point ID","point_id"),("X from West wall (m)","x_m"),("Y from South wall (m)","y_m"),("Height above FFL (m)","height_m"),("Location / description","location"),("Instrument","instrument"),("Reading (µSv/h)","reading_uSv_h"),("Background (µSv/h)","background_uSv_h"))
        for label,key in fields:
            ttk.Label(win,text=label).grid(row=row,column=0,sticky="w",padx=12,pady=4); ttk.Entry(win,textvariable=vars_[key],width=42).grid(row=row,column=1,sticky="ew",padx=12,pady=4); row+=1
        ttk.Label(win,text="Status").grid(row=row,column=0,sticky="w",padx=12,pady=4)
        ttk.Combobox(win,textvariable=vars_["status"],values=("Not assessed","Pass","Review","Fail"),state="readonly",width=39).grid(row=row,column=1,sticky="ew",padx=12,pady=4); row+=1
        ttk.Label(win,text="Notes").grid(row=row,column=0,sticky="nw",padx=12,pady=4)
        notes=tk.Text(win,height=5,width=42); notes.insert("1.0",mp.notes); notes.grid(row=row,column=1,sticky="ew",padx=12,pady=4); row+=1
        corrected_var=tk.StringVar(value="")
        ttk.Label(win,text="Corrected reading").grid(row=row,column=0,sticky="w",padx=12,pady=4); ttk.Label(win,textvariable=corrected_var).grid(row=row,column=1,sticky="w",padx=12,pady=4); row+=1

        def preview(*_):
            try:
                reading=_float_or_none(vars_["reading_uSv_h"].get()); bg=_float_or_none(vars_["background_uSv_h"].get()) or 0.0
                corrected_var.set("" if reading is None else f"{max(0.0,reading-bg):g} µSv/h")
            except ValueError: corrected_var.set("Invalid numeric value")
        vars_["reading_uSv_h"].trace_add("write",preview); vars_["background_uSv_h"].trace_add("write",preview); preview()

        def save():
            try:
                x=float(vars_["x_m"].get()); y=float(vars_["y_m"].get()); h=float(vars_["height_m"].get()); reading=_float_or_none(vars_["reading_uSv_h"].get()); bg=_float_or_none(vars_["background_uSv_h"].get())
            except ValueError:
                messagebox.showerror("Measurement", "Coordinates, height and readings must be numeric or blank where permitted.", parent=win); return
            g=self.app.project.geometry
            if not (0 <= x <= g.width_m and 0 <= y <= g.length_m):
                messagebox.showerror("Measurement", "Point coordinates must be inside the room.", parent=win); return
            mp.point_id=vars_["point_id"].get().strip() or mp.point_id; mp.x_m=x; mp.y_m=y; mp.height_m=h; mp.location=vars_["location"].get().strip(); mp.instrument=vars_["instrument"].get().strip(); mp.reading_uSv_h=reading; mp.background_uSv_h=bg; mp.status=vars_["status"].get(); mp.notes=notes.get("1.0","end-1c").strip(); mp.recalculate()
            win.destroy(); self.refresh(); self.app.mark_dirty(); self.app.floor_tab.redraw()
        ttk.Button(win,text="Save",command=save).grid(row=row,column=1,sticky="e",padx=12,pady=12)

        if is_new:
            def on_close():
                if mp in self.app.project.measurements and not mp.location and mp.reading_uSv_h is None:
                    self.app.project.measurements.remove(mp)
                    self.refresh(); self.app.floor_tab.redraw()
                win.destroy()
            win.protocol("WM_DELETE_WINDOW", on_close)
