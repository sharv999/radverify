from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from services.scanner_database import ScannerDatabase
from services.ct_source_display import build_ct_source_display_state_from_source
from services.ct_scanner_resolution import (
    canonical_ct_vendor_label,
    default_ct_phantom_for_family,
    friendly_ct_model_name,
)

from geometry.geometry_model import RoomGeometry, Opening, WallBucky, BuckyShield, ControlWall
from geometry.control_wall_collision import point_on_control_wall, source_path_crosses_control_wall
from geometry.room_defaults import get_standard_construction_for_material
from geometry.geometry_canvas import GeometryCanvas
from geometry.pet_preview_overlay import draw_pet_geometry_preview_overlay
from geometry.spect_preview_overlay import draw_spect_geometry_preview_overlay

from config.geometry_constants import *
from config.ui_constants import *
from config.material_constants import *
from geometry.opening_controller import OpeningControllerMixin
from geometry.scanner_renderer import ScannerRendererMixin
from geometry.source_sync import SourceSyncMixin
from geometry.geometry_nudge import GeometryNudgeMixin
from geometry.barrier_sync import BarrierSyncMixin, safe_refresh_barrier_schedule

from modalities.registry import (
    ct_ksec_source_types,
    geometry_ui_for_modality,
    layout_rendering_for_modality,
    default_source_type_for_modality,
    source_label_for_type,
    source_type_for_modality_role,
    get_modality_plugin,
)
from services.calculation_display_state import room_calculation_display_state
from tabs.results_barrier_maps import (
    get_barrier_dose_label_map,
    get_barrier_risk_map,
)

