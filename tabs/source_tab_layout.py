from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from modalities.registry import source_type_options


def build_sources_tab(app) -> None:
    """Build the Sources tab widgets and initialise source-form variables.

    This module owns Sources-tab layout construction. The app object still owns
    the Tk variables and event-handler methods used by existing bindings.
    """
    self = app
    frame = self.sources_tab
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1)

    left = ttk.Frame(frame)
    left.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
    right_shell = ttk.Frame(frame)
    right_shell.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
    right_shell.columnconfigure(0, weight=1)
    right_shell.rowconfigure(0, weight=1)

    self.sources_right_canvas = tk.Canvas(
        right_shell,
        highlightthickness=0,
        borderwidth=0,
    )
    self.sources_right_canvas.grid(row=0, column=0, sticky="nsew")

    self.sources_right_scrollbar = ttk.Scrollbar(
        right_shell,
        orient="vertical",
        command=self.sources_right_canvas.yview,
    )
    self.sources_right_scrollbar.grid(row=0, column=1, sticky="ns")
    self.sources_right_canvas.configure(yscrollcommand=self.sources_right_scrollbar.set)

    right = ttk.Frame(self.sources_right_canvas)
    self.sources_right_content = right
    self.sources_right_window = self.sources_right_canvas.create_window(
        (0, 0),
        window=right,
        anchor="nw",
    )
    right.columnconfigure(0, weight=1)

    def _sync_sources_scrollregion(_event=None) -> None:
        self.sources_right_canvas.configure(
            scrollregion=self.sources_right_canvas.bbox("all")
        )

    def _sync_sources_content_width(event) -> None:
        self.sources_right_canvas.itemconfigure(
            self.sources_right_window,
            width=event.width,
        )

    right.bind("<Configure>", _sync_sources_scrollregion)
    self.sources_right_canvas.bind("<Configure>", _sync_sources_content_width)

    self.sources_room_var = tk.StringVar()
    ttk.Label(left, text="Room").pack(anchor="w")
    self.sources_room_combo = ttk.Combobox(left, textvariable=self.sources_room_var, state="readonly")
    self.sources_room_combo.pack(fill="x")
    self.sources_room_combo.bind("<<ComboboxSelected>>", lambda e: self.on_sources_room_change())
    self.sources_locked_notice_var = tk.StringVar(
        value="Sources are defined in the Geometry tab."
    )
    self.sources_locked_notice_label = ttk.Label(
        left,
        textvariable=self.sources_locked_notice_var,
        wraplength=220,
        foreground="#555555",
        justify="left",
    )
    self.sources_locked_notice_label.pack(fill="x", pady=(6, 4))

    self.sources_list = tk.Listbox(left, width=35)
    self.sources_list.configure(exportselection=False)
    self.sources_list.pack(fill="both", expand=True, pady=8)
    self.sources_list.bind("<<ListboxSelect>>", lambda e: self.load_selected_source())

    self.add_source_button = ttk.Button(left, text="Add Source", state="disabled")
    self.add_source_button.pack(fill="x", pady=4)

    self.delete_source_button = ttk.Button(left, text="Delete Source", state="disabled")
    self.delete_source_button.pack(fill="x", pady=4)

    self.apply_source_button = None

    header = ttk.Frame(right)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)

    self.source_name_var = tk.StringVar()
    self.source_type_var = tk.StringVar()
    self.radiation_type_var = tk.StringVar()
    self.source_name_var.trace_add("write", self.on_source_form_change)
    self.source_type_var.trace_add("write", self.on_source_form_change)

    ttk.Label(header, text="Source Name").grid(row=0, column=0, sticky="w", padx=4, pady=4)
    self.source_name_entry = ttk.Entry(header, textvariable=self.source_name_var)
    self.source_name_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

    ttk.Label(header, text="Source Type").grid(row=1, column=0, sticky="w", padx=4, pady=4)

    self.source_type_combo = ttk.Combobox(
        header,
        textvariable=self.source_type_var,
        state="readonly",
        values=source_type_options(production_only=True),
    )

    self.source_type_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
    self.source_type_combo.bind("<<ComboboxSelected>>", lambda e: self.on_source_type_change())

    ttk.Label(header, text="Radiation Type / TVL Key (auto)").grid(row=2, column=0, sticky="w", padx=4, pady=4)
    self._make_readonly_entry(header, self.radiation_type_var).grid(row=2, column=1, sticky="ew", padx=4, pady=4)

    self.source_form_container = ttk.LabelFrame(right, text="Modality-Defined Source Parameters")
    self.source_form_container.grid(row=1, column=0, sticky="nsew", padx=4, pady=8)
    self.source_form_container.columnconfigure(1, weight=1)

    self.manual_vars = {
        "dose_rate_uSv_h_at_1m": tk.StringVar(),
        "hours_per_week": tk.StringVar(),
    }
    self.primary_vars = {
        "xray_method": tk.StringVar(value="ncrp_simplified"),
        "workload_uSv_per_week_at_1m": tk.StringVar(value="100000"),
        "use_factor": tk.StringVar(value="0.25"),

        "exam_room_type": tk.StringVar(value="general_radiography"),
        "exams_per_week": tk.StringVar(value="100"),
        "tube_potential_kvp": tk.StringVar(value="120"),

        "derived_workload_uSv_per_week_at_1m": tk.StringVar(value=""),
        "derived_use_factor_default": tk.StringVar(value=""),
        "derived_method_note": tk.StringVar(value=""),
    }
    self.ct_vars = {
        "preset": tk.StringVar(value="ct_low_dose"),
        "use_scanner_db": tk.StringVar(value="1"),
        "manual_ksec_override": tk.StringVar(value="0"),
        "scanner_family": tk.StringVar(value=""),
        "scanner_phantom": tk.StringVar(value="body"),
        "scanner_vendor": tk.StringVar(value=""),
        "scanner_model": tk.StringVar(value=""),
        "scanner_kvp": tk.StringVar(value="140"),
        "scanner_source": tk.StringVar(value=""),
        "manual_ksec_entered_by": tk.StringVar(value=""),
        "manual_ksec_reason": tk.StringVar(value=""),
        "manual_ksec_reference": tk.StringVar(value=""),
        "manual_ksec_last_updated": tk.StringVar(value=""),
        "scans_per_week": tk.StringVar(value="60"),
        "ksec_mGy_per_100mAs_at_1m": tk.StringVar(value="0.06"),
        "workload_mAs_per_scan": tk.StringVar(value="630"),
        "tvl_key": tk.StringVar(value="xray_120kvp"),
        "scanner_debug": tk.StringVar(value=""),
    }
    self.ct_resolved_family_var = tk.StringVar(value="")
    self.xray_vars = {
        "preset": tk.StringVar(value="general_room"),
        "exams_per_week": tk.StringVar(),
        "scatter_rate_uSv_h_at_1m": tk.StringVar(),
        "beam_on_time_s_per_exposure": tk.StringVar(),
        "exposures_per_exam": tk.StringVar(),
        "beam_on_time_min_per_exam": tk.StringVar(),
        "tvl_key": tk.StringVar(value="xray_120kvp"),
    }
    self.nm_vars = {
        "radionuclide": tk.StringVar(value="Tc99m"),
        "NMPS_R": tk.StringVar(value="20"),
        "NMPS_S": tk.StringVar(value="20"),
        "NBONE": tk.StringVar(value="40"),
        "AMPS_R": tk.StringVar(value="350"),
        "AMPS_S": tk.StringVar(value="1000"),
        "ABONE": tk.StringVar(value="1000"),
        "tMPS_R": tk.StringVar(value="0.33"),
        "tMPS_S": tk.StringVar(value="0.33"),
        "tBONE": tk.StringVar(value="1.0"),
        "RMPS": tk.StringVar(value="0.0206"),
        "RBONE": tk.StringVar(value="0.0125"),
    }

    for var in (
        list(self.manual_vars.values())
        + list(self.primary_vars.values())
        + list(self.ct_vars.values())
        + list(self.xray_vars.values())
        + list(self.nm_vars.values())
    ):
        var.trace_add("write", self.on_source_input_change)

    self.refresh_source_form_by_type()
    self.refresh_selected_source_resolution(force=True)
    self.source_calc_frame = ttk.LabelFrame(right, text="Live Source Calculations")
    self.source_calc_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=8)
    self.source_calc_text = tk.Text(
        self.source_calc_frame,
        height=24,
        wrap="word",
        background="#f8fafc",
        foreground="#111827",
        font=self.ui_font_mono,
        padx=10,
        pady=8,
        spacing1=2,
        spacing3=3,
    )
    self.source_calc_text.pack(fill="both", expand=True, padx=4, pady=4)
    self._configure_source_calc_text_tags()
    self.ct_vars["scanner_kvp"].trace_add("write", self.on_source_selector_energy_change)
