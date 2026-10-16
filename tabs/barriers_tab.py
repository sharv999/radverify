import tkinter as tk
from tkinter import ttk

from engine.shielding_engine import SOLVER_MODE_OPTIONS
from tabs.barrier_risk_ui import (
    on_barrier_table_leave,
    on_barrier_table_motion,
)

class BarrierInlineEditor(ttk.Entry):
    def __init__(self, parent, app, item_id, column_name, initial_value):
        self.var = tk.StringVar(value=str(initial_value))
        super().__init__(parent, textvariable=self.var)
        self.app = app
        self.item_id = item_id
        self.column_name = column_name

        self.bind("<Return>", self.save)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", self.save)

        self.focus_set()
        self.select_range(0, "end")

    def save(self, event=None):
        try:
            from tabs.barriers_tab_actions import save_inline_barrier_edit

            save_inline_barrier_edit(
                self.app,
                item_id,
                column_name,
                raw_value,
                apply_preset=apply_preset,
            )
        finally:
            self.destroy()


def _on_barriers_solver_selected(app):
    """Apply a user solver choice only when the selected modality permits it."""
    combo = getattr(app, "barriers_solver_combo", None)
    if combo is None or str(combo.cget("state")) != "readonly":
        return
    values = tuple(combo.cget("values") or ())
    if len(values) <= 1:
        return
    value = str(getattr(app, "barriers_solver_display_var").get() or "").strip()
    if value:
        app.solver_mode_var.set(value)
    app.refresh_barrier_schedule()


def build_barriers_tab(app):
    frame = app.barriers_tab
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    top = ttk.Frame(frame)
    top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
    top.columnconfigure(5, weight=0)

    app.barriers_room_var = tk.StringVar()

    ttk.Label(top, text="Room").grid(row=0, column=0, sticky="w", padx=4)

    app.barriers_room_combo = ttk.Combobox(
        top,
        textvariable=app.barriers_room_var,
        state="readonly",
    )
    app.barriers_room_combo.grid(row=0, column=1, sticky="ew", padx=4)
    app.barriers_room_combo.bind(
        "<<ComboboxSelected>>",
        lambda e: app.refresh_barrier_schedule(),
    )

    ttk.Label(
        top,
        text="Barriers are generated from Geometry. Edit room dimensions/source position in the Geometry tab.",
        foreground="#555555",
    ).grid(row=0, column=2, columnspan=3, sticky="w", padx=8)

    # Keep global_energy_var for existing calculation/report paths, but do not
    # expose it as an editable dropdown for CT. CT source strength is governed by
    # the selected scanner ksec and its ksec_energy_kvp basis.
    app.global_energy_var = tk.StringVar(value="140 kVp")
    app.results_energy_basis_var = tk.StringVar(value="")
    app.barriers_solver_display_var = tk.StringVar(value="")

    ttk.Label(top, text="Energy basis").grid(
        row=1,
        column=0,
        sticky="w",
        padx=4,
        pady=(6, 0),
    )

    ttk.Entry(
        top,
        textvariable=app.results_energy_basis_var,
        state="readonly",
        width=34,
    ).grid(
        row=1,
        column=1,
        sticky="w",
        padx=4,
        pady=(6, 0),
    )

    ttk.Label(top, text="Solver").grid(
        row=1,
        column=2,
        sticky="w",
        padx=(12, 4),
        pady=(6, 0),
    )

    app.barriers_solver_combo = ttk.Combobox(
        top,
        textvariable=app.barriers_solver_display_var,
        values=SOLVER_MODE_OPTIONS,
        state="readonly",
        width=28,
    )
    app.barriers_solver_combo.grid(row=1, column=3, sticky="w", padx=4, pady=(6, 0))
    app.barriers_solver_combo.bind(
        "<<ComboboxSelected>>",
        lambda e: _on_barriers_solver_selected(app),
    )

    ttk.Button(
        top,
        text="Generate Outputs",
        command=app.generate_outputs,
    ).grid(row=1, column=4, padx=(12, 4), pady=(6, 0), sticky="e")

    app.barrier_status_note_var = tk.StringVar(value="")
    app.barrier_status_note_label = ttk.Label(
        frame,
        textvariable=app.barrier_status_note_var,
        foreground="#8A4B00",
        wraplength=900,
    )
    app.barrier_status_note_label.grid(
        row=2,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 4),
    )

    info = ttk.Label(
        frame,
        text=(
            "Double-click editable cells to edit. Material/thickness and T are edited "
            "in the Geometry tab. Energy basis and solver provenance follow the selected "
            "room modality; only CT exposes the generic solver selector."
        ),
    )
    info.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))

    columns = app.BARRIER_COLUMNS
    app.barrier_table = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        selectmode="browse",
    )
    app.barrier_table.configure(height=12)

    heading_map = {
        "name": "Barrier",
        "thickness_mm": "Actual (mm)",
        "material": "Material",
        "barrier_role": "Role",
        "distance_m": "Distance from source (m)",
        "occupancy_factor": "T",
        "design_goal_uSv_per_week": "P (uSv/wk)",
        "unshielded_weekly_dose_uSv": "Unshielded (uSv/wk)",
        "transmitted_dose_uSv_per_week": "Transmitted (uSv/wk)",
        "barrier_transmission_factor_B": "B",
        "display_required_thickness_mm": "Required (mm)",
        "solver_used": "Solver",
        "compliance_status": "Status",
    }

    widths = {
        "name": 120,
        "thickness_mm": 95,
        "material": 90,
        "barrier_role": 145,
        "distance_m": 135,
        "occupancy_factor": 55,
        "design_goal_uSv_per_week": 105,
        "unshielded_weekly_dose_uSv": 135,
        "transmitted_dose_uSv_per_week": 135,
        "barrier_transmission_factor_B": 80,
        "display_required_thickness_mm": 95,
        "solver_used": 150,
        "compliance_status": 75,
    }

    for col in columns:
        app.barrier_table.heading(col, text=heading_map.get(col, col))
        app.barrier_table.column(col, width=widths.get(col, 120), stretch=True)

    app.barrier_table.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    yscroll = ttk.Scrollbar(frame, orient="vertical", command=app.barrier_table.yview)
    xscroll = ttk.Scrollbar(frame, orient="horizontal", command=app.barrier_table.xview)

    app.barrier_table.configure(
        yscrollcommand=yscroll.set,
        xscrollcommand=xscroll.set,
    )

    yscroll.grid(row=1, column=1, sticky="ns", pady=8)
    xscroll.grid(row=3, column=0, sticky="ew", padx=8)

    app.barrier_table.bind(
        "<Double-1>",
        lambda event: app.set_status(
            "Barrier properties are edited from the Geometry tab. The Barriers tab is read-only."
        ),
    )

    app.barrier_table.bind(
        "<Motion>",
        lambda event: on_barrier_table_motion(app, event),
    )
    app.barrier_table.bind(
        "<Leave>",
        lambda event: on_barrier_table_leave(app, event),
    )

    app.barrier_table.tag_configure("qa_fail", background="#ffd6d6")
    app.barrier_table.tag_configure("qa_review", background="#fff1bf")
    app.barrier_table.tag_configure("qa_pass", background="#e3f6e3")
    app.barrier_table.tag_configure("flash_highlight", background="#cfe8ff")

    # Barrier Risk / Confidence panel removed.
    # The main barrier table is now the source of truth for Results/QA display.
    # PDF/JSON/CSV outputs are generated from the canonical results payload.

    app.after(250, app.refresh_barrier_schedule)