class GeometryTab(ttk.Frame, OpeningControllerMixin, ScannerRendererMixin, SourceSyncMixin, BarrierSyncMixin, GeometryNudgeMixin):

    def __init__(self, master, app, on_change=None):
        super().__init__(master)

        self.app = app
        self.on_change = on_change
        self.geometry: RoomGeometry | None = None
        self._loading = False
        self.selected_opening_var = tk.StringVar(value="")
        self._opening_loading = False
        self._redraw_pending = False
        self.scanner_db = self._create_scanner_database()

        self._build_ui()
        self.refresh_room_list()


    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.source_type_var = tk.StringVar(value="CT")
        self.source_option_var = tk.StringVar(value="")
        self.scanner_ksec_var = tk.StringVar(value="")
        self.scanner_ksec_energy_var = tk.StringVar(value="")
        self._scanner_display_to_family: dict[str, str] = {}

        left_shell = ttk.Frame(self)
        left_shell.grid(row=0, column=0, sticky="ns")

        left_canvas = tk.Canvas(
            left_shell,
            width=330,
            highlightthickness=0,
            bg=COLOUR_PANEL_BG if "COLOUR_PANEL_BG" in globals() else None,
        )

        left_scrollbar = ttk.Scrollbar(
            left_shell,
            orient="vertical",
            command=left_canvas.yview,
        )

        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.grid(row=0, column=0, sticky="ns")
        left_scrollbar.grid(row=0, column=1, sticky="ns")

        left_shell.rowconfigure(0, weight=1)

        left = ttk.Frame(left_canvas, padding=10)
        left_window = left_canvas.create_window(
            (0, 0),
            window=left,
            anchor="nw",
        )

        def _on_left_configure(event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        def _on_canvas_configure(event):
            left_canvas.itemconfigure(left_window, width=event.width)

        left.bind("<Configure>", _on_left_configure)
        left_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left_canvas.bind("<Enter>", lambda e: left_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        left_canvas.bind("<Leave>", lambda e: left_canvas.unbind_all("<MouseWheel>"))

        right = ttk.Frame(self, padding=10)
        right.grid(row=0, column=1, sticky="nsew")

        self.canvas = GeometryCanvas(right)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.request_redraw())

        self.room_select_var = tk.StringVar()
        self.room_name_var = tk.StringVar()
        self.source_label_var = tk.StringVar(value="CT")
        self.source_info_var = tk.StringVar(value="")
        self.scanner_rotation_var = tk.IntVar(value=0)

        self.length_var = tk.DoubleVar(value=DEFAULT_ROOM_LENGTH_M)
        self.width_var = tk.DoubleVar(value=DEFAULT_ROOM_WIDTH_M)
        self.height_var = tk.DoubleVar(value=DEFAULT_ROOM_HEIGHT_M)

        self.source_x_var = tk.DoubleVar(value=DEFAULT_SOURCE_X_M)
        self.source_y_var = tk.DoubleVar(value=DEFAULT_SOURCE_Y_M)
        self.xray_bucky_wall_var = tk.StringVar(value="N")
        self.xray_bucky_offset_var = tk.DoubleVar(value=1.0)
        self.xray_control_x_var = tk.DoubleVar(value=1.0)
        self.xray_control_y_var = tk.DoubleVar(value=1.0)
        self.xray_control_length_var = tk.DoubleVar(value=1.5)
        self.xray_control_nib_length_var = tk.DoubleVar(value=0.75)
        self.xray_control_material_var = tk.StringVar(value="Pb")
        self.xray_control_thickness_var = tk.StringVar(value="0.88")
        self.xray_control_t_var = tk.StringVar(value="1.0")
        self.xray_control_p_var = tk.StringVar(value="100 µSv/wk")
        self.xray_control_orientation_var = tk.StringVar(value="0")

        row = 0
        ttk.Label(left, text="Room Geometry", style="Heading.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        row = self._field(left, row, "Room name", self.room_name_var, readonly=True)

        row = self._nudge_field(
            left,
            row,
           "Length S-N (m)",
            self.length_var,
            lambda: self.nudge_room_dimension("length", -0.1),
            lambda: self.nudge_room_dimension("length", 0.1),
        )

        row = self._nudge_field(
            left,
            row,
            "Width W-E (m)",
            self.width_var,
            lambda: self.nudge_room_dimension("width", -0.1),
            lambda: self.nudge_room_dimension("width", 0.1),
        )

        row = self._nudge_field(
            left,
            row,
            "Height (m)",
            self.height_var,
            lambda: self.nudge_room_dimension("height", -0.1),
            lambda: self.nudge_room_dimension("height", 0.1),
        )

        ttk.Separator(left).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(left, text="Source", style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        # Room modality is owned by the Project tab in the single-room workflow.
        # ``source_type_var`` remains as a hidden compatibility/state value for
        # existing source-sync helpers, but Geometry no longer exposes a second
        # modality selector.
        self.source_option_label = ttk.Label(left, text="Scanner / config")
        self.source_option_label.grid(row=row, column=0, sticky="w", pady=2)
        self.source_option_combo = ttk.Combobox(
            left,
            textvariable=self.source_option_var,
            values=[],
            width=16,
            state="readonly",
        )
        self.source_option_combo.grid(row=row, column=1, sticky="ew", pady=2)
        self.source_option_combo.bind("<<ComboboxSelected>>", self.on_geometry_scanner_changed)
        row += 1

        self.scanner_ksec_label = ttk.Label(left, text="ksec")
        self.scanner_ksec_label.grid(row=row, column=0, sticky="w", pady=2)
        self.scanner_ksec_value_label = ttk.Label(
            left,
            textvariable=self.scanner_ksec_var,
            width=19,
            wraplength=150,
        )
        self.scanner_ksec_value_label.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        self.scanner_ksec_energy_label = ttk.Label(left, text="ksec energy")
        self.scanner_ksec_energy_label.grid(row=row, column=0, sticky="w", pady=2)
        self.scanner_ksec_energy_value_label = ttk.Label(
            left,
            textvariable=self.scanner_ksec_energy_var,
            width=19,
            wraplength=150,
        )
        self.scanner_ksec_energy_value_label.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        row = self._field(left, row, "Source label", self.source_label_var)

        self.source_info_label = ttk.Label(left, text="")
        self.source_info_label.grid(row=row, column=0, sticky="w", pady=2)
        self.source_info_value_label = ttk.Label(
            left,
            textvariable=self.source_info_var,
            width=19,
            wraplength=150,
        )
        self.source_info_value_label.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        row = self._nudge_field(
            left,
            row,
            "From West wall (m)",
            self.source_x_var,
            lambda: self.nudge_source_position("x", -0.1),
            lambda: self.nudge_source_position("x", 0.1),
        )

        row = self._nudge_field(
            left,
            row,
            "From South wall (m)",
            self.source_y_var,
            lambda: self.nudge_source_position("y", -0.1),
            lambda: self.nudge_source_position("y", 0.1),
        )

        self.rotate_scanner_button = ttk.Button(
            left,
            text="Rotate scanner 90° CW",
            command=self.rotate_scanner_cw,
        )
        self.rotate_scanner_button.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        row += 1

        # General Radiography controls stand alone as two peer panels.  There is
        # deliberately no redundant outer "General Radiography geometry" frame.
        self.xray_chest_bucky_frame = ttk.LabelFrame(left, text="Chest Bucky", padding=5)
        chest_bucky_frame = self.xray_chest_bucky_frame
        chest_bucky_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 3))
        chest_bucky_frame.columnconfigure(1, weight=1)
        ttk.Label(chest_bucky_frame, text="Wall").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(chest_bucky_frame, textvariable=self.xray_bucky_wall_var, values=["E", "W"], state="readonly", width=12).grid(row=0, column=1, sticky="ew", pady=2)
        self._nudge_field(
            chest_bucky_frame, 1, "Distance along wall (m)", self.xray_bucky_offset_var,
            lambda: self.nudge_xray_chest_bucky(-0.1), lambda: self.nudge_xray_chest_bucky(0.1),
        )
        ttk.Button(chest_bucky_frame, text="Add / update chest bucky", command=self.add_or_update_xray_chest_receptor).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(3,2))
        ttk.Button(chest_bucky_frame, text="Remove chest bucky", command=self.remove_xray_chest_bucky).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2,0))

        row += 1
        self.xray_control_wall_frame = ttk.LabelFrame(left, text="Control Wall", padding=5)
        control_wall_frame = self.xray_control_wall_frame
        control_wall_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(3, 4))
        control_wall_frame.columnconfigure(1, weight=1)
        self._nudge_field(
            control_wall_frame, 0, "From West wall (m)", self.xray_control_x_var,
            lambda: self.nudge_xray_control_wall("x", -0.1), lambda: self.nudge_xray_control_wall("x", 0.1),
        )
        self._nudge_field(
            control_wall_frame, 1, "From North wall (m)", self.xray_control_y_var,
            lambda: self.nudge_xray_control_wall("north", -0.1), lambda: self.nudge_xray_control_wall("north", 0.1),
        )
        ttk.Label(control_wall_frame, text="Control wall length (m)").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(control_wall_frame, textvariable=self.xray_control_length_var).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(control_wall_frame, text="Nib length (m)").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(control_wall_frame, textvariable=self.xray_control_nib_length_var).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(control_wall_frame, text="Material").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Combobox(control_wall_frame, textvariable=self.xray_control_material_var, values=["Pb", "Concrete"], state="readonly").grid(row=4, column=1, sticky="ew", pady=2)
        ttk.Label(control_wall_frame, text="Thickness (mm)").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(control_wall_frame, textvariable=self.xray_control_thickness_var).grid(row=5, column=1, sticky="ew", pady=2)
        ttk.Label(control_wall_frame, text="T").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Combobox(control_wall_frame, textvariable=self.xray_control_t_var, values=NCRP_147_T_VALUES, state="readonly").grid(row=6, column=1, sticky="ew", pady=2)
        ttk.Label(control_wall_frame, text="P (Design dose)").grid(row=7, column=0, sticky="w", pady=2)
        ttk.Combobox(control_wall_frame, textvariable=self.xray_control_p_var, values=["10 µSv/wk", "20 µSv/wk", "50 µSv/wk", "100 µSv/wk"], state="readonly").grid(row=7, column=1, sticky="ew", pady=2)
        ttk.Button(control_wall_frame, text="Rotate control wall 90° CW", command=self.rotate_xray_control_wall_cw).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(3,2))
        ttk.Button(control_wall_frame, text="Add / update control wall", command=self.add_or_update_xray_control_wall).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(2,2))
        ttk.Button(control_wall_frame, text="Remove control wall", command=self.remove_xray_control_wall).grid(row=10, column=0, columnspan=2, sticky="ew", pady=2)
        row += 1

        ttk.Separator(left).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(2, 4),
        )
        row += 1

        ttk.Label(left, text="Barrier", style="Section.TLabel").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(2, 4),
        )
        row += 1

        self.barrier_wall_var = tk.StringVar(value="N")
        self.barrier_material_var = tk.StringVar(value="Pb")
        self.barrier_thickness_var = tk.StringVar(value="0.88")
        self.barrier_t_var = tk.StringVar(value="0.2")
        self.barrier_distance_var = tk.StringVar(value="")

        row = self._combo(left, row, "Barrier", self.barrier_wall_var, ["N", "E", "S", "W", "Floor", "Ceiling"])
        row = self._combo(left, row, "Material", self.barrier_material_var, ["Pb", "Concrete", "Pb glass"])

        ttk.Label(left, text="Thickness (mm)").grid(row=row, column=0, sticky="w", pady=2)
        self.barrier_thickness_combo = ttk.Combobox(
            left,
            textvariable=self.barrier_thickness_var,
            values=STANDARD_PB_THICKNESSES_MM,
            state="readonly",
        )
        self.barrier_thickness_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(left, text="T").grid(row=row, column=0, sticky="w", pady=2)
        self.barrier_t_combo = ttk.Combobox(
            left,
            textvariable=self.barrier_t_var,
            values=NCRP_147_T_VALUES,
            state="readonly",
            width=16,
        )
        self.barrier_t_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # --- P (Design dose constraint) ---
        ttk.Label(left, text="P (Design dose)").grid(row=row, column=0, sticky="w")

        self.p_var = tk.StringVar(value="10 µSv/wk")

        self.p_combo = ttk.Combobox(
            left,
            textvariable=self.p_var,
            values=["10 µSv/wk", "20 µSv/wk", "50 µSv/wk", "100 µSv/wk"],
            state="readonly",
            width=18,
        )
        self.p_combo.grid(row=row, column=1, sticky="ew")
        self.p_combo.bind("<<ComboboxSelected>>", self.on_p_changed)
        row += 1

        # Read-only annual equivalent of the selected weekly design dose.
        # This is presentation-only: the canonical barrier design goal remains
        # the weekly P value stored on the barrier.
        ttk.Label(left, text="Annual design dose (µSv/yr)").grid(
            row=row, column=0, sticky="w", pady=2
        )
        self.annual_p_var = tk.StringVar(value="520")
        self.annual_p_entry = ttk.Entry(
            left,
            textvariable=self.annual_p_var,
            width=19,
            state="readonly",
        )
        self.annual_p_entry.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        self.p_var.trace_add("write", lambda *_: self._update_annual_design_dose_display())
        self._update_annual_design_dose_display()

        ttk.Label(left, text="Distance (m)").grid(row=row, column=0, sticky="w", pady=2)

        self.barrier_distance_entry = ttk.Entry(
            left,
            textvariable=self.barrier_distance_var,
            width=19,
        )
        self.barrier_distance_entry.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8
        )
        row += 1

        ttk.Label(left, text="Openings", style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        ttk.Label(left, text="Selected opening").grid(row=row, column=0, sticky="w", pady=2)

        self.opening_select_combo = ttk.Combobox(
            left,
            textvariable=self.selected_opening_var,
            values=[],
            state="readonly",
        )
        self.opening_select_combo.grid(row=row, column=1, sticky="ew", pady=2)
        self.opening_select_combo.bind("<<ComboboxSelected>>", self.load_selected_opening_into_fields)
        row += 1

        self.opening_wall_var = tk.StringVar(value="N")
        self.opening_type_var = tk.StringVar(value="door")
        self.opening_offset_var = tk.DoubleVar(value=1.0)
        self.opening_width_var = tk.DoubleVar(value=0.9)
        self.opening_pb_var = tk.StringVar(value="0.88")
        self.opening_pb_var.trace_add("write", self.update_current_opening_thickness)
        self.opening_material_var = tk.StringVar(value="Pb")

        ttk.Label(left, text="Wall").grid(row=row, column=0, sticky="w", pady=3)
        self.opening_wall_combo = ttk.Combobox(
            left,
            textvariable=self.opening_wall_var,
            values=["N", "E", "S", "W"],
            width=19,
            state="readonly",
        )
        self.opening_wall_combo.grid(row=row, column=1, sticky="ew", pady=3)
        self.opening_wall_combo.bind("<<ComboboxSelected>>", self.on_opening_selector_field_change)
        row += 1

        ttk.Label(left, text="Type").grid(row=row, column=0, sticky="w", pady=3)
        self.opening_type_combo = ttk.Combobox(
            left,
            textvariable=self.opening_type_var,
            values=["Door", "Viewing Panel"],
            width=19,
            state="readonly",
        )
        self.opening_type_combo.grid(row=row, column=1, sticky="ew", pady=3)
        self.opening_type_combo.bind("<<ComboboxSelected>>", self.on_opening_selector_field_change)
        row += 1

        ttk.Label(left, text="Material").grid(row=row, column=0, sticky="w", pady=2)
        self.opening_material_combo = ttk.Combobox(
            left,
            textvariable=self.opening_material_var,
            values=self._opening_material_values("door"),
            state="readonly",
        )
        self.opening_material_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(left, text="Distance along wall (m)").grid(row=row, column=0, sticky="w", pady=2)

        offset_frame = ttk.Frame(left)
        offset_frame.grid(row=row, column=1, sticky="ew", pady=2)
        offset_frame.columnconfigure(1, weight=1)

        ttk.Button(
            offset_frame,
            text="-",
            width=3,
            command=lambda: self.nudge_opening_offset(-0.1),
        ).grid(row=0, column=0, padx=(0, 2))

        ttk.Entry(
            offset_frame,
            textvariable=self.opening_offset_var,
            width=8,
        ).grid(row=0, column=1, sticky="ew")

        ttk.Button(
            offset_frame,
            text="+",
            width=3,
            command=lambda: self.nudge_opening_offset(0.1),
        ).grid(row=0, column=2, padx=(2, 0))
        row += 1

        row = self._field(left, row, "Width (m)", self.opening_width_var)

        ttk.Label(left, text="Thickness (mm)").grid(row=row, column=0, sticky="w", pady=2)
        self.opening_pb_combo = ttk.Combobox(
            left,
            textvariable=self.opening_pb_var,
            values=STANDARD_PB_THICKNESSES_MM,
            state="readonly",
        )
        self.opening_pb_combo.grid(row=row, column=1, sticky="ew", pady=2)
        self.opening_pb_combo.bind("<<ComboboxSelected>>", self.update_current_opening_thickness)
        row += 1

        self.opening_type_var.trace_add("write", lambda *_: self.on_opening_type_changed())
        self.opening_material_var.trace_add(
            "write",
            lambda *_: self.on_opening_selector_field_change()
        )
        self.source_type_var.trace_add("write", lambda *_: self.update_source_options())
        self.source_option_var.trace_add("write", lambda *_: self.safe_live_update())
        self.barrier_wall_var.trace_add("write", lambda *_: self.load_selected_barrier_fields())

        self.barrier_material_var.trace_add("write", self.on_barrier_material_changed)
        self.barrier_thickness_var.trace_add("write", self.on_barrier_field_change)
        self.barrier_t_var.trace_add("write", self.on_barrier_field_change)
        self.barrier_distance_var.trace_add("write", self.on_barrier_field_change)
        self.xray_control_material_var.trace_add("write", self.on_xray_control_material_changed)
        for control_var in (
            self.xray_control_x_var, self.xray_control_y_var,
            self.xray_control_length_var, self.xray_control_nib_length_var,
            self.xray_control_thickness_var, self.xray_control_t_var,
            self.xray_control_p_var,
        ):
            control_var.trace_add("write", self.on_xray_control_field_changed)

        # ADD OPENING BUTTON
        ttk.Button(left, text="Add opening", command=self.add_opening).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4
        )
        self.opening_material_combo.bind("<<ComboboxSelected>>", self.on_opening_selector_field_change)
        self.opening_pb_combo.bind("<<ComboboxSelected>>", self.on_opening_selector_field_change)
        row += 1

        ttk.Button(left, text="Clear openings", command=self.clear_openings).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4
        )

        for var in [
            self.length_var,
            self.width_var,
            self.height_var,
            self.source_label_var,
            self.source_x_var,
            self.source_y_var,
        ]:
            var.trace_add("write", lambda *_: self.safe_live_update())

        self.update_source_options()


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

    def _create_scanner_database(self) -> ScannerDatabase:
        project_root = Path(__file__).resolve().parents[1]
        database_path = project_root / "data" / "ct" / "ct_scatter_master_database.json"
        return ScannerDatabase(database_path)


    def _scanner_records_for_source_type(self, source_type_label: str):
        geometry_ui = geometry_ui_for_modality(source_type_label)
        if geometry_ui.selector_kind != "ct_scanner_database":
            return []
        return self.scanner_db.list_scanners(
            include_null_ksec=True,
            metadata_group=geometry_ui.scanner_metadata_group,
        )


    def _scanner_display_value(self, scanner) -> str:
        return scanner.short_name


    def _format_ksec_energy_basis(self, value) -> str:
        try:
            if value in (None, "", "NULL", "null", "None"):
                return ""
            return f"{float(value):g} kVp"
        except Exception:
            text = str(value or "").strip()
            return text if text.lower().endswith("kvp") else (f"{text} kVp" if text else "")


    def _scanner_database_ksec_energy(self, scanner) -> str:
        for attr in ("ksec_energy_kvp", "energy_kvp", "scanner_kvp"):
            try:
                value = getattr(scanner, attr)
            except Exception:
                value = None
            formatted = self._format_ksec_energy_basis(value)
            if formatted:
                return formatted
        return ""


    def _selected_scanner_ksec_energy_fallback(self, selected_family_id: str = "") -> str:
        """
        Best-effort fallback for the Geometry tab ksec energy label.

        Source params are preferred, but immediately after adding this field to
        older projects the selected Source may not yet contain ksec_energy_kvp.
        In that case use the live Sources-tab variables if they correspond to
        the same scanner family, then fall back to the scanner database, then
        finally the app-level scanner kVp.
        """
        selected_family_id = str(selected_family_id or "").strip()

        try:
            ct_vars = getattr(self.app, "ct_vars", {}) or {}
            source_family = str(ct_vars.get("scanner_family").get()).strip() if ct_vars.get("scanner_family") else ""
            if not selected_family_id or not source_family or source_family == selected_family_id:
                for key in ("ksec_energy_kvp", "scanner_kvp"):
                    var = ct_vars.get(key)
                    if var is None:
                        continue
                    formatted = self._format_ksec_energy_basis(var.get())
                    if formatted:
                        return formatted
        except Exception:
            pass

        if selected_family_id:
            try:
                scanner = self.scanner_db.get_scanner(selected_family_id)
                formatted = self._scanner_database_ksec_energy(scanner)
                if formatted:
                    return formatted
            except Exception:
                pass

        try:
            return self._format_ksec_energy_basis(getattr(self.app, "global_energy_var").get().replace("kVp", ""))
        except Exception:
            return ""


    def _set_scanner_ksec_energy_from_params(self, params: dict, fallback: str = "") -> None:
        params = params or {}
        value = (
            params.get("ksec_energy_kvp", None)
            or params.get("scanner_kvp", None)
            or fallback
        )
        formatted = self._format_ksec_energy_basis(value)
        self.scanner_ksec_energy_var.set(formatted or "not specified")



    def _update_scanner_ksec_label(self, scanner=None) -> None:
        """
        Display Geometry ksec status.

        Source params are authoritative for the selected room because manual
        overrides live on the source model, not in the scanner database. This
        prevents Geometry from continuing to show NULL after a valid manual
        override has been entered in the Sources tab.
        """
        try:
            from services.ksec_status import resolve_ksec_status
        except Exception:
            resolve_ksec_status = None

        selected = self.source_option_var.get().strip()
        selected_family_id = self._scanner_display_to_family.get(selected, selected)
        room = self.get_selected_room()

        # 1. Prefer current room source params. This is the only place where a
        # user-entered manual override/audit trail exists.
        if room and resolve_ksec_status is not None:
            try:
                sources = list(self.app.get_sources_for_room(room.name))
            except Exception:
                sources = list(getattr(room, "sources", []) or [])

            for src in sources:
                if str(getattr(src, "source_type", "") or "").strip() not in (
                    "ct_scatter",
                    "spect_ct_secondary_scatter",
                ):
                    continue

                params = getattr(src, "params", {}) or {}
                source_family = str(params.get("scanner_family", "") or "").strip()

                display_state = build_ct_source_display_state_from_source(
                    src,
                    fallback_energy_kvp=self._selected_scanner_ksec_energy_fallback(selected_family_id),
                )

                # A documented manual override on the current room source is
                # authoritative for the Geometry ksec label. Do not fall back
                # to the scanner database just because the Geometry combobox
                # display text does not map cleanly to the stored family key.
                if display_state.is_manual_override and display_state.ksec_display:
                    self.scanner_ksec_var.set(display_state.ksec_display)
                    self.scanner_ksec_energy_var.set(display_state.ksec_energy_display)
                    return

                # For non-manual sources, avoid showing a ksec from an
                # unrelated/stale scanner source.
                if selected_family_id and source_family and source_family != selected_family_id:
                    continue

                if display_state.ksec_display:
                    self.scanner_ksec_var.set(display_state.ksec_display)
                    self.scanner_ksec_energy_var.set(display_state.ksec_energy_display)
                    return

                break

        # 2. Fallback to scanner database only if source params are unavailable.
        if scanner is None:
            try:
                scanner = self.scanner_db.get_scanner(selected_family_id)
            except Exception:
                self.scanner_ksec_var.set("")
                self.scanner_ksec_energy_var.set("")
                return

        if getattr(scanner, "requires_manual_ksec", False):
            self.scanner_ksec_var.set("NULL — manual override\nrequired")
        else:
            self.scanner_ksec_var.set(f"{scanner.ksec_display} mGy/100 mAs @ 1 m")

        energy = (
            self._scanner_database_ksec_energy(scanner)
            or self._selected_scanner_ksec_energy_fallback(selected_family_id)
        )
        self.scanner_ksec_energy_var.set(energy or "not specified")


    def _default_vendor_for_source_type(self, source_type: str) -> str:
        vendors = self.app._ct_scatter_vendor_values_for_source_type(source_type)
        return vendors[0] if vendors else ""


    def _field(self, parent, row, label, variable, readonly=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        state = "readonly" if readonly else "normal"
        ttk.Entry(parent, textvariable=variable, width=19, state=state).grid(
            row=row, column=1, sticky="ew", pady=3
        )
        return row + 1


    def _nudge_field(self, parent, row, label, variable, minus_command, plus_command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)

        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)

        ttk.Button(frame, text="-", width=3, command=minus_command).grid(row=0, column=0, padx=(0, 2))

        ttk.Entry(frame, textvariable=variable, width=8).grid(row=0, column=1, sticky="ew")

        ttk.Button(frame, text="+", width=3, command=plus_command).grid(row=0, column=2, padx=(2, 0))

        return row + 1


    def _section_label(self, parent, row, text, pady=(12, 4)):
        ttk.Label(parent, text=text, style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=pady
        )
        return row + 1


    def _combo(self, parent, row, label, variable, values):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            width=19,
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=3)
        return row + 1

