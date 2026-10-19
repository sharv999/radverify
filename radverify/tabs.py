from __future__ import annotations

import os
import math
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable

from geometry.geometry_canvas import GeometryCanvas, DESIGN_FIELD_WIDTH_M, DESIGN_FIELD_HEIGHT_M, CANVAS_MARGIN_PX
from geometry.geometry_model import Opening
from geometry.room_defaults import get_barrier_default
from config.geometry_constants import MIN_ROOM_DIMENSION_M
from config.ui_constants import COLOUR_PASS, COLOUR_REVIEW_DARK, COLOUR_FAIL, COLOUR_TEXT
from radverify.models import RadVerifyProject, BarrierInspection, EvidenceItem, MeasurementPoint, MeasurementRecord, STATUS_OPTIONS


ROOM_TYPES = ("CT", "General X-ray", "PET/CT", "SPECT/CT", "Nuclear Medicine", "Other")


def _float_or_none(value: str):
    text = str(value).strip()
    if not text:
        return None
    return float(text)


# Opening-editor defaults are suggested values, not verification findings.
# The Pb equivalence may be overridden by the inspector and must never be
# silently treated as an as-built measurement.
_OPENING_MATERIALS = {
    "door": ("Lead-lined door", "Solid timber + Pb", "Steel + Pb", "Fire door + Pb", "Pb"),
    "viewing_panel": ("Pb equivalent glass", "Pb glass", "Lead acrylic"),
}
_OPENING_LABEL_PREFIX = {"door": "Door", "viewing_panel": "Viewing Panel"}


def opening_editor_defaults(opening_type: str, room_type: str = "CT") -> dict[str, str]:
    """Proposed opening editor values, consistent with RadShield's room defaults."""
    kind = "viewing_panel" if opening_type == "viewing_panel" else "door"
    spec = get_barrier_default(room_type, kind)
    return {
        "material": _OPENING_MATERIALS[kind][0],
        "pb": f"{float(spec.get('pb_mm', 2.2 if kind == 'viewing_panel' else 0.88)):g}",
        "width": "1.2" if kind == "viewing_panel" else "0.9",
        "sill": f"{float(spec.get('sill_height_above_ffl_m', 0.9 if kind == 'viewing_panel' else 0.0)):g}",
        "head": f"{float(spec.get('head_height_above_ffl_m', 1.8 if kind == 'viewing_panel' else 2.1)):g}",
    }


def switched_opening_fields(
    values: dict[str, str], previous_type: str, new_type: str, room_type: str = "CT"
) -> dict[str, str]:
    """Refresh type-dependent defaults without erasing custom size/shielding entries."""
    before = opening_editor_defaults(previous_type, room_type)
    after = opening_editor_defaults(new_type, room_type)
    updated = dict(values)
    for key in ("width", "pb", "sill", "head"):
        current = values.get(key, "").strip()
        try:
            is_default = (not current or abs(float(current) - float(before[key])) < 1e-9)
        except ValueError:
            is_default = False
        if is_default:
            updated[key] = after[key]
    current_material = values.get("material", "").strip()
    if not current_material or current_material not in _OPENING_MATERIALS[new_type]:
        updated["material"] = after["material"]
    return updated


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
            if key not in {"length_m", "width_m", "height_m"}:
                var.set(str(getattr(d, key)))
        self.load_dimensions()
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", d.notes)

    def load_dimensions(self):
        """Sync room detail fields from the canonical shared geometry."""
        for key in ("length_m", "width_m", "height_m"):
            self.vars[key].set(f"{getattr(self.app.project.geometry, key):g}")

    def apply_to_model(self):
        if getattr(self.app, "_loading", False):
            return
        d = self.app.project.details
        for key, var in self.vars.items():
            if key in {"length_m", "width_m", "height_m"}:
                continue
            setattr(d, key, str(var.get()))
        d.notes = self.notes.get("1.0", "end-1c") if hasattr(self, "notes") else d.notes
        g = self.app.project.geometry
        for key in ("length_m", "width_m", "height_m"):
            try:
                value = float(self.vars[key].get())
                if not math.isfinite(value) or value < MIN_ROOM_DIMENSION_M:
                    raise ValueError
            except (ValueError, tk.TclError):
                self.vars[key].set(f"{getattr(g, key):g}")
                self.app.set_status(f"Invalid {key.replace('_m', '')}: enter at least {MIN_ROOM_DIMENSION_M:g} m.")
                continue
            if hasattr(self.app, "floor_tab"):
                issue = self.app.floor_tab._dimension_conflict(key, value)
                if issue:
                    self.vars[key].set(f"{getattr(g, key):g}")
                    self.app.set_status(f"Room dimensions unchanged: {issue}")
                    continue
            setattr(g, key, value)
        g.room_name = d.room_name or "Imaging Room"
        g.clamp_source_inside_room()
        if hasattr(self.app, "floor_tab"):
            self.app.floor_tab.load_dimensions()
        self.app.mark_dirty()
        self.app.refresh_visuals()


def _pb_equivalence_text(value: float | None) -> str:
    """Render a recorded Pb-equivalence value without guessing from design/status."""
    if value is None:
        return "not recorded"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "not recorded"
    if not math.isfinite(number) or number < 0:
        return "not recorded"
    return f"{number:g} mm"