# ---------------------------------------------------------
# FUNCTIONS
# ---------------------------------------------------------

    def _update_annual_design_dose_display(self) -> None:
        """Display the annual equivalent of the selected weekly design dose."""
        try:
            weekly_text = str(self.p_var.get() or "").strip()
            weekly_uSv = float(weekly_text.split()[0])
            annual_uSv = weekly_uSv * 52.0
            text = f"{annual_uSv:g}"
        except Exception:
            text = ""

        if hasattr(self, "annual_p_var"):
            self.annual_p_var.set(text)


    def refresh_room_list(self, preferred_room_name: str | None = None):
        """Refresh Geometry from the project's sole room.

        ``room_select_var`` is retained as a non-visible compatibility value for
        existing synchronisation helpers, but Geometry no longer exposes a room
        selector because a project contains exactly one room.
        """
        rooms = list(getattr(self.app.project, "rooms", []) or [])

        if not rooms:
            self.geometry = None
            self.room_select_var.set("")
            self.canvas.delete("all")
            return

        room = rooms[0]
        self.room_select_var.set(str(getattr(room, "name", "") or ""))
        self.load_selected_room_geometry()


    def ensure_room_geometry(self, room):
        if not getattr(room, "geometry", None):
            room.geometry = self.app.create_default_room_geometry(room.name, room.modality)

        room.geometry.room_name = room.name

        if not getattr(room.geometry.source, "label", ""):
            room.geometry.source.label = room.modality or "Source"

        return room.geometry


    def _canonical_vendor_for_scanner(self, scanner) -> str:
        vendor = str(getattr(scanner, "vendor", "") or "").strip()
        try:
            return canonical_ct_vendor_label(self.app.ct_scanner_resolution_context, vendor)
        except Exception:
            return vendor


    def _friendly_model_for_scanner(self, scanner) -> str:
        try:
            friendly = friendly_ct_model_name(
                self.app.ct_scanner_resolution_context,
                scanner.family_id,
            )
            if friendly:
                return friendly
        except Exception:
            pass

        vendor = self._canonical_vendor_for_scanner(scanner)
        short_name = str(getattr(scanner, "short_name", "") or "").strip()
        return f"{vendor} {short_name}".strip()



    def _set_geometry_source_label_from_scanner(self, room, scanner) -> None:
        """Keep the Geometry left-panel Source label aligned with the selected scanner."""
        try:
            model_label = self._friendly_model_for_scanner(scanner)
        except Exception:
            model_label = ""

        if not model_label:
            return

        try:
            self.source_label_var.set(model_label)
        except Exception:
            pass

        try:
            if getattr(room, "geometry", None) is not None and getattr(room.geometry, "source", None) is not None:
                room.geometry.source.label = model_label
        except Exception:
            pass


    def _scanner_phantom_for_family(self, family_id: str) -> str:
        try:
            return default_ct_phantom_for_family(
                self.app.ct_scanner_resolution_context,
                family_id,
            )
        except Exception:
            return "body"


    def _apply_scanner_record_to_source(self, src, scanner, source_type: str) -> None:
        """
        Apply the Geometry-tab scanner selection to a Source object.

        This is deliberately centralised because both project.sources and
        room.sources may contain CT-like source objects. If only one container is
        updated, app.enforce_room_source_types() can accidentally resurrect the
        stale scanner from the other container.
        """
        if src is None:
            return

        src.source_type = source_type

        try:
            src.name = self.app._canonical_source_name_for_type(source_type)
        except Exception:
            pass

        if not isinstance(getattr(src, "params", None), dict):
            src.params = {}

        vendor = self._canonical_vendor_for_scanner(scanner)
        model = self._friendly_model_for_scanner(scanner)
        family_id = scanner.family_id

        src.params["preset"] = src.params.get("preset", "ct_low_dose")
        src.params["use_scanner_db"] = "1"
        src.params["scanner_family"] = family_id
        src.params["scanner_vendor"] = vendor
        src.params["scanner_model"] = model
        src.params["scanner_phantom"] = self._scanner_phantom_for_family(family_id)
        src.params["scanner_modality_class"] = scanner.modality_class
        src.params["ksec_definition"] = scanner.ksec_definition
        src.params["ksec_confidence"] = scanner.ksec_confidence
        src.params["ksec_reference_distance_m"] = scanner.ksec_reference_distance_m

        # Preserve workload fields if already present.
        src.params["scans_per_week"] = src.params.get("scans_per_week", 60)
        src.params["workload_mAs_per_scan"] = src.params.get("workload_mAs_per_scan", 630)
        src.params["scanner_kvp"] = src.params.get("scanner_kvp", 140)

        if scanner.ksec_mGy_per_100mAs_at_1m is None:
            # Critical: do not leave the previous scanner's ksec in place.
            # Use a blank string rather than None so Tkinter entries show blank,
            # not the literal text "None".
            src.params["ksec_mGy_per_100mAs_at_1m"] = ""
            src.params["scanner_source"] = f"NULL ksec — manual override required ({family_id})"
            src.params["scanner_ksec_status"] = "manual_override_required"
            # This is not a manual override yet. It only becomes "1" after
            # the user enters a manual ksec in the Sources tab.
            src.params["manual_ksec_override"] = "0"
        else:
            src.params["ksec_mGy_per_100mAs_at_1m"] = float(scanner.ksec_mGy_per_100mAs_at_1m)
            src.params["scanner_source"] = (
                scanner.source_document_display
                if scanner.source_document_display != "—"
                else f"JSON worst-case Ksec lookup ({family_id})"
            )
            src.params["scanner_ksec_status"] = "database"
            src.params["manual_ksec_override"] = "0"


    def _sync_geometry_scanner_to_room_sources(self, room, scanner, source_type: str) -> None:
        """
        Keep project-level and room-level source stores in agreement.

        The app currently maintains both project.sources and room.sources in
        some workflows. app.enforce_room_source_types() examines both, so stale
        room.sources can overwrite the new Geometry scanner selection unless
        both containers are repaired.
        """
        ct_like = set(ct_ksec_source_types())

        touched = []

        # Project-level source objects.
        for src in list(getattr(self.app.project, "sources", []) or []):
            if str(getattr(src, "room_name", "") or "").strip() != room.name:
                continue
            if str(getattr(src, "source_type", "") or "") in ct_like:
                self._apply_scanner_record_to_source(src, scanner, source_type)
                src.room_name = room.name
                touched.append(src)

        # Room-level source objects.
        for src in list(getattr(room, "sources", []) or []):
            if str(getattr(src, "source_type", "") or "") in ct_like:
                self._apply_scanner_record_to_source(src, scanner, source_type)
                src.room_name = room.name
                touched.append(src)

        # If no CT-like source exists yet, create one.
        if not touched:
            try:
                src = self.app._default_source_for_type(
                    source_type,
                    self.app._canonical_source_name_for_type(source_type),
                )
            except Exception:
                return

            src.room_name = room.name
            self._apply_scanner_record_to_source(src, scanner, source_type)

            if not hasattr(self.app.project, "sources") or self.app.project.sources is None:
                self.app.project.sources = []
            self.app.project.sources.append(src)
            room.sources = [src]
            touched.append(src)


    def on_geometry_scanner_changed(self, event=None):
        room = self.get_selected_room()
        if not room:
            return

        selected_model = self.source_option_var.get().strip()
        if not selected_model:
            self.scanner_ksec_var.set("")
            return

        family_id = self._scanner_display_to_family.get(selected_model, selected_model)

        try:
            scanner = self.scanner_db.get_scanner(family_id)
        except Exception:
            self.scanner_ksec_var.set("scanner not found")
            return

        self._update_scanner_ksec_label(scanner)

        selected_modality = self.source_type_var.get().strip()
        geometry_ui = geometry_ui_for_modality(selected_modality)
        source_type = source_type_for_modality_role(
            selected_modality,
            geometry_ui.primary_source_role,
        )
        if not source_type:
            return

        # First update both project.sources and room.sources so stale copies
        # cannot win during enforce_room_source_types().
        self._sync_geometry_scanner_to_room_sources(room, scanner, source_type)

        # Let the app repair the source inventory, then immediately re-apply
        # the selected scanner to the enforced CT-like source. This avoids any
        # normalisation/default path reintroducing an old scanner or old ksec.
        try:
            self.app.enforce_room_source_types(room)
        except Exception:
            pass

        self._sync_geometry_scanner_to_room_sources(room, scanner, source_type)

        try:
            if hasattr(self.app, "sources_room_var"):
                self.app.sources_room_var.set(room.name)

            self.app.current_source_index = 0
            self.app.last_selected_source_index = 0
            self.app.last_selected_source_room_name = room.name

            self.app.refresh_sources_list(preserve_index=0)
            self.app._reload_source_ui_from_model(room, 0, refresh_live=True)

            # Reloading the Sources form may normalise params. Refresh the
            # Geometry label after that so NULL/manual status is shown accurately.
            self._update_scanner_ksec_label(scanner)

        except Exception as exc:
            print(f"Geometry -> Sources scanner sync failed: {exc}")

        try:
            safe_refresh_barrier_schedule(self.app)
        except Exception:
            pass

        # Re-load from canonical room state after the refresh. This keeps the
        # selected Floor/Ceiling controls aligned with exactly what the canvas
        # and result model are using.
        try:
            self.load_selected_barrier_fields()
        except Exception:
            pass

        try:
            self.app.refresh_results_tab()
        except Exception:
            pass

        # Final left-panel refresh: source reloads and result refreshes can
        # touch source/geometry state. Re-apply the scanner label at the end so
        # the Geometry Source label cannot remain stale after a dropdown change.
        self._set_geometry_source_label_from_scanner(room, scanner)

        self.request_redraw()


    def load_selected_room_geometry(self):
        room = self.get_selected_room()
        if not room:
            return

        self._loading = True
        try:
            self.geometry = self.ensure_room_geometry(room)

            if hasattr(self.app, "sources_room_var"):
                self.app.sources_room_var.set(room.name)
            if hasattr(self.app, "barriers_room_var"):
                self.app.barriers_room_var.set(room.name)

            # Load saved model values into Geometry UI BEFORE any live update can fire
            self.refresh_from_model()
            self.load_selected_barrier_fields()

           # Load source/scanner UI while still protected
            self.load_source_from_project(room)
            self.load_scanner_from_room_source(room)

            # If this is a new/default project with an incomplete CT source
            # model, commit the visible default scanner once. Valid existing
            # sources and manual ksec overrides remain authoritative.
            try:
                self.initialise_missing_ct_source_from_geometry_selection(room)
            except Exception:
                pass

            # Source params are authoritative on room load. Do not call
            # on_geometry_scanner_changed() here, because that would re-resolve the
            # scanner database and may overwrite or mask a saved manual CT ksec override.
            try:
                self._update_scanner_ksec_label()
            except Exception:
                pass

        finally:
            self._loading = False

        self.request_redraw()
        self.refresh_opening_selector()

        if callable(self.on_change):
            self.on_change()


    def draw_room_with_risk(self):
        if not self.geometry:
            return

        g = self.geometry
        g.clamp_source_inside_room()
        # self._clamp_ct_scanner_inside_room()

        for opening in getattr(g, "openings", []) or []:
            self._clamp_opening_to_wall(opening)

        # --- 1. Draw base room (single source of truth for scale) ---
        self.canvas.delete("all")

        room = self.get_selected_room()

        # Fallback: after edits in the Barriers tab, the app-level selected room
        # may be fresher than GeometryTab's local selection/cache.
        try:
            app_room = self.app.get_selected_room()
            if app_room is not None:
                room = app_room
                self.geometry = getattr(app_room, "geometry", self.geometry)
                g = self.geometry
        except Exception:
            pass

        wall_material_labels = {}
        wall_thickness_mm_by_wall = {}
        wall_p_values = {}
        wall_distance_values = {}
        wall_role_labels = {}

        def barrier_canvas_key(barrier) -> str | None:
            name = str(getattr(barrier, "name", "") or "").strip().lower()
            role = str(getattr(barrier, "barrier_role", "") or "").strip().lower()

            if name in {"n wall", "north wall"} or name.startswith("n "):
                return "N"
            if name in {"e wall", "east wall"} or name.startswith("e "):
                return "E"
            if name in {"s wall", "south wall"} or name.startswith("s "):
                return "S"
            if name in {"w wall", "west wall"} or name.startswith("w "):
                return "W"

            if name in {"floor", "floor barrier", "floor slab"} or role == "floor":
                return "Floor"

            if name in {"ceiling", "ceiling barrier", "ceiling slab"} or role == "ceiling":
                return "Ceiling"

            return None


        if room:
            for b in getattr(room, "barriers", []) or []:
                key = barrier_canvas_key(b)
                if not key:
                    continue

                material = str(getattr(b, "material", "") or "").strip()
                thickness = getattr(b, "thickness_mm", None)
                p_val = getattr(b, "design_goal_uSv_per_week", None)
                distance_val = getattr(b, "distance_m", None)

                if material:
                    try:
                        thickness_val = float(thickness)
                        if thickness_val > 0:
                            label = f"{material} {thickness_val:.2f} mm"
                        else:
                            label = material
                    except Exception:
                        label = material

                    wall_material_labels[key] = label

                try:
                    wall_thickness_mm_by_wall[key] = float(thickness)
                except Exception:
                    pass

                try:
                    wall_p_values[key] = float(p_val)
                except Exception:
                    wall_p_values[key] = 10.0

                try:
                    wall_distance_values[key] = float(distance_val)
                except Exception:
                    pass

                if str(getattr(room, "modality", "") or "").upper() == "X-RAY":
                    role = str(getattr(b, "barrier_role", "") or "")
                    role_names = {
                        "fig52_chest_bucky_wall": "PRIMARY — chest bucky",
                        "fig52_cross_table_wall": "PRIMARY + SECONDARY — cross-table",
                        "fig52_secondary_wall": "SECONDARY",
                        "fig52_control_wall": "SECONDARY — control wall",
                        "fig52_door": "SECONDARY — door",
                        "fig52_darkroom_wall": "SECONDARY — darkroom",
                        "fig52_floor_under_table": "PRIMARY + SECONDARY — floor",
                        "fig52_ceiling": "SECONDARY — ceiling",
                    }
                    if role in role_names:
                        wall_role_labels[key] = role_names[role]

        g.wall_material_labels = wall_material_labels
        g.wall_thickness_mm_by_wall = wall_thickness_mm_by_wall
        g.wall_p_values = wall_p_values
        g.wall_distance_values = wall_distance_values
        g.wall_role_labels = wall_role_labels

        room = self.get_selected_room()
        calculation_display_state = room_calculation_display_state(self.app, room) if room else None

        if room and not calculation_display_state.blocking:
            g.barrier_risk_map = get_barrier_risk_map(self.app, room.name)
            g.barrier_dose_label_map = get_barrier_dose_label_map(self.app, room.name)
        else:
            g.barrier_risk_map = {}
            g.barrier_dose_label_map = {}

        if room and hasattr(self, "sync_geometry_source_metadata_from_project_source"):
            try:
                self.sync_geometry_source_metadata_from_project_source(room)
            except Exception:
                pass

        layout_rendering = layout_rendering_for_modality(getattr(room, "modality", "") if room else "").as_dict()
        self.canvas.draw_room(
            g,
            wall_t_values=self._wall_t_values_for_canvas(room),
            layout_rendering=layout_rendering,
        )

        risk_map = getattr(g, "barrier_risk_map", {}) or {}

        def colour(barrier_name):
            state = str(risk_map.get(barrier_name, "pass")).lower()
            if state == "fail":
                return COLOUR_FAIL
            if state == "review":
                return COLOUR_REVIEW_DARK
            return COLOUR_PASS

        # --- 2. Find the actual drawn room rectangle (no re-scaling!) ---
        room_items = self.canvas.find_withtag("room_outline")

        if not room_items:
            return

        room_bbox = self.canvas.bbox(room_items[0])

        if not room_bbox:
            return

        x0, y0, x1, y1 = room_bbox

        # Preview overlays are modality-local. The modality plugin declares which
        # preview overlay, if any, belongs on this canvas; stale preview state
        # from another modality is explicitly suppressed.
        preview_overlay_kind = str(layout_rendering.get("preview_overlay_kind", "") or "").strip().lower()
        draw_pet_geometry_preview_overlay(
            self.canvas,
            g,
            room_bbox,
            getattr(self.app, "pet_preview_geometry_overlay", None) if preview_overlay_kind == "pet" else None,
            layout_rendering,
        )
        draw_spect_geometry_preview_overlay(
            self.canvas,
            g,
            room_bbox,
            getattr(self.app, "spect_preview_geometry_overlay", None) if preview_overlay_kind == "spect" else None,
            layout_rendering,
        )

        if calculation_display_state is not None and calculation_display_state.blocking:
            if str(layout_rendering.get("source_symbol_kind", "")) == "ct_scanner":
                self._draw_equipment_symbol(g, room_bbox, layout_rendering)
            self.canvas.create_text(
                (x0 + x1) / 2,
                max(12, y0 - 14),
                text=calculation_display_state.message,
                fill=COLOUR_FAIL,
                font=("TkDefaultFont", 10, "bold"),
                anchor="s",
                tags=("calculation_blocked_message",),
            )
            return

        # --- 3. Overlay coloured walls exactly on top of base room ---
        self.canvas.create_line(x0, y0, x1, y0, fill=colour("N wall"), width=BARRIER_OVERLAY_WIDTH)
        self.canvas.create_line(x1, y0, x1, y1, fill=colour("E wall"), width=BARRIER_OVERLAY_WIDTH)
        self.canvas.create_line(x0, y1, x1, y1, fill=colour("S wall"), width=BARRIER_OVERLAY_WIDTH)
        self.canvas.create_line(x0, y0, x0, y1, fill=colour("W wall"), width=BARRIER_OVERLAY_WIDTH)

        self.canvas.tag_raise("opening")
        self.canvas.tag_raise("opening_label")

        if str(layout_rendering.get("source_symbol_kind", "")) == "ct_scanner":
            self._draw_equipment_symbol(g, room_bbox, layout_rendering)


    def add_or_update_xray_chest_receptor(self):
        room = self.get_selected_room()
        if room is None or str(getattr(room, "modality", "") or "").upper() != "X-RAY":
            return
        wall_design = self._snapshot_parent_wall_design_fields()
        g = self.ensure_room_geometry(room)
        wall = self.xray_bucky_wall_var.get().strip().upper() or "W"
        if wall not in {"E", "W"}:
            raise ValueError("GXR chest bucky must be on the E or W wall")
        offset = max(0.0, float(self.xray_bucky_offset_var.get()))
        wall_len = g.width_m if wall in {"N", "S"} else g.length_m
        offset = min(offset, wall_len)
        if g.wall_bucky is None:
            g.wall_bucky = WallBucky(wall=wall, offset_m=offset)
        else:
            g.wall_bucky.wall = wall
            g.wall_bucky.offset_m = offset
        # XR-19A: every Chest Bucky owns a deterministic 1.2 m wide, 2.2 mm Pb
        # Bucky Shield centred behind it.  Geometry only: no attenuation credit yet.
        g.bucky_shield = BuckyShield(wall=wall, offset_m=offset)
        self.app._apply_geometry_to_selected_room_barriers(room)
        self._restore_parent_wall_design_fields(wall_design)
        if callable(self.on_change): self.on_change()
        self.draw_room_with_risk()

    def nudge_xray_chest_bucky(self, delta_m):
        room = self.get_selected_room()
        if room is None:
            return
        g = self.ensure_room_geometry(room)
        wall = self.xray_bucky_wall_var.get().strip().upper() or "W"
        if wall not in {"E", "W"}:
            raise ValueError("GXR chest bucky must be on the E or W wall")
        wall_len = g.width_m if wall in {"N", "S"} else g.length_m
        value = min(max(float(self.xray_bucky_offset_var.get()) + float(delta_m), 0.0), wall_len)
        self.xray_bucky_offset_var.set(round(value, 2))
        self.add_or_update_xray_chest_receptor()

    def remove_xray_chest_bucky(self):
        room = self.get_selected_room()
        if room is None or str(getattr(room, "modality", "") or "").upper() != "X-RAY":
            return
        wall_design = self._snapshot_parent_wall_design_fields()
        g = self.ensure_room_geometry(room)
        g.wall_bucky = None
        g.bucky_shield = None
        self.app._apply_geometry_to_selected_room_barriers(room)
        self._restore_parent_wall_design_fields(wall_design)
        if callable(self.on_change): self.on_change()
        self.draw_room_with_risk()

    def nudge_xray_control_wall(self, axis, delta_m):
        room = self.get_selected_room()
        if room is None:
            return
        g = self.ensure_room_geometry(room)
        var = self.xray_control_x_var if axis == "x" else self.xray_control_y_var
        limit = g.width_m if axis == "x" else g.length_m
        value = min(max(float(var.get()) + float(delta_m), 0.0), limit)
        var.set(round(value, 2))
        if getattr(g, "control_wall", None) is not None:
            self.add_or_update_xray_control_wall()

    def rotate_xray_control_wall_cw(self):
        """Rotate the pending/existing GXR control wall by 90 degrees clockwise."""
        try:
            current = int(float(self.xray_control_orientation_var.get() or 0)) % 360
        except (TypeError, ValueError):
            current = 0
        next_orientation = (current + 90) % 360
        self.xray_control_orientation_var.set(str(next_orientation))
        room = self.get_selected_room()
        if room is not None:
            g = self.ensure_room_geometry(room)
            if getattr(g, "control_wall", None) is not None:
                self.add_or_update_xray_control_wall()

    def add_or_update_xray_control_wall(self):
        room = self.get_selected_room()
        if room is None or str(getattr(room, "modality", "") or "").upper() != "X-RAY":
            return
        wall_design = self._snapshot_parent_wall_design_fields()
        g = self.ensure_room_geometry(room)
        is_new_control_wall = getattr(g, "control_wall", None) is None
        if is_new_control_wall:
            self._loading = True
            try:
                self.xray_control_material_var.set("Pb")
                self.xray_control_thickness_var.set("0.88")
                self.xray_control_t_var.set("1.0")
                self.xray_control_p_var.set("100 µSv/wk")
            finally:
                self._loading = False
        x = min(max(float(self.xray_control_x_var.get()), 0.0), g.width_m)
        north_distance = min(max(float(self.xray_control_y_var.get()), 0.0), g.length_m)
        y = g.length_m - north_distance
        length = max(0.1, float(self.xray_control_length_var.get()))
        nib_length = max(0.0, float(self.xray_control_nib_length_var.get()))
        try:
            orientation = int(float(self.xray_control_orientation_var.get() or 0)) % 360
        except (TypeError, ValueError):
            orientation = 0
        material = str(self.xray_control_material_var.get() or "Pb")
        thickness = max(0.0, float(self.xray_control_thickness_var.get()))
        occupancy = max(0.0, min(1.0, float(self.xray_control_t_var.get())))
        p_text = str(self.xray_control_p_var.get() or "100 µSv/wk")
        design_goal = max(0.0, float(p_text.split()[0]))
        proposed_wall = ControlWall(
            center_x_m=x, center_y_m=y, length_m=length, orientation_deg=orientation,
            nib_length_m=nib_length, material=material, thickness_mm=thickness,
            occupancy_factor=occupancy, design_goal_uSv_per_week=design_goal,
        )
        source_point = (float(g.source.x_m), float(g.source.y_m))
        if point_on_control_wall(source_point, proposed_wall):
            self._source_control_wall_warning = "Control Wall update blocked — wall intersects X-ray source."
            if hasattr(self.app, "set_status"):
                self.app.set_status(self._source_control_wall_warning)
            self._loading = True
            try:
                if g.control_wall is not None:
                    self.xray_control_x_var.set(g.control_wall.center_x_m)
                    self.xray_control_y_var.set(round(g.length_m - g.control_wall.center_y_m, 2))
                    self.xray_control_length_var.set(g.control_wall.length_m)
                    self.xray_control_nib_length_var.set(g.control_wall.nib_length_m)
                    self.xray_control_orientation_var.set(str(g.control_wall.orientation_deg))
            finally:
                self._loading = False
            return
        g.control_wall = proposed_wall
        self.app._apply_geometry_to_selected_room_barriers(room)
        self._restore_parent_wall_design_fields(wall_design)
        if callable(self.on_change): self.on_change()
        self.draw_room_with_risk()

    def remove_xray_control_wall(self):
        room = self.get_selected_room()
        if room is None or str(getattr(room, "modality", "") or "").upper() != "X-RAY":
            return
        wall_design = self._snapshot_parent_wall_design_fields()
        g = self.ensure_room_geometry(room)
        g.control_wall = None
        room.barriers = [b for b in room.barriers if str(getattr(b, "barrier_role", "") or "") != "fig52_control_wall"]
        self._loading = True
        try:
            self.xray_control_material_var.set("Pb")
            self.xray_control_thickness_var.set("0.88")
            self.xray_control_t_var.set("1.0")
            self.xray_control_p_var.set("100 µSv/wk")
        finally:
            self._loading = False
        self.app._apply_geometry_to_selected_room_barriers(room)
        self._restore_parent_wall_design_fields(wall_design)
        if callable(self.on_change): self.on_change()
        self.draw_room_with_risk()


    def refresh_from_model(self):
        if not self.geometry:
            return

        g = self.geometry
        g.clamp_source_inside_room()
        # self._clamp_ct_scanner_inside_room()

        self._loading = True
        try:
            self.room_name_var.set(g.room_name)
            self.length_var.set(g.length_m)
            self.width_var.set(g.width_m)
            self.height_var.set(g.height_m)
            self.source_label_var.set(g.source.label)
            self.source_x_var.set(g.source.x_m)
            self.source_y_var.set(g.source.y_m)
            self.scanner_rotation_var.set(
                int(getattr(g.source, "rotation_deg", DEFAULT_SCANNER_ROTATION_DEG) or DEFAULT_SCANNER_ROTATION_DEG)
            )
            if getattr(g, "wall_bucky", None) is not None:
                self.xray_bucky_wall_var.set(g.wall_bucky.wall)
                self.xray_bucky_offset_var.set(g.wall_bucky.offset_m)
            if getattr(g, "control_wall", None) is not None:
                self.xray_control_x_var.set(g.control_wall.center_x_m)
                self.xray_control_y_var.set(round(g.length_m - g.control_wall.center_y_m, 2))
                self.xray_control_length_var.set(g.control_wall.length_m)
                self.xray_control_nib_length_var.set(getattr(g.control_wall, "nib_length_m", 0.75))
                self.xray_control_material_var.set(getattr(g.control_wall, "material", "Pb"))
                self.xray_control_thickness_var.set(str(getattr(g.control_wall, "thickness_mm", 0.88)))
                self.xray_control_t_var.set(str(getattr(g.control_wall, "occupancy_factor", 1.0)))
                self.xray_control_p_var.set(f'{float(getattr(g.control_wall, "design_goal_uSv_per_week", 100.0)):g} µSv/wk')
                self.xray_control_orientation_var.set(str(int(g.control_wall.orientation_deg) % 360))
            else:
                # A room without a persisted Control Wall starts from the
                # qualified standard construction, never stale controls from
                # the previously selected room.
                self.xray_control_material_var.set("Pb")
                self.xray_control_thickness_var.set("0.88")
                self.xray_control_t_var.set("1.0")
                self.xray_control_p_var.set("100 µSv/wk")
        finally:
            self._loading = False

        self.request_redraw()
        self.refresh_opening_selector()


    def on_barrier_material_changed(self, *_):
        """Apply the standard construction when the user selects a material."""
        if getattr(self, "_loading", False):
            return
        _material, thickness = get_standard_construction_for_material(
            self.barrier_material_var.get()
        )
        self.barrier_thickness_var.set(f"{thickness:g}")
        self.on_barrier_field_change()

    def on_xray_control_material_changed(self, *_):
        """Keep the GXR control-wall material/thickness pair physically sensible."""
        if getattr(self, "_loading", False):
            return
        _material, thickness = get_standard_construction_for_material(
            self.xray_control_material_var.get()
        )
        self.xray_control_thickness_var.set(f"{thickness:g}")
        self.on_xray_control_field_changed()

    def on_xray_control_field_changed(self, *_):
        """Live-apply valid Control Wall edits so risk colour follows inputs."""
        if getattr(self, "_loading", False) or getattr(self, "_control_wall_live_update", False):
            return
        room = self.get_selected_room()
        if room is None or str(getattr(room, "modality", "") or "").upper() != "X-RAY":
            return
        g = self.ensure_room_geometry(room)
        if getattr(g, "control_wall", None) is None:
            return
        self._control_wall_live_update = True
        try:
            # Entry variables pass through transient invalid states while the
            # user types; wait for the next valid value rather than disrupting
            # editing or replacing the last valid persisted construction.
            self.add_or_update_xray_control_wall()
        except (TypeError, ValueError):
            return
        finally:
            self._control_wall_live_update = False

    def on_barrier_field_change(self, *_):
        """Commit Geometry-tab barrier controls to room.barriers and redraw."""
        if getattr(self, "_loading", False):
            return
        if getattr(self, "_opening_loading", False):
            return

        room = self.get_selected_room()
        if room is None:
            return

        # Commit only the selected barrier fields directly.
        # Do not rely on the full geometry update path here.
        try:
            self.apply_barrier_fields_to_room(room)
        except Exception as e:
            print("BARRIER FIELD APPLY FAILED:", e)
            return

        # Keep read-only Barriers tab and Results tab in sync.
        try:
            safe_refresh_barrier_schedule(self.app)
        except Exception:
            pass

        try:
            self.app.refresh_results_tab()
        except Exception:
            pass

        # Direct barrier-field edits intentionally bypass the full geometry
        # sync guard. Refresh the canonical non-production PET barrier preview
        # here as well so material/thickness/T edits are visible immediately.
        try:
            from tabs.pet_preview_panel import refresh_pet_barrier_results_preview

            refresh_pet_barrier_results_preview(self.app, room=room)
        except Exception:
            # PET preview must never interfere with normal Geometry editing.
            pass

        # Redraw the Geometry canvas from the updated room.barriers.
        try:
            self.draw_room_with_risk()
        except Exception as e:
            print("BARRIER FIELD REDRAW FAILED:", e)


    def safe_live_update(self):
        if self._loading:
            return
        try:
            self.update_model_from_fields(show_errors=False)
        except Exception:
            pass


    def update_model_from_fields(self, show_errors=True):
        if self._loading:
            return

        room = self.get_selected_room()
        if not room:
            return

        try:
            g = self.ensure_room_geometry(room)

            g.room_name = room.name
            g.length_m = float(self.length_var.get())
            g.width_m = float(self.width_var.get())
            g.height_m = float(self.height_var.get())
            g.source.label = self.source_label_var.get().strip() or room.modality or "Source"
            proposed_x = float(self.source_x_var.get())
            proposed_y = float(self.source_y_var.get())
            if str(getattr(room, "modality", "") or "").upper() == "X-RAY" and g.control_wall is not None:
                start = (float(g.source.x_m), float(g.source.y_m))
                end = (min(max(proposed_x, 0.0), g.width_m), min(max(proposed_y, 0.0), g.length_m))
                if source_path_crosses_control_wall(start, end, g.control_wall):
                    self._loading = True
                    try:
                        self.source_x_var.set(start[0])
                        self.source_y_var.set(start[1])
                    finally:
                        self._loading = False
                    self._source_control_wall_warning = "Source movement blocked — cannot cross Control Wall."
                    if hasattr(self.app, "set_status"):
                        self.app.set_status(self._source_control_wall_warning)
                    return
            g.source.x_m = proposed_x
            g.source.y_m = proposed_y
            is_gxr = (str(getattr(room, "modality", "") or "").upper() == "X-RAY"
                      and self.source_option_var.get().strip() == "General Radiography")
            g.source.rotation_deg = (0 if is_gxr else
                int(self.scanner_rotation_var.get() or DEFAULT_SCANNER_ROTATION_DEG) % 360)
            g.clamp_source_inside_room()
            # self._clamp_ct_scanner_inside_room()

            self.geometry = g

            self._loading = True
            try:
                self.source_x_var.set(g.source.x_m)
                self.source_y_var.set(g.source.y_m)
            finally:
                self._loading = False

            # 1. Geometry owns source/scanner
            self.apply_geometry_source_to_project(room)

            # 2. Ensure N/E/S/W barriers exist and distances are updated
            self.app._apply_geometry_to_selected_room_barriers(room)

            # 3. Barrier construction/T/P are committed only by their own
            # barrier-field callbacks. Generic geometry/opening updates must not
            # write whatever values happen to be visible in the Barrier editor
            # back into the model (XR-20E).

            # 4. Refresh app state/results
            if callable(self.on_change):
                self.on_change()

            self.request_redraw()

        except Exception as exc:
            if show_errors:
                messagebox.showerror("Geometry error", str(exc))


    def _opening_material_values(self, opening_type: str) -> list[str]:
        otype = str(opening_type or "").strip().lower()

        if otype in {"viewing panel", "viewing_panel"}:
            return ["Pb glass"]

        return [
            "Pb",
            "Solid timber + Pb",
            "Steel + Pb",
            "Fire door + Pb",
        ]


    def _default_opening_material(self, opening_type: str) -> str:
        otype = str(opening_type or "").strip().lower()
        return "Pb glass" if otype in {"viewing panel", "viewing_panel"} else "Pb"


    def on_opening_type_changed(self):
        if not hasattr(self, "opening_material_combo"):
            return

        otype_ui = self.opening_type_var.get().strip().lower()

        otype = "door" if otype_ui == "door" else "viewing_panel"

        values = self._opening_material_values(otype)
        self.opening_material_combo["values"] = values

        if self.opening_material_var.get() not in values:
            self.opening_material_var.set(values[0] if values else "")

        # Sensible defaults for new openings. Do not overwrite user edits if
        # they have already entered a non-default Pb value.
        try:
            current_pb = float(self.opening_pb_var.get())
        except Exception:
            current_pb = 0.0

        if str(otype).strip().lower() in {"lead_glass", "viewing_panel", "vp", "pb_glass"}:
            if current_pb in (0.0, 0, 0.88, 2.2):
                self.opening_pb_var.set(2.20)
        else:
            if current_pb in (0.0, 2.2):
                self.opening_pb_var.set(0.88)

        self.safe_live_update()


    def _update_source_control_visibility(self, geometry_ui) -> None:
        """Show only source controls declared by the selected modality.

        ``selector_kind`` is the modality-neutral contract: ``none`` hides
        the selector row, while ``ct_scanner_database`` also enables the
        CT-only ksec metadata rows.
        """
        selector_kind = str(getattr(geometry_ui, "selector_kind", "none") or "none").strip()
        show_selector = selector_kind != "none"
        show_ct_ksec = selector_kind == "ct_scanner_database"

        for widget in (self.source_option_label, self.source_option_combo):
            widget.grid() if show_selector else widget.grid_remove()

        for widget in (
            self.scanner_ksec_label,
            self.scanner_ksec_value_label,
            self.scanner_ksec_energy_label,
            self.scanner_ksec_energy_value_label,
        ):
            widget.grid() if show_ct_ksec else widget.grid_remove()

        # Only CT scanners rotate. The GXR table/tube is fixed with its
        # tube north of the table and the beam directed south.
        if hasattr(self, "rotate_scanner_button"):
            if show_ct_ksec:
                self.rotate_scanner_button.configure(text="Rotate scanner 90° CW")
                self.rotate_scanner_button.grid()
            else:
                self.rotate_scanner_button.grid_remove()

        if not show_selector:
            self.source_option_var.set("")
        if not show_ct_ksec:
            self.scanner_ksec_var.set("")
            self.scanner_ksec_energy_var.set("")

        info_label = str(getattr(geometry_ui, "source_info_label", "") or "").strip()
        show_source_info = bool(info_label and getattr(geometry_ui, "source_info_param_key", ""))
        if hasattr(self, "source_info_label"):
            self.source_info_label.configure(text=info_label)
            self.source_info_label.grid() if show_source_info else self.source_info_label.grid_remove()
        if hasattr(self, "source_info_value_label"):
            self.source_info_value_label.grid() if show_source_info else self.source_info_value_label.grid_remove()
        if not show_source_info and hasattr(self, "source_info_var"):
            self.source_info_var.set("")

        if hasattr(self, "xray_chest_bucky_frame"):
            # GeometryUISpec.source_label is the canvas/equipment label ("X-ray"),
            # not the static room-type selector value ("General Radiography").
            # Gate both standalone GXR panels on modality plus room type.
            modality_id = self.source_type_var.get().strip()
            room_type = self.source_option_var.get().strip()
            show_xray_geometry = (
                modality_id.upper() == "X-RAY"
                and room_type == "General Radiography"
            )
            for frame in (self.xray_chest_bucky_frame, self.xray_control_wall_frame):
                frame.grid() if show_xray_geometry else frame.grid_remove()


    def _update_source_info_value(self, room=None, geometry_ui=None) -> None:
        """Populate plugin-declared read-only source metadata for Geometry."""
        if geometry_ui is None:
            geometry_ui = geometry_ui_for_modality(self.source_type_var.get().strip())
        key = str(getattr(geometry_ui, "source_info_param_key", "") or "").strip()
        if not key:
            self.source_info_var.set("")
            return
        if room is None:
            room = self.get_selected_room()
        if room is None:
            self.source_info_var.set("")
            return

        try:
            plugin = get_modality_plugin(str(getattr(room, "modality", "") or "").strip())
            params = plugin.geometry_live_source_params(room) if plugin is not None else {}
        except Exception:
            params = {}

        value = params.get(key) if isinstance(params, dict) else None
        try:
            value_text = f"{float(value):g}"
        except (TypeError, ValueError):
            value_text = str(value or "").strip()
        unit = str(getattr(geometry_ui, "source_info_unit", "") or "").strip()
        self.source_info_var.set(f"{value_text} {unit}".strip() if value_text else "")


    def update_source_options(self):
        if not hasattr(self, "source_option_combo"):
            return

        modality_id = self.source_type_var.get().strip()
        geometry_ui = geometry_ui_for_modality(modality_id)

        # A source label belongs to the selected modality, not to the room that
        # happened to be active before the switch. In particular, a CT scanner
        # model must not survive into PET/SPECT as the patient-source label.
        # Preserve saved/custom labels while loading an existing room; only a
        # live modality transition receives the new modality's canonical label.
        previous_modality = getattr(self, "_source_label_modality_id", modality_id)
        if not self._loading and previous_modality != modality_id:
            default_source_type = default_source_type_for_modality(modality_id)
            canonical_label = source_label_for_type(default_source_type)
            self.source_label_var.set(canonical_label)
            try:
                room = self.get_selected_room()
                geometry_source = getattr(getattr(room, "geometry", None), "source", None)
                if geometry_source is not None:
                    geometry_source.label = canonical_label
            except Exception:
                pass
        self._source_label_modality_id = modality_id

        self._update_source_control_visibility(geometry_ui)
        if hasattr(self, "_update_source_info_value"):
            self._update_source_info_value(geometry_ui=geometry_ui)
        self._scanner_display_to_family = {}

        if geometry_ui.selector_kind == "ct_scanner_database":
            scanners = self._scanner_records_for_source_type(modality_id)
            options = []
            for scanner in scanners:
                display = self._scanner_display_value(scanner)
                options.append(display)
                self._scanner_display_to_family[display] = scanner.family_id
        else:
            options = list(geometry_ui.static_options)
            self.scanner_ksec_var.set("")

        self.source_option_combo["values"] = options

        if options and self.source_option_var.get() not in options:
            self.source_option_var.set(options[0])

        if geometry_ui.selector_kind == "ct_scanner_database" and self.source_option_var.get() in options:
            self._update_scanner_ksec_label()

        if not self._loading and geometry_ui.selector_kind == "ct_scanner_database":
            self.on_geometry_scanner_changed()

    def get_selected_room(self):
        """Return the project's sole room. Geometry has no room selector."""
        rooms = list(getattr(getattr(self.app, "project", None), "rooms", []) or [])
        return rooms[0] if rooms else None


    def opening_display_id(self, opening, index: int) -> str:
        otype = str(getattr(opening, "opening_type", "") or "").strip().lower()
        prefix = "VP" if otype in {"viewing_panel", "lead_glass", "vp", "pb_glass"} else "D"

        explicit = str(getattr(opening, "id", "") or "").strip()
        if explicit:
            return explicit

        return f"{prefix}{index}"


    def on_opening_selector_field_change(self, event=None):
        if self._opening_loading:
            return

        self.refresh_opening_material_combo()
        self.update_selected_opening_from_fields()
        self.refresh_opening_selector()




    def refresh_after_opening_edit(self):
        if callable(self.on_change):
            self.on_change()

        try:
            safe_refresh_barrier_schedule(self.app)
        except Exception:
            pass

        try:
            self.app.refresh_results_tab()
        except Exception:
            pass

        self.request_redraw()


    def request_redraw(self):
        if self._redraw_pending:
            return

        self._redraw_pending = True

        def _do():
            self._redraw_pending = False
            self.draw_room_with_risk()

        self.after_idle(_do)