def floor_plan_wall_pb_labels(barriers: list[BarrierInspection]) -> tuple[dict[str, str], dict[str, str]]:
    """Return separately identified as-built and design labels for the four walls.

    Inspection status does not establish thickness; ``observed_pb_mm`` is the
    only source of the as-built Pb-equivalence label. A missing field stays
    missing even when a design specification or Pass status exists.
    """
    as_built, design = {}, {}
    for barrier in barriers:
        if barrier.barrier_id not in {"N wall", "E wall", "S wall", "W wall"}:
            continue
        as_built[barrier.barrier_id] = f"As-built Pb eq: {_pb_equivalence_text(barrier.observed_pb_mm)}"
        if barrier.expected_pb_mm is not None:
            design[barrier.barrier_id] = f"Design Pb eq: {_pb_equivalence_text(barrier.expected_pb_mm)}"
    return as_built, design


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
        self.dimension_vars: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # The sidebar is scrollable, as in RadShield, so all controls remain
        # reachable on smaller field-laptop displays and at 125–150% scaling.
        left_shell = ttk.Frame(self)
        left_shell.grid(row=0, column=0, sticky="ns")
        left_shell.rowconfigure(0, weight=1)
        left_canvas = tk.Canvas(left_shell, width=315, highlightthickness=0, borderwidth=0)
        left_canvas.grid(row=0, column=0, sticky="ns")
        left_scrollbar = ttk.Scrollbar(left_shell, orient="vertical", command=left_canvas.yview)
        left_scrollbar.grid(row=0, column=1, sticky="ns")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        controls = ttk.Frame(left_canvas, padding=12)
        controls_id = left_canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", lambda _e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.bind("<Configure>", lambda e: left_canvas.itemconfigure(controls_id, width=e.width))
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-event.delta / 120), "units")
        left_canvas.bind("<Enter>", lambda _e: left_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        left_canvas.bind("<Leave>", lambda _e: left_canvas.unbind_all("<MouseWheel>"))
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

        # Match RadShield's direct entry and 0.1 m nudge controls while using
        # the same geometry object that is saved in native and Digital Twin JSON.
        dimensions = ttk.LabelFrame(controls, text="Room geometry (m)", padding=8)
        dimensions.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        dimensions.columnconfigure(1, weight=1)
        for drow, (label, key) in enumerate((
            ("Length S–N", "length_m"),
            ("Width W–E", "width_m"),
            ("Height", "height_m"),
        )):
            ttk.Label(dimensions, text=label).grid(row=drow, column=0, sticky="w", pady=2, padx=(0, 7))
            var = tk.StringVar(value=f"{getattr(self.app.project.geometry, key):g}")
            self.dimension_vars[key] = var
            ttk.Button(dimensions, text="−", width=3,
                       command=lambda k=key: self.nudge_dimension(k, -0.1)).grid(
                row=drow, column=1, sticky="e", padx=(0, 3), pady=2
            )
            entry = ttk.Entry(dimensions, textvariable=var, width=8, justify="right")
            entry.grid(row=drow, column=2, sticky="ew", pady=2)
            entry.bind("<Return>", lambda _e, k=key: self.commit_dimension(k))
            entry.bind("<FocusOut>", lambda _e, k=key: self.commit_dimension(k))
            ttk.Button(dimensions, text="+", width=3,
                       command=lambda k=key: self.nudge_dimension(k, 0.1)).grid(
                row=drow, column=3, sticky="w", padx=(3, 0), pady=2
            )
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
        self.selected_barrier_pb_var = tk.StringVar(value="")
        ttk.Label(selected, textvariable=self.selected_barrier_var, style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(selected, textvariable=self.selected_barrier_status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 6)
        )
        ttk.Label(selected, textvariable=self.selected_barrier_pb_var, justify="left", wraplength=270).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        self.edit_barrier_button = ttk.Button(
            selected, text="Open inspection…", command=self.open_selected_barrier
        )
        self.edit_barrier_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.pass_button = ttk.Button(
            selected, text="Pass", command=lambda: self.set_selected_barrier_status("Pass")
        )
        self.review_button = ttk.Button(
            selected, text="Review", command=lambda: self.set_selected_barrier_status("Review")
        )
        self.fail_button = ttk.Button(
            selected, text="Fail", command=lambda: self.set_selected_barrier_status("Fail")
        )
        self.pass_button.grid(row=4, column=0, sticky="ew", padx=(0, 2))
        self.review_button.grid(row=4, column=1, sticky="ew", padx=(2, 0))
        self.fail_button.grid(row=5, column=0, sticky="ew", padx=(0, 2), pady=(4, 0))
        self.not_inspected_button = ttk.Button(
            selected, text="Not inspected", command=lambda: self.set_selected_barrier_status("Not inspected")
        )
        self.not_inspected_button.grid(row=5, column=1, sticky="ew", padx=(2, 0), pady=(4, 0))
        floor_ceiling = ttk.Frame(selected)
        floor_ceiling.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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

    def load_dimensions(self):
        """Keep the Floor Plan editors in sync with Room Details and file imports."""
        for key, var in self.dimension_vars.items():
            var.set(f"{getattr(self.app.project.geometry, key):g}")

    def _dimension_conflict(self, key: str, value: float) -> str | None:
        """Do not strand surveyed points/openings outside the edited room footprint."""
        g = self.app.project.geometry
        if key == "height_m":
            for point in self.app.project.measurements:
                if point.height_m > value + 1e-8:
                    return f"{point.point_id} measurement height lies above the proposed ceiling."
            for opening in g.openings:
                if opening.head_height_above_ffl_m > value + 1e-8:
                    return f"Opening {opening.id or opening.label or opening.wall} exceeds the proposed ceiling height."
            return None
        axis = "x_m" if key == "width_m" else "y_m"
        for point in self.app.project.measurements:
            if getattr(point, axis) > value + 1e-8:
                return f"{point.point_id} lies outside the proposed room boundary."
        wall_set = {"N", "S"} if key == "width_m" else {"E", "W"}
        for opening in g.openings:
            # offset_m denotes the *centre* of an opening, not its near edge.
            if opening.wall in wall_set and opening.offset_m + opening.width_m / 2 > value + 1e-8:
                return f"Opening {opening.id or opening.label or opening.wall} would extend beyond its wall."
        return None

    def commit_dimension(self, key: str):
        """Commit a typed dimension on Return/focus loss, preserving existing records."""
        if getattr(self.app, "_loading", False) or key not in self.dimension_vars:
            return False
        g = self.app.project.geometry
        text = self.dimension_vars[key].get().strip()
        try:
            value = float(text)
            if not math.isfinite(value) or value < MIN_ROOM_DIMENSION_M:
                raise ValueError
        except ValueError:
            self.dimension_vars[key].set(f"{getattr(g, key):g}")
            self.app.set_status(f"Invalid {key.replace('_m', '')}: enter a finite value of at least {MIN_ROOM_DIMENSION_M:g} m.")
            return False
        issue = self._dimension_conflict(key, value)
        if issue:
            self.dimension_vars[key].set(f"{getattr(g, key):g}")
            self.app.set_status(f"Room dimensions unchanged: {issue}")
            return False
        previous = getattr(g, key)
        if abs(value - previous) < 1e-9:
            self.dimension_vars[key].set(f"{previous:g}")
            return True
        old_source = (g.source.x_m, g.source.y_m)
        setattr(g, key, value)
        g.clamp_source_inside_room()
        self.load_dimensions()
        self.app.room_tab.load_dimensions()
        self.app.mark_dirty()
        self.app.refresh_visuals()
        msg = f"Room {key.replace('_m', '')}: {value:g} m"
        if (g.source.x_m, g.source.y_m) != old_source:
            msg += " (source moved inside resized room)"
        self.app.set_status(msg)
        return True

    def nudge_dimension(self, key: str, delta_m: float):
        """RadShield-style +/- 0.1 m nudge, using the canonical model."""
        if key not in self.dimension_vars:
            return False
        current = getattr(self.app.project.geometry, key)
        value = round(max(MIN_ROOM_DIMENSION_M, current + delta_m), 3)
        self.dimension_vars[key].set(f"{value:g}")
        return self.commit_dimension(key)

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
            if barrier is None:
                self.selected_barrier_pb_var.set("")
            else:
                lines = [f"As-built Pb eq: {_pb_equivalence_text(barrier.observed_pb_mm)}"]
                if barrier.expected_pb_mm is not None:
                    lines.append(f"Design Pb eq: {_pb_equivalence_text(barrier.expected_pb_mm)}")
                self.selected_barrier_pb_var.set("\n".join(lines))
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

        room_type = self.app.project.details.room_type
        existing_ids = {b.barrier_id for b in self.app.project.barriers}

        def next_label(kind: str) -> str:
            prefix = _OPENING_LABEL_PREFIX[kind]
            index = 1
            while f"{prefix} {index}" in existing_ids:
                index += 1
            return f"{prefix} {index}"

        prior_type = self.kind_var.get()
        defaults = opening_editor_defaults(prior_type, room_type)
        previous_label = self.label_var.get()
        if previous_label in existing_ids:
            previous_label = next_label(prior_type)
        local = {
            "wall": tk.StringVar(value=self.wall_var.get()),
            "kind": tk.StringVar(value=prior_type),
            "offset": tk.StringVar(value=self.offset_var.get()),
            "width": tk.StringVar(value=self.width_var.get()),
            "label": tk.StringVar(value=previous_label),
            "material": tk.StringVar(value=self.material_var.get()),
            "pb": tk.StringVar(value=self.pb_var.get()),
            "sill": tk.StringVar(value=defaults["sill"]),
            "head": tk.StringVar(value=defaults["head"]),
        }
        row = 0
        ttk.Label(win, text="Wall").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        ttk.Combobox(win, textvariable=local["wall"], values=("N", "E", "S", "W"), state="readonly", width=24).grid(
            row=row, column=1, sticky="ew", padx=12, pady=4
        )
        row += 1
        ttk.Label(win, text="Type").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        kind_combo = ttk.Combobox(win, textvariable=local["kind"], values=("door", "viewing_panel"), state="readonly", width=24)
        kind_combo.grid(row=row, column=1, sticky="ew", padx=12, pady=4)
        row += 1
        for label, key in (
            ("Offset to opening centre (m)", "offset"),
            ("Width (m)", "width"),
            ("Label / ID", "label"),
        ):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Entry(win, textvariable=local[key], width=28).grid(row=row, column=1, sticky="ew", padx=12, pady=4)
            row += 1
        ttk.Label(win, text="Material").grid(row=row, column=0, sticky="w", padx=12, pady=4)
        material_combo = ttk.Combobox(win, textvariable=local["material"], values=_OPENING_MATERIALS[prior_type], width=26)
        material_combo.grid(row=row, column=1, sticky="ew", padx=12, pady=4)
        row += 1
        for label, key in (
            ("Pb equivalence (mm)", "pb"),
            ("Sill above FFL (m)", "sill"),
            ("Head above FFL (m)", "head"),
        ):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Entry(win, textvariable=local[key], width=28).grid(row=row, column=1, sticky="ew", padx=12, pady=4)
            row += 1

        def on_type_change(_event=None):
            nonlocal prior_type
            kind = local["kind"].get()
            if kind == prior_type or kind not in _OPENING_MATERIALS:
                return
            values = {key: var.get() for key, var in local.items()}
            updated = switched_opening_fields(values, prior_type, kind, room_type)
            for key in ("material", "width", "pb", "sill", "head"):
                local[key].set(updated[key])
            old_prefix = _OPENING_LABEL_PREFIX[prior_type]
            label = local["label"].get().strip()
            # Only auto-rename an auto-generated ID, never a deliberate user ID.
            if label.startswith(old_prefix + " ") and label[len(old_prefix) + 1:].isdigit():
                local["label"].set(next_label(kind))
            material_combo["values"] = _OPENING_MATERIALS[kind]
            prior_type = kind

        kind_combo.bind("<<ComboboxSelected>>", on_type_change)

        def save():
            try:
                offset = float(local["offset"].get())
                width = float(local["width"].get())
                pb = float(local["pb"].get())
                sill = float(local["sill"].get())
                head = float(local["head"].get())
            except ValueError:
                messagebox.showerror("Opening", "Offset, width, Pb equivalence and heights must be numeric.", parent=win)
                return
            if not all(math.isfinite(v) for v in (offset, width, pb, sill, head)) or width <= 0 or pb < 0:
                messagebox.showerror("Opening", "Use finite values; width must be positive and Pb equivalence non-negative.", parent=win)
                return
            if sill < 0 or head <= sill or head > self.app.project.geometry.height_m:
                messagebox.showerror("Opening", "Require 0 ≤ sill < head ≤ room height.", parent=win)
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
            label = local["label"].get().strip() or next_label(local["kind"].get())
            if label in existing_ids:
                messagebox.showerror("Opening", f"Barrier/opening ID {label!r} is already in use.", parent=win)
                return
            kind = local["kind"].get()
            type_spec = get_barrier_default(room_type, kind)
            op = Opening(
                wall=wall,
                opening_type=kind,
                offset_m=offset,
                width_m=width,
                label=label,
                material=local["material"].get().strip(),
                pb_equiv_mm=pb,
                sill_height_above_ffl_m=sill,
                head_height_above_ffl_m=head,
                kvp_basis=type_spec.get("kvp_basis") if kind == "viewing_panel" else None,
                id=label,
            )
            self.wall_var.set(wall)
            self.kind_var.set(kind)
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
        for b in self.app.project.barriers:
            state = b.risk_state()
            if state:
                risk[b.barrier_id] = state
        # Only a recorded field observation may be shown as actual shielding.
        # The RadShield design is a separate reference, never an as-built fallback.
        as_built_labels, design_labels = floor_plan_wall_pb_labels(self.app.project.barriers)
        g.barrier_risk_map = risk
        g.wall_material_labels = design_labels
        g.wall_p_values = {}
        g.wall_distance_values = {}
        g.wall_role_labels = as_built_labels
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
    """Design-vs-as-built barrier verification workspace.

    RadShield design values are displayed as immutable reference data.  The
    field inspector edits only the as-built and verification layers, preserving
    design intent for the Radiation Room Digital Twin lifecycle.
    """

    COLUMNS = (
        "barrier_id", "type", "design", "design_pb", "as_built", "as_built_pb",
        "difference", "status", "evidence",
    )

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._suppress_floor_sync = False
        self._editor_loading = False
        self._editor_barrier_id: str | None = None
        self._build()

    @staticmethod
    def comparison_summary(barrier: BarrierInspection) -> str:
        if barrier.status.strip().lower() == "not inspected" and not barrier.observed_construction and barrier.observed_pb_mm is None:
            return "Not inspected"
        has_design = bool(barrier.expected_construction.strip()) or barrier.expected_pb_mm is not None
        has_as_built = bool(barrier.observed_construction.strip()) or barrier.observed_pb_mm is not None
        if not has_design:
            return "No design specification"
        if not has_as_built:
            return "As-built not recorded"

        differences = []
        if barrier.expected_construction.strip() and barrier.observed_construction.strip():
            if barrier.expected_construction.strip().casefold() != barrier.observed_construction.strip().casefold():
                differences.append("construction")
        if barrier.expected_pb_mm is not None and barrier.observed_pb_mm is not None:
            delta = barrier.observed_pb_mm - barrier.expected_pb_mm
            if abs(delta) > 1e-9:
                differences.append(f"Pb {delta:+g} mm")
        elif barrier.expected_pb_mm is not None or barrier.observed_pb_mm is not None:
            differences.append("Pb")

        return "Matches design" if not differences else "Differs: " + ", ".join(differences)

    @staticmethod
    def evidence_summary(barrier: BarrierInspection) -> str:
        count = len(barrier.evidence_items)
        if count:
            suffix = "item" if count == 1 else "items"
            primary = barrier.evidence_ref.strip()
            return f"{count} {suffix}" + (f" — {primary}" if primary else "")
        return barrier.evidence_ref

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Barrier Inspection — Design vs As-Built", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        body = ttk.Panedwindow(self, orient="vertical")
        body.grid(row=1, column=0, sticky="nsew")

        table_frame = ttk.Frame(body)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS, show="headings", selectmode="browse", height=11)
        headings = {
            "barrier_id": "Barrier", "type": "Type", "design": "Design construction",
            "design_pb": "Design Pb mm", "as_built": "As-built construction",
            "as_built_pb": "As-built Pb mm", "difference": "Comparison", "status": "Status",
            "evidence": "Evidence",
        }
        widths = {
            "barrier_id": 105, "type": 90, "design": 180, "design_pb": 95, "as_built": 190,
            "as_built_pb": 100, "difference": 155, "status": 95, "evidence": 125,
        }
        for c in self.COLUMNS:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], minwidth=70, stretch=c in {"design", "as_built", "difference"})
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._tree_selection_changed)
        body.add(table_frame, weight=3)

        editor = ttk.Frame(body, padding=(0, 8, 0, 0))
        editor.columnconfigure(0, weight=1)
        editor.columnconfigure(1, weight=1)
        editor.columnconfigure(2, weight=1)
        body.add(editor, weight=2)

        self.editor_title_var = tk.StringVar(value="Select a barrier to inspect")
        ttk.Label(editor, textvariable=self.editor_title_var, style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )

        # DESIGN is reference-only.  The readonly state is intentional: a field
        # verification must never overwrite the originating RadShield design.
        design = ttk.LabelFrame(editor, text="DESIGN — read only", padding=9)
        design.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        design.columnconfigure(1, weight=1)
        self.design_construction_var = tk.StringVar()
        self.design_pb_var = tk.StringVar()
        ttk.Label(design, text="Construction").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.design_construction_entry = ttk.Entry(design, textvariable=self.design_construction_var, state="readonly")
        self.design_construction_entry.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(design, text="Pb equivalent (mm)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.design_pb_entry = ttk.Entry(design, textvariable=self.design_pb_var, state="readonly")
        self.design_pb_entry.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(
            design,
            text="Imported design intent is preserved and cannot be edited in RadVerify.",
            wraplength=310,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        asbuilt = ttk.LabelFrame(editor, text="AS-BUILT — field observation", padding=9)
        asbuilt.grid(row=1, column=1, sticky="nsew", padx=5)
        asbuilt.columnconfigure(1, weight=1)
        self.asbuilt_construction_var = tk.StringVar()
        self.asbuilt_pb_var = tk.StringVar()
        ttk.Label(asbuilt, text="Construction").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.asbuilt_construction_entry = ttk.Entry(asbuilt, textvariable=self.asbuilt_construction_var)
        self.asbuilt_construction_entry.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(asbuilt, text="Pb equivalent (mm)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.asbuilt_pb_entry = ttk.Entry(asbuilt, textvariable=self.asbuilt_pb_var)
        self.asbuilt_pb_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self.comparison_var = tk.StringVar(value="")
        ttk.Label(asbuilt, text="Comparison").grid(row=2, column=0, sticky="nw", padx=(0, 8), pady=(8, 4))
        ttk.Label(asbuilt, textvariable=self.comparison_var, style="Section.TLabel", wraplength=230).grid(
            row=2, column=1, sticky="w", pady=(8, 4)
        )

        verification = ttk.LabelFrame(editor, text="VERIFICATION", padding=9)
        verification.grid(row=1, column=2, sticky="nsew", padx=(5, 0))
        verification.columnconfigure(1, weight=1)
        self.status_var = tk.StringVar(value="Not inspected")
        self.evidence_var = tk.StringVar()
        ttk.Label(verification, text="Status").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.status_combo = ttk.Combobox(
            verification, textvariable=self.status_var, values=STATUS_OPTIONS, state="readonly"
        )
        self.status_combo.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(verification, text="Primary evidence ref").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.evidence_entry = ttk.Entry(verification, textvariable=self.evidence_var)
        self.evidence_entry.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(verification, text="Notes").grid(row=2, column=0, sticky="nw", padx=(0, 8), pady=4)
        self.notes_text = tk.Text(verification, height=4, width=28, wrap="word")
        self.notes_text.grid(row=2, column=1, sticky="nsew", pady=4)
        verification.rowconfigure(2, weight=1)

        evidence = ttk.LabelFrame(editor, text="EVIDENCE — linked to selected barrier", padding=9)
        evidence.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(9, 0))
        evidence.columnconfigure(0, weight=1)
        evidence.rowconfigure(1, weight=1)
        ttk.Label(
            evidence,
            text="Attach photos/documents or record non-file evidence. Files are linked, not embedded; a SHA-256 hash is recorded when a file is attached.",
            wraplength=1050,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        evidence_columns = ("id", "type", "reference", "file", "date", "inspector", "integrity", "description")
        self.evidence_tree = ttk.Treeview(evidence, columns=evidence_columns, show="headings", selectmode="browse", height=5)
        evidence_headings = {
            "id": "ID", "type": "Type", "reference": "Reference", "file": "Linked file",
            "date": "Date", "inspector": "Inspector", "integrity": "Integrity", "description": "Description",
        }
        evidence_widths = {
            "id": 90, "type": 85, "reference": 130, "file": 190, "date": 90, "inspector": 110,
            "integrity": 100, "description": 260,
        }
        for col in evidence_columns:
            self.evidence_tree.heading(col, text=evidence_headings[col])
            self.evidence_tree.column(col, width=evidence_widths[col], minwidth=65, stretch=col in {"file", "description"})
        self.evidence_tree.grid(row=1, column=0, sticky="nsew")
        evidence_scroll = ttk.Scrollbar(evidence, orient="vertical", command=self.evidence_tree.yview)
        evidence_scroll.grid(row=1, column=1, sticky="ns")
        self.evidence_tree.configure(yscrollcommand=evidence_scroll.set)
        self.evidence_tree.bind("<<TreeviewSelect>>", self._evidence_selection_changed)
        self.evidence_tree.bind("<Double-1>", lambda _e: self.edit_selected_evidence())

        evidence_buttons = ttk.Frame(evidence)
        evidence_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.add_evidence_file_button = ttk.Button(evidence_buttons, text="Attach file…", command=self.add_evidence_file)
        self.add_evidence_file_button.pack(side="left", padx=(0, 4))
        self.add_evidence_reference_button = ttk.Button(evidence_buttons, text="Add reference…", command=self.add_evidence_reference)
        self.add_evidence_reference_button.pack(side="left", padx=4)
        self.edit_evidence_button = ttk.Button(evidence_buttons, text="Edit…", command=self.edit_selected_evidence)
        self.edit_evidence_button.pack(side="left", padx=4)
        self.remove_evidence_button = ttk.Button(evidence_buttons, text="Remove", command=self.remove_selected_evidence)
        self.remove_evidence_button.pack(side="left", padx=4)
        self.open_evidence_button = ttk.Button(evidence_buttons, text="Open file", command=self.open_selected_evidence)
        self.open_evidence_button.pack(side="left", padx=4)
        self.verify_evidence_button = ttk.Button(evidence_buttons, text="Verify hash", command=self.verify_selected_evidence)
        self.verify_evidence_button.pack(side="left", padx=4)
        self.evidence_status_var = tk.StringVar(value="")
        ttk.Label(evidence_buttons, textvariable=self.evidence_status_var).pack(side="right", padx=(10, 0))
        editor.rowconfigure(2, weight=1)

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Save as-built / verification", command=self.save_selected).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Mark Pass", command=lambda: self.set_status("Pass")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Review", command=lambda: self.set_status("Review")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Fail", command=lambda: self.set_status("Fail")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Mark Not inspected", command=lambda: self.set_status("Not inspected")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Show on Floor Plan", command=self.show_selected_on_floor_plan).pack(side="right")

        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in (self.asbuilt_construction_entry, self.asbuilt_pb_entry, self.evidence_entry):
            widget.configure(state=state)
        self.status_combo.configure(state="readonly" if enabled else "disabled")
        self.notes_text.configure(state=state)
        for widget in (
            self.add_evidence_file_button, self.add_evidence_reference_button, self.edit_evidence_button,
            self.remove_evidence_button, self.open_evidence_button, self.verify_evidence_button,
        ):
            widget.configure(state=state)
        if not enabled:
            self.evidence_status_var.set("")

    def _selected_barrier_id(self):
        b = self._selected()
        return b.barrier_id if b else None

    def refresh(self, select_id: str | None = None):
        self.app.project.sync_opening_inspections()
        preserve_id = select_id or self._selected_barrier_id() or self._editor_barrier_id
        self._suppress_floor_sync = True
        try:
            self.tree.delete(*self.tree.get_children())
            selected_iid = None
            for idx, b in enumerate(self.app.project.barriers):
                iid = str(idx)
                self.tree.insert("", "end", iid=iid, values=(
                    b.barrier_id,
                    b.barrier_type,
                    b.expected_construction,
                    "" if b.expected_pb_mm is None else f"{b.expected_pb_mm:g}",
                    b.observed_construction,
                    "" if b.observed_pb_mm is None else f"{b.observed_pb_mm:g}",
                    self.comparison_summary(b),
                    b.status,
                    self.evidence_summary(b),
                ))
                if b.barrier_id == preserve_id:
                    selected_iid = iid
            if selected_iid is not None:
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.tree.see(selected_iid)
        finally:
            self._suppress_floor_sync = False
        self._load_editor(self._find_barrier(preserve_id) if preserve_id else None)

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

    def _find_barrier(self, barrier_id: str | None):
        if not barrier_id:
            return None
        for barrier in self.app.project.barriers:
            if barrier.barrier_id == barrier_id:
                return barrier
        return None

    def _load_editor(self, barrier: BarrierInspection | None):
        self._editor_loading = True
        try:
            self._editor_barrier_id = barrier.barrier_id if barrier else None
            if barrier is None:
                self.editor_title_var.set("Select a barrier to inspect")
                for var in (
                    self.design_construction_var, self.design_pb_var, self.asbuilt_construction_var,
                    self.asbuilt_pb_var, self.evidence_var, self.comparison_var,
                ):
                    var.set("")
                self.status_var.set("Not inspected")
                self.notes_text.configure(state="normal")
                self.notes_text.delete("1.0", "end")
                self.notes_text.configure(state="disabled")
                self._refresh_evidence(None)
                self._set_editor_enabled(False)
                return
            self._set_editor_enabled(True)
            self.editor_title_var.set(f"{barrier.barrier_id} — {barrier.barrier_type}")
            self.design_construction_var.set(barrier.expected_construction or "—")
            self.design_pb_var.set("—" if barrier.expected_pb_mm is None else f"{barrier.expected_pb_mm:g}")
            self.asbuilt_construction_var.set(barrier.observed_construction)
            self.asbuilt_pb_var.set("" if barrier.observed_pb_mm is None else f"{barrier.observed_pb_mm:g}")
            self.status_var.set(barrier.status)
            self.evidence_var.set(barrier.evidence_ref)
            self.comparison_var.set(self.comparison_summary(barrier))
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", barrier.notes)
            self._refresh_evidence(barrier)
        finally:
            self._editor_loading = False

    def _refresh_evidence(self, barrier: BarrierInspection | None):
        if not hasattr(self, "evidence_tree"):
            return
        self.evidence_tree.delete(*self.evidence_tree.get_children())
        self.evidence_status_var.set("")
        if barrier is None:
            return
        for idx, item in enumerate(barrier.evidence_items):
            file_name = Path(item.file_path).name if item.file_path else ""
            integrity = item.integrity_status()
            self.evidence_tree.insert("", "end", iid=str(idx), values=(
                item.evidence_id,
                item.evidence_type,
                item.reference,
                file_name,
                item.inspection_date,
                item.inspector,
                integrity,
                item.description,
            ))

    def _selected_evidence(self) -> EvidenceItem | None:
        barrier = self._find_barrier(self._editor_barrier_id)
        if barrier is None:
            return None
        sel = self.evidence_tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except (TypeError, ValueError):
            return None
        if idx < 0 or idx >= len(barrier.evidence_items):
            return None
        return barrier.evidence_items[idx]

    def _next_evidence_id(self, barrier: BarrierInspection) -> str:
        stem = "".join(ch if ch.isalnum() else "-" for ch in barrier.barrier_id.upper()).strip("-") or "BARRIER"
        used = {item.evidence_id for item in barrier.evidence_items}
        number = 1
        while True:
            candidate = f"{stem}-EV{number:02d}"
            if candidate not in used:
                return candidate
            number += 1

    def add_evidence_item(self, barrier_id: str, item: EvidenceItem) -> bool:
        barrier = self._find_barrier(barrier_id)
        if barrier is None:
            return False
        if not item.evidence_id:
            item.evidence_id = self._next_evidence_id(barrier)
        if any(existing.evidence_id == item.evidence_id for existing in barrier.evidence_items):
            raise ValueError(f"Evidence ID already exists for {barrier_id}: {item.evidence_id}")
        barrier.evidence_items.append(item)
        if not barrier.evidence_ref:
            barrier.evidence_ref = item.reference or (Path(item.file_path).name if item.file_path else item.evidence_id)
        self.evidence_var.set(barrier.evidence_ref)
        self.refresh(select_id=barrier_id)
        self.app.mark_dirty()
        self.app.set_status(f"Added evidence {item.evidence_id} to {barrier_id}")
        return True

    def _evidence_dialog(self, *, title: str, item: EvidenceItem) -> EvidenceItem | None:
        win = tk.Toplevel(self)
        win.title(title)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.columnconfigure(1, weight=1)

        type_var = tk.StringVar(value=item.evidence_type or "Photo")
        ref_var = tk.StringVar(value=item.reference)
        path_var = tk.StringVar(value=item.file_path)
        date_var = tk.StringVar(value=item.inspection_date or self.app.project.details.inspection_date)
        inspector_var = tk.StringVar(value=item.inspector or self.app.project.details.inspector)

        fields = [
            ("Type", type_var, "combo"),
            ("Reference", ref_var, "entry"),
            ("Linked file", path_var, "entry"),
            ("Inspection date", date_var, "entry"),
            ("Inspector", inspector_var, "entry"),
        ]
        for row, (label, var, kind) in enumerate(fields):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=5)
            if kind == "combo":
                widget = ttk.Combobox(win, textvariable=var, values=("Photo", "Drawing", "Document", "Measurement", "Other"), state="readonly")
            else:
                widget = ttk.Entry(win, textvariable=var, width=55)
            widget.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=5)

        ttk.Label(win, text="Description").grid(row=5, column=0, sticky="nw", padx=(12, 8), pady=5)
        description = tk.Text(win, height=5, width=55, wrap="word")
        description.grid(row=5, column=1, sticky="nsew", padx=(0, 12), pady=5)
        description.insert("1.0", item.description)
        win.rowconfigure(5, weight=1)

        result = {"ok": False}

        def save():
            item.evidence_type = type_var.get().strip() or "Other"
            item.reference = ref_var.get().strip()
            item.file_path = path_var.get().strip()
            item.inspection_date = date_var.get().strip()
            item.inspector = inspector_var.get().strip()
            item.description = description.get("1.0", "end-1c").strip()
            if item.file_path:
                try:
                    item.refresh_hash()
                except OSError as exc:
                    messagebox.showerror("Evidence", f"Could not read the linked file:\n{exc}", parent=win)
                    return
            else:
                item.sha256 = ""
            if not item.reference and not item.file_path:
                messagebox.showerror("Evidence", "Enter a reference or select a linked file.", parent=win)
                return
            result["ok"] = True
            win.destroy()

        buttons = ttk.Frame(win)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self.wait_window(win)
        return item if result["ok"] else None

    def add_evidence_file(self):
        barrier = self._find_barrier(self._editor_barrier_id)
        if barrier is None:
            return
        filename = filedialog.askopenfilename(
            title=f"Attach evidence to {barrier.barrier_id}",
            filetypes=(("Evidence files", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.pdf *.doc *.docx *.xls *.xlsx"), ("All files", "*.*")),
        )
        if not filename:
            return
        item = EvidenceItem(
            evidence_id=self._next_evidence_id(barrier),
            evidence_type="Photo" if Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"} else "Document",
            reference=Path(filename).name,
            file_path=str(Path(filename)),
            inspection_date=self.app.project.details.inspection_date,
            inspector=self.app.project.details.inspector,
        )
        edited = self._evidence_dialog(title="Attach evidence file", item=item)
        if edited is not None:
            self.add_evidence_item(barrier.barrier_id, edited)

    def add_evidence_reference(self):
        barrier = self._find_barrier(self._editor_barrier_id)
        if barrier is None:
            return
        item = EvidenceItem(
            evidence_id=self._next_evidence_id(barrier),
            evidence_type="Other",
            inspection_date=self.app.project.details.inspection_date,
            inspector=self.app.project.details.inspector,
        )
        edited = self._evidence_dialog(title="Add evidence reference", item=item)
        if edited is not None:
            self.add_evidence_item(barrier.barrier_id, edited)

    def edit_selected_evidence(self):
        barrier = self._find_barrier(self._editor_barrier_id)
        item = self._selected_evidence()
        if barrier is None or item is None:
            return
        edited = EvidenceItem(**{name: getattr(item, name) for name in EvidenceItem.__dataclass_fields__})
        edited = self._evidence_dialog(title=f"Edit evidence {item.evidence_id}", item=edited)
        if edited is None:
            return
        item.evidence_type = edited.evidence_type
        item.reference = edited.reference
        item.file_path = edited.file_path
        item.sha256 = edited.sha256
        item.inspection_date = edited.inspection_date
        item.inspector = edited.inspector
        item.description = edited.description
        if barrier.evidence_ref == "" or barrier.evidence_ref == item.evidence_id:
            barrier.evidence_ref = item.reference or (Path(item.file_path).name if item.file_path else item.evidence_id)
        self.evidence_var.set(barrier.evidence_ref)
        self.refresh(select_id=barrier.barrier_id)
        self.app.mark_dirty()
        self.app.set_status(f"Updated evidence {item.evidence_id}")

    def remove_selected_evidence(self):
        barrier = self._find_barrier(self._editor_barrier_id)
        item = self._selected_evidence()
        if barrier is None or item is None:
            return
        if not messagebox.askyesno("Remove evidence", f"Remove {item.evidence_id} from {barrier.barrier_id}?\n\nThe linked source file will not be deleted.", parent=self):
            return
        barrier.evidence_items = [existing for existing in barrier.evidence_items if existing.evidence_id != item.evidence_id]
        if barrier.evidence_ref in {item.reference, item.evidence_id, Path(item.file_path).name if item.file_path else ""}:
            if barrier.evidence_items:
                first = barrier.evidence_items[0]
                barrier.evidence_ref = first.reference or (Path(first.file_path).name if first.file_path else first.evidence_id)
            else:
                barrier.evidence_ref = ""
        self.evidence_var.set(barrier.evidence_ref)
        self.refresh(select_id=barrier.barrier_id)
        self.app.mark_dirty()
        self.app.set_status(f"Removed evidence {item.evidence_id}")

    @staticmethod
    def _open_file_path(path: Path):
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def open_selected_evidence(self):
        item = self._selected_evidence()
        if item is None or not item.file_path:
            messagebox.showinfo("Evidence", "The selected evidence record has no linked file.", parent=self)
            return
        path = Path(item.file_path)
        if not path.exists():
            messagebox.showerror("Evidence", f"Linked evidence file not found:\n{path}", parent=self)
            return
        try:
            self._open_file_path(path)
        except OSError as exc:
            messagebox.showerror("Evidence", f"Could not open linked evidence file:\n{exc}", parent=self)

    def verify_selected_evidence(self):
        item = self._selected_evidence()
        if item is None:
            return
        status = item.integrity_status()
        self.evidence_status_var.set(f"{item.evidence_id}: {status}")
        barrier = self._find_barrier(self._editor_barrier_id)
        if barrier is not None:
            self._refresh_evidence(barrier)
        self.app.set_status(f"Evidence integrity {item.evidence_id}: {status}")

    def _evidence_selection_changed(self, _event=None):
        item = self._selected_evidence()
        if item is None:
            self.evidence_status_var.set("")
            return
        self.evidence_status_var.set(f"{item.evidence_id}: {item.integrity_status()}")

    def _tree_selection_changed(self, _event=None):
        if self._suppress_floor_sync:
            return
        barrier = self._selected()
        self._load_editor(barrier)
        if barrier is not None and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(barrier.barrier_id, sync_table=False)

    def clear_selection(self, *, sync_floor: bool = False):
        self._suppress_floor_sync = True
        try:
            for iid in self.tree.selection():
                self.tree.selection_remove(iid)
        finally:
            self._suppress_floor_sync = False
        self._load_editor(None)
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
        barrier = self._find_barrier(barrier_id)
        self._load_editor(barrier)
        if sync_floor and hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(barrier_id, sync_table=False)
        if focus_tab:
            self.app.notebook.select(self)
            self.after_idle(self.asbuilt_construction_entry.focus_set)
        return True

    def show_selected_on_floor_plan(self):
        barrier = self._selected()
        if barrier is None:
            return
        self.app.floor_tab.set_selected_barrier(barrier.barrier_id, sync_table=False)
        self.app.notebook.select(self.app.floor_tab)
        self.app.set_status(f"Selected barrier {barrier.barrier_id} on Floor Plan")

    def save_selected(self):
        barrier = self._find_barrier(self._editor_barrier_id)
        if barrier is None:
            return False
        try:
            observed_pb = _float_or_none(self.asbuilt_pb_var.get())
        except ValueError:
            messagebox.showerror("Barrier", "As-built Pb equivalence must be numeric or blank.", parent=self)
            return False

        # Deliberately do not assign expected_* here.  Those fields are the
        # immutable design layer imported from RadShield/the Digital Twin.
        barrier.observed_construction = self.asbuilt_construction_var.get().strip()
        barrier.observed_pb_mm = observed_pb
        barrier.status = self.status_var.get()
        barrier.evidence_ref = self.evidence_var.get().strip()
        barrier.notes = self.notes_text.get("1.0", "end-1c").strip()
        self.comparison_var.set(self.comparison_summary(barrier))
        self.refresh(select_id=barrier.barrier_id)
        self.app.mark_dirty()
        if hasattr(self.app, "floor_tab"):
            self.app.floor_tab.set_selected_barrier(barrier.barrier_id, sync_table=False, redraw=True)
        self.app.set_status(f"Saved as-built verification: {barrier.barrier_id}")
        return True

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
        barrier = self._selected() or self._find_barrier(self._editor_barrier_id)
        if barrier is None:
            return
        self.set_status_for_id(barrier.barrier_id, status)

    def edit_barrier(self, barrier_id: str):
        if self.select_barrier(barrier_id, focus_tab=True, sync_floor=True):
            self.app.set_status(f"Inspecting barrier {barrier_id}: design is read-only; record as-built findings")

    def edit_selected(self):
        barrier = self._selected()
        if barrier is None:
            return
        self.select_barrier(barrier.barrier_id, focus_tab=True, sync_floor=True)


class MeasurementPointsTab(ttk.Frame):
    """Spatial survey workflow with instrument traceability and measurement history."""

    COLUMNS = (
        "id", "x", "y", "h", "location", "instrument", "calibration",
        "measured", "reading", "background", "corrected", "status", "history",
    )

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._suppress_floor_sync = False
        self._build()

    def _build(self):
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Measurement Points", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Place points spatially on the Floor Plan, then record traceable survey measurements against each location.",
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show="headings", selectmode="browse")
        labels = (
            "Point", "X m", "Y m", "Height m", "Location", "Instrument", "Calibration",
            "Latest", "Gross µSv/h", "BG µSv/h", "Corrected µSv/h", "Status", "History",
        )
        widths = (70, 60, 60, 70, 145, 160, 90, 120, 95, 80, 110, 90, 65)
        for c, label, width in zip(self.COLUMNS, labels, widths):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width, minwidth=50, stretch=c in {"location", "instrument"})
        self.tree.grid(row=2, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self.view_history())
        self.tree.bind("<<TreeviewSelect>>", self._tree_selection_changed)

        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, sticky="ew", pady=8)
        ttk.Button(buttons, text="Add point", command=self.add_point_dialog).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Edit point / instrument", command=self.edit_selected).pack(side="left", padx=3)
        ttk.Button(buttons, text="Record measurement…", command=self.record_selected).pack(side="left", padx=(12, 3))
        ttk.Button(buttons, text="Measurement history…", command=self.view_history).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete point", command=self.delete_selected).pack(side="left", padx=(12, 3))
        ttk.Button(buttons, text="Show on Floor Plan", command=self.show_selected_on_floor_plan).pack(side="left", padx=(12, 3))
        ttk.Label(buttons, text="Tip: Floor Plan → Place measurement point is fastest in the field.").pack(side="right", padx=(18, 0))

    @staticmethod
    def _fmt(value):
        return "" if value is None else f"{value:g}"

    @staticmethod
    def _instrument_summary(mp: MeasurementPoint) -> str:
        parts = [part for part in (mp.instrument, mp.instrument_id, mp.serial_number) if str(part).strip()]
        return " / ".join(parts)

    def _selected_point_id(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.app.project.measurements):
            return None
        return self.app.project.measurements[idx].point_id

    def _point_by_id(self, point_id: str | None) -> MeasurementPoint | None:
        for point in self.app.project.measurements:
            if point.point_id == point_id:
                return point
        return None

    def refresh(self, select_id: str | None = None):
        preserve_id = select_id or self._selected_point_id()
        self._suppress_floor_sync = True
        try:
            self.tree.delete(*self.tree.get_children())
            selected_iid = None
            for idx, m in enumerate(self.app.project.measurements):
                m.recalculate()
                calibration_reference_date = m.measured_at or self.app.project.details.inspection_date
                iid = str(idx)
                self.tree.insert("", "end", iid=iid, values=(
                    m.point_id,
                    f"{m.x_m:.2f}",
                    f"{m.y_m:.2f}",
                    f"{m.height_m:.2f}",
                    m.location,
                    self._instrument_summary(m),
                    m.calibration_status(calibration_reference_date),
                    m.measured_at,
                    self._fmt(m.reading_uSv_h),
                    self._fmt(m.background_uSv_h),
                    self._fmt(m.corrected_uSv_h),
                    m.status,
                    len(m.measurement_history),
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
        mp = MeasurementPoint(point_id=self.next_id(), x_m=g.width_m / 2, y_m=g.length_m / 2)
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
        mp = self._point_by_id(point_id)
        if mp is not None:
            self.select_point(point_id, sync_floor=True)
            self._edit(mp)

    def edit_selected(self):
        point_id = self._selected_point_id()
        mp = self._point_by_id(point_id)
        if mp is not None:
            self._edit(mp)

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
        self.app.set_status(f"Deleted measurement point {point_id}")

    def add_measurement_record(self, point_id: str, record: MeasurementRecord) -> bool:
        """Programmatic workflow used by the UI and regression tests."""
        mp = self._point_by_id(point_id)
        if mp is None:
            return False
        if not record.record_id:
            record.record_id = mp.next_record_id()
        mp.add_measurement_record(record)
        self.refresh(select_id=point_id)
        self.app.mark_dirty()
        self.app.floor_tab.set_selected_measurement(point_id, sync_table=False, redraw=True)
        self.app.set_status(f"Recorded {record.record_id} at {point_id}")
        return True

    def record_selected(self):
        point_id = self._selected_point_id()
        mp = self._point_by_id(point_id)
        if mp is None:
            return
        self._edit_record(mp, None)

    def _edit(self, mp: MeasurementPoint, is_new: bool = False):
        original_id = mp.point_id
        win = tk.Toplevel(self)
        win.title(f"Measurement Point / Instrument — {mp.point_id}")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.columnconfigure(1, weight=1)

        point_frame = ttk.LabelFrame(win, text="Spatial point", padding=8)
        point_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        point_frame.columnconfigure(1, weight=1)
        instrument_frame = ttk.LabelFrame(win, text="Instrument / calibration", padding=8)
        instrument_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        instrument_frame.columnconfigure(1, weight=1)
        defaults_frame = ttk.LabelFrame(win, text="Survey defaults", padding=8)
        defaults_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        defaults_frame.columnconfigure(1, weight=1)

        values = {
            "point_id": mp.point_id,
            "x_m": str(mp.x_m),
            "y_m": str(mp.y_m),
            "height_m": str(mp.height_m),
            "location": mp.location,
            "instrument": mp.instrument,
            "instrument_id": mp.instrument_id,
            "serial_number": mp.serial_number,
            "calibration_date": mp.calibration_date,
            "calibration_due_date": mp.calibration_due_date,
            "calibration_reference": mp.calibration_reference,
            "measurement_type": mp.measurement_type,
        }
        vars_ = {k: tk.StringVar(value=v) for k, v in values.items()}

        def entries(frame, fields):
            for row, (label, key) in enumerate(fields):
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
                ttk.Entry(frame, textvariable=vars_[key], width=44).grid(row=row, column=1, sticky="ew", pady=3)

        entries(point_frame, (
            ("Point ID", "point_id"),
            ("X from West wall (m)", "x_m"),
            ("Y from South wall (m)", "y_m"),
            ("Height above FFL (m)", "height_m"),
            ("Location / description", "location"),
        ))
        entries(instrument_frame, (
            ("Instrument / make-model", "instrument"),
            ("Instrument ID / asset ID", "instrument_id"),
            ("Serial number", "serial_number"),
            ("Calibration date (YYYY-MM-DD)", "calibration_date"),
            ("Calibration due (YYYY-MM-DD)", "calibration_due_date"),
            ("Calibration certificate/reference", "calibration_reference"),
        ))
        ttk.Label(defaults_frame, text="Measurement type").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Entry(defaults_frame, textvariable=vars_["measurement_type"], width=44).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(defaults_frame, text="Default field conditions").grid(row=1, column=0, sticky="nw", padx=(0, 10), pady=3)
        conditions = tk.Text(defaults_frame, height=3, width=44)
        conditions.insert("1.0", mp.field_conditions)
        conditions.grid(row=1, column=1, sticky="ew", pady=3)

        calib_var = tk.StringVar(value=mp.calibration_status(self.app.project.details.inspection_date))
        ttk.Label(instrument_frame, text="Calibration status").grid(row=6, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Label(instrument_frame, textvariable=calib_var).grid(row=6, column=1, sticky="w", pady=3)

        def update_calibration(*_):
            probe = MeasurementRecord(
                record_id="_preview",
                measured_at=self.app.project.details.inspection_date,
                calibration_due_date=vars_["calibration_due_date"].get().strip(),
            )
            calib_var.set(probe.calibration_status(self.app.project.details.inspection_date))

        vars_["calibration_due_date"].trace_add("write", update_calibration)

        button_frame = ttk.Frame(win)
        button_frame.grid(row=3, column=0, columnspan=2, sticky="e", padx=10, pady=10)

        def cancel():
            if is_new and mp in self.app.project.measurements and not mp.location and not mp.measurement_history:
                self.app.project.measurements.remove(mp)
                self.refresh()
                if self.app.floor_tab.selected_measurement_id == mp.point_id:
                    self.app.floor_tab.selected_measurement_id = None
                self.app.floor_tab.redraw()
            win.destroy()

        def save():
            try:
                x = float(vars_["x_m"].get())
                y = float(vars_["y_m"].get())
                h = float(vars_["height_m"].get())
            except ValueError:
                messagebox.showerror("Measurement", "Coordinates and height must be numeric.", parent=win)
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
            mp.instrument_id = vars_["instrument_id"].get().strip()
            mp.serial_number = vars_["serial_number"].get().strip()
            mp.calibration_date = vars_["calibration_date"].get().strip()
            mp.calibration_due_date = vars_["calibration_due_date"].get().strip()
            mp.calibration_reference = vars_["calibration_reference"].get().strip()
            mp.measurement_type = vars_["measurement_type"].get().strip() or "Ambient dose rate"
            mp.field_conditions = conditions.get("1.0", "end-1c").strip()
            win.destroy()
            self.refresh(select_id=mp.point_id)
            self.app.mark_dirty()
            if self.app.floor_tab.selected_measurement_id == original_id or is_new:
                self.app.floor_tab.selected_measurement_id = mp.point_id
            self.app.floor_tab.set_selected_measurement(mp.point_id, sync_table=False, redraw=True)
            self.app.set_status(f"Updated measurement point {mp.point_id}")
            if is_new:
                self.after_idle(lambda: self._edit_record(mp, None))

        ttk.Button(button_frame, text="Save point", command=save).pack(side="right")
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side="right", padx=(0, 6))

        if is_new:
            win.protocol("WM_DELETE_WINDOW", cancel)

    def _edit_record(self, mp: MeasurementPoint, record: MeasurementRecord | None):
        editing = record is not None
        if record is None:
            measured_default = self.app.project.details.inspection_date or datetime.now().date().isoformat()
            record = MeasurementRecord(
                record_id=mp.next_record_id(),
                measured_at=measured_default,
                instrument=mp.instrument,
                instrument_id=mp.instrument_id,
                serial_number=mp.serial_number,
                calibration_date=mp.calibration_date,
                calibration_due_date=mp.calibration_due_date,
                calibration_reference=mp.calibration_reference,
                measurement_type=mp.measurement_type,
                field_conditions=mp.field_conditions,
            )
        win = tk.Toplevel(self)
        win.title(f"{'Edit' if editing else 'Record'} Measurement — {mp.point_id}")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.columnconfigure(1, weight=1)

        values = {
            "record_id": record.record_id,
            "measured_at": record.measured_at,
            "instrument": record.instrument,
            "instrument_id": record.instrument_id,
            "serial_number": record.serial_number,
            "calibration_date": record.calibration_date,
            "calibration_due_date": record.calibration_due_date,
            "calibration_reference": record.calibration_reference,
            "measurement_type": record.measurement_type,
            "reading_uSv_h": "" if record.reading_uSv_h is None else str(record.reading_uSv_h),
            "background_uSv_h": "" if record.background_uSv_h is None else str(record.background_uSv_h),
            "status": record.status,
        }
        vars_ = {k: tk.StringVar(value=v) for k, v in values.items()}

        measurement_frame = ttk.LabelFrame(win, text="Measurement", padding=8)
        measurement_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        measurement_frame.columnconfigure(1, weight=1)
        instrument_frame = ttk.LabelFrame(win, text="Instrument snapshot", padding=8)
        instrument_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        instrument_frame.columnconfigure(1, weight=1)

        row = 0
        for label, key in (
            ("Record ID", "record_id"),
            ("Measured at (YYYY-MM-DD or ISO date/time)", "measured_at"),
            ("Measurement type", "measurement_type"),
            ("Gross reading (µSv/h)", "reading_uSv_h"),
            ("Background (µSv/h)", "background_uSv_h"),
        ):
            ttk.Label(measurement_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Entry(measurement_frame, textvariable=vars_[key], width=44).grid(row=row, column=1, sticky="ew", pady=3)
            row += 1

        corrected_var = tk.StringVar(value="")
        ttk.Label(measurement_frame, text="Corrected reading").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Label(measurement_frame, textvariable=corrected_var).grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        ttk.Label(measurement_frame, text="Assessment status").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Combobox(
            measurement_frame,
            textvariable=vars_["status"],
            values=("Not assessed", "Pass", "Review", "Fail"),
            state="readonly",
            width=41,
        ).grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        ttk.Label(measurement_frame, text="Field conditions").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
        conditions = tk.Text(measurement_frame, height=3, width=44)
        conditions.insert("1.0", record.field_conditions)
        conditions.grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        ttk.Label(measurement_frame, text="Measurement notes").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
        notes = tk.Text(measurement_frame, height=3, width=44)
        notes.insert("1.0", record.notes)
        notes.grid(row=row, column=1, sticky="ew", pady=3)

        for row, (label, key) in enumerate((
            ("Instrument / make-model", "instrument"),
            ("Instrument ID / asset ID", "instrument_id"),
            ("Serial number", "serial_number"),
            ("Calibration date", "calibration_date"),
            ("Calibration due", "calibration_due_date"),
            ("Calibration certificate/reference", "calibration_reference"),
        )):
            ttk.Label(instrument_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Entry(instrument_frame, textvariable=vars_[key], width=44).grid(row=row, column=1, sticky="ew", pady=3)

        calibration_var = tk.StringVar(value="")
        ttk.Label(instrument_frame, text="Calibration status at measurement").grid(row=6, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Label(instrument_frame, textvariable=calibration_var).grid(row=6, column=1, sticky="w", pady=3)

        def preview(*_):
            try:
                reading = _float_or_none(vars_["reading_uSv_h"].get())
                bg = _float_or_none(vars_["background_uSv_h"].get()) or 0.0
                corrected_var.set("" if reading is None else f"{max(0.0, reading - bg):g} µSv/h")
            except ValueError:
                corrected_var.set("Invalid numeric value")
            probe = MeasurementRecord(
                record_id="_preview",
                measured_at=vars_["measured_at"].get().strip(),
                calibration_due_date=vars_["calibration_due_date"].get().strip(),
            )
            calibration_var.set(probe.calibration_status())

        for key in ("reading_uSv_h", "background_uSv_h", "measured_at", "calibration_due_date"):
            vars_[key].trace_add("write", preview)
        preview()

        button_frame = ttk.Frame(win)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=10)

        def save_record():
            try:
                reading = _float_or_none(vars_["reading_uSv_h"].get())
                background = _float_or_none(vars_["background_uSv_h"].get())
            except ValueError:
                messagebox.showerror("Measurement", "Gross and background readings must be numeric or blank.", parent=win)
                return
            new_record_id = vars_["record_id"].get().strip() or record.record_id or mp.next_record_id()
            if any(other is not record and other.record_id == new_record_id for other in mp.measurement_history):
                messagebox.showerror("Measurement", f"Record ID {new_record_id!r} is already in use at this point.", parent=win)
                return
            record.record_id = new_record_id
            record.measured_at = vars_["measured_at"].get().strip()
            record.instrument = vars_["instrument"].get().strip()
            record.instrument_id = vars_["instrument_id"].get().strip()
            record.serial_number = vars_["serial_number"].get().strip()
            record.calibration_date = vars_["calibration_date"].get().strip()
            record.calibration_due_date = vars_["calibration_due_date"].get().strip()
            record.calibration_reference = vars_["calibration_reference"].get().strip()
            record.measurement_type = vars_["measurement_type"].get().strip() or "Ambient dose rate"
            record.field_conditions = conditions.get("1.0", "end-1c").strip()
            record.reading_uSv_h = reading
            record.background_uSv_h = background
            record.status = vars_["status"].get()
            record.notes = notes.get("1.0", "end-1c").strip()
            record.recalculate()
            if editing:
                if mp.measurement_history and mp.measurement_history[-1] is record:
                    mp.apply_record_as_latest(record)
                self.refresh(select_id=mp.point_id)
                self.app.mark_dirty()
                self.app.floor_tab.redraw()
                self.app.set_status(f"Updated {record.record_id} at {mp.point_id}")
            else:
                self.add_measurement_record(mp.point_id, record)
            win.destroy()

        ttk.Button(button_frame, text="Save measurement", command=save_record).pack(side="right")
        ttk.Button(button_frame, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 6))

    def view_history(self):
        point_id = self._selected_point_id()
        mp = self._point_by_id(point_id)
        if mp is None:
            return
        win = tk.Toplevel(self)
        win.title(f"Measurement History — {mp.point_id}")
        win.transient(self.winfo_toplevel())
        win.geometry("1180x420")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
        cols = ("id", "when", "type", "instrument", "calibration", "gross", "bg", "corrected", "status", "conditions")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        labels = ("Record", "Measured", "Type", "Instrument", "Calibration", "Gross", "BG", "Corrected", "Status", "Field conditions")
        widths = (100, 130, 130, 170, 90, 75, 70, 85, 80, 220)
        for c, label, width in zip(cols, labels, widths):
            tree.heading(c, text=label)
            tree.column(c, width=width, minwidth=55, stretch=c in {"instrument", "conditions"})
        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=10)
        tree.configure(yscrollcommand=sb.set)

        def refill(select_index: int | None = None):
            tree.delete(*tree.get_children())
            for idx, record in enumerate(mp.measurement_history):
                tree.insert("", "end", iid=str(idx), values=(
                    record.record_id,
                    record.measured_at,
                    record.measurement_type,
                    " / ".join(p for p in (record.instrument, record.instrument_id, record.serial_number) if p),
                    record.calibration_status(),
                    self._fmt(record.reading_uSv_h),
                    self._fmt(record.background_uSv_h),
                    self._fmt(record.corrected_uSv_h),
                    record.status,
                    record.field_conditions,
                ))
            if select_index is not None and 0 <= select_index < len(mp.measurement_history):
                tree.selection_set(str(select_index))
                tree.focus(str(select_index))

        def selected_record():
            sel = tree.selection()
            if not sel:
                return None, None
            try:
                idx = int(sel[0])
            except ValueError:
                return None, None
            if not (0 <= idx < len(mp.measurement_history)):
                return None, None
            return idx, mp.measurement_history[idx]

        def add():
            self._edit_record(mp, None)
            win.destroy()

        def edit():
            _idx, record = selected_record()
            if record is None:
                return
            self._edit_record(mp, record)
            win.destroy()

        def delete():
            idx, record = selected_record()
            if record is None:
                return
            if not messagebox.askyesno("Measurement history", f"Delete {record.record_id}?", parent=win):
                return
            del mp.measurement_history[idx]
            mp.sync_latest_from_history()
            self.refresh(select_id=mp.point_id)
            self.app.mark_dirty()
            self.app.floor_tab.redraw()
            refill(min(idx, len(mp.measurement_history) - 1) if mp.measurement_history else None)

        buttons = ttk.Frame(win)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Add measurement…", command=add).pack(side="left")
        ttk.Button(buttons, text="Edit selected…", command=edit).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete selected", command=delete).pack(side="left")
        ttk.Button(buttons, text="Close", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", lambda _e: edit())
        refill()



class RoomSummaryTab(ttk.Frame):
    """Derived room verification and RadStatus-readiness dashboard."""

    ISSUE_COLUMNS = ("severity", "area", "item", "issue")

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        ttk.Label(self, text="Room Verification / Compliance Readiness", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self,
            text=(
                "Derived from the current RadVerify inspection record. This dashboard is a workflow/readiness summary "
                "and is not, by itself, an independent regulatory compliance certification."
            ),
            wraplength=1250,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        header = ttk.Frame(self)
        header.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=1)

        state_box = ttk.LabelFrame(header, text="Overall room state", padding=10)
        state_box.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        readiness_box = ttk.LabelFrame(header, text="RadStatus hand-off", padding=10)
        readiness_box.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.state_var = tk.StringVar(value="Incomplete")
        self.state_label = tk.Label(
            state_box,
            textvariable=self.state_var,
            font=("Bahnschrift", 16, "bold"),
            padx=14,
            pady=8,
            relief="solid",
            bd=1,
        )
        self.state_label.pack(anchor="w")
        self.state_detail_var = tk.StringVar(value="")
        ttk.Label(state_box, textvariable=self.state_detail_var, wraplength=560, justify="left").pack(
            anchor="w", pady=(8, 0)
        )

        self.ready_var = tk.StringVar(value="NOT READY")
        self.ready_label = tk.Label(
            readiness_box,
            textvariable=self.ready_var,
            font=("Bahnschrift", 16, "bold"),
            padx=14,
            pady=8,
            relief="solid",
            bd=1,
        )
        self.ready_label.pack(anchor="w")
        self.ready_detail_var = tk.StringVar(value="")
        ttk.Label(readiness_box, textvariable=self.ready_detail_var, wraplength=560, justify="left").pack(
            anchor="w", pady=(8, 0)
        )

        metrics = ttk.Frame(self)
        metrics.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        for c in range(3):
            metrics.columnconfigure(c, weight=1)

        barrier_frame = ttk.LabelFrame(metrics, text="Barrier verification", padding=9)
        barrier_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        evidence_frame = ttk.LabelFrame(metrics, text="Evidence completeness", padding=9)
        evidence_frame.grid(row=0, column=1, sticky="nsew", padx=4)
        measurement_frame = ttk.LabelFrame(metrics, text="Measurement survey", padding=9)
        measurement_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        self.barrier_metrics_var = tk.StringVar()
        self.evidence_metrics_var = tk.StringVar()
        self.measurement_metrics_var = tk.StringVar()
        ttk.Label(barrier_frame, textvariable=self.barrier_metrics_var, justify="left").pack(anchor="w")
        ttk.Label(evidence_frame, textvariable=self.evidence_metrics_var, justify="left").pack(anchor="w")
        ttk.Label(measurement_frame, textvariable=self.measurement_metrics_var, justify="left").pack(anchor="w")

        issues_frame = ttk.LabelFrame(self, text="Outstanding items", padding=8)
        issues_frame.grid(row=4, column=0, sticky="nsew")
        issues_frame.columnconfigure(0, weight=1)
        issues_frame.rowconfigure(0, weight=1)
        self.issue_tree = ttk.Treeview(
            issues_frame,
            columns=self.ISSUE_COLUMNS,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "severity": "Severity",
            "area": "Area",
            "item": "Item",
            "issue": "Outstanding item",
        }
        widths = {"severity": 95, "area": 110, "item": 130, "issue": 650}
        for column in self.ISSUE_COLUMNS:
            self.issue_tree.heading(column, text=headings[column])
            self.issue_tree.column(column, width=widths[column], minwidth=70, stretch=column == "issue")
        self.issue_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(issues_frame, orient="vertical", command=self.issue_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.issue_tree.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(self)
        buttons.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Refresh summary", command=self.refresh).pack(side="left")
        ttk.Button(buttons, text="Barrier Inspection", command=lambda: self.app.notebook.select(self.app.barrier_tab)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Measurement Points", command=lambda: self.app.notebook.select(self.app.measurement_tab)).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(buttons, text="Export RadStatus payload…", command=self.app.export_radstatus_payload).pack(side="right")

    @staticmethod
    def _state_colours(state: str) -> tuple[str, str]:
        if state == "Verified":
            return COLOUR_PASS, "white"
        if state == "Failed":
            return COLOUR_FAIL, "white"
        if state == "Review required":
            return COLOUR_REVIEW_DARK, "white"
        return "#6b7280", "white"

    def refresh(self):
        summary = self.app.project.verification_summary()
        state = summary["verification_state"]
        self.state_var.set(state)
        background, foreground = self._state_colours(state)
        self.state_label.configure(background=background, foreground=foreground)

        barriers = summary["barriers"]
        measurements = summary["measurements"]
        self.state_detail_var.set(
            f"Barriers: {barriers['pass']} Pass / {barriers['review']} Review / {barriers['fail']} Fail / "
            f"{barriers['not_inspected']} not inspected. Measurements: {measurements['pass']} Pass / "
            f"{measurements['review']} Review / {measurements['fail']} Fail / "
            f"{measurements['not_assessed']} not assessed."
        )

        ready = bool(summary["radstatus_ready"])
        self.ready_var.set("READY FOR RADSTATUS" if ready else "NOT READY FOR RADSTATUS")
        self.ready_label.configure(
            background=COLOUR_PASS if ready else COLOUR_REVIEW_DARK,
            foreground="white",
        )
        self.ready_detail_var.set(
            "The verification dataset is complete enough for RadStatus hand-off. Outcome may still be Review or Fail."
            if ready
            else "Complete the outstanding inspection/evidence/measurement data before RadStatus hand-off."
        )

        self.barrier_metrics_var.set(
            "\n".join((
                f"Applicable barriers: {barriers['applicable']} / {barriers['total']}",
                f"Pass: {barriers['pass']}",
                f"Review: {barriers['review']}",
                f"Fail: {barriers['fail']}",
                f"Not inspected: {barriers['not_inspected']}",
                f"N/A: {barriers['n_a']}",
                f"As-built recorded: {barriers['as_built_complete']} / {barriers['applicable']}",
            ))
        )
        self.evidence_metrics_var.set(
            "\n".join((
                f"Evidence recorded: {barriers['evidence_complete']} / {barriers['applicable']}",
                f"Integrity issues: {barriers['evidence_integrity_issues']}",
                "Reference-only evidence is accepted as recorded evidence.",
            ))
        )
        self.measurement_metrics_var.set(
            "\n".join((
                f"Spatial points: {measurements['points_total']}",
                f"Points with readings: {measurements['points_recorded']}",
                f"Assessed points: {measurements['points_assessed']}",
                f"Calibration current: {measurements['calibration_current']}",
                f"Pass / Review / Fail: {measurements['pass']} / {measurements['review']} / {measurements['fail']}",
                f"Not assessed: {measurements['not_assessed']}",
            ))
        )

        self.issue_tree.delete(*self.issue_tree.get_children())
        for index, issue in enumerate(summary["issues"]):
            self.issue_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(issue["severity"], issue["area"], issue["item_id"], issue["issue"]),
            )
        if not summary["issues"]:
            self.issue_tree.insert("", "end", values=("—", "—", "—", "No outstanding items"))
        return summary
