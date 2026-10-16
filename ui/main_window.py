from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tabs.geometry_tab import GeometryTab


def build_ui(app) -> None:
    """Build the main application window, toolbar, notebook, and tab frames."""
    app.columnconfigure(0, weight=1)
    app.rowconfigure(1, weight=1)

    toolbar = ttk.Frame(app)
    toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
    ttk.Button(toolbar, text="New", command=app.new_project).pack(side="left", padx=4)
    ttk.Button(toolbar, text="Open", command=app.open_project).pack(side="left", padx=4)
    ttk.Button(toolbar, text="Save", command=app.save_project).pack(side="left", padx=4)
    ttk.Button(toolbar, text="Save As", command=app.save_project_as).pack(side="left", padx=4)
    ttk.Button(toolbar, text="Quit", command=app.destroy).pack(side="right", padx=4)

    app.main_notebook = ttk.Notebook(app)
    app.main_notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    app.project_tab = ttk.Frame(app.main_notebook)
    app.geometry_tab = GeometryTab(
        app.main_notebook,
        app=app,
        on_change=app.geometry_changed,
    )
    app.sources_tab = ttk.Frame(app.main_notebook)
    app.barriers_tab = ttk.Frame(app.main_notebook)
    app.results_tab = ttk.Frame(app.main_notebook)

    app.source_type_var = tk.StringVar()
    app.source_option_var = tk.StringVar()

    app.source_type_var.trace_add("write", lambda *_: app.update_source_options())
    app.main_notebook.add(app.project_tab, text="Project")
    app.main_notebook.add(app.geometry_tab, text="Geometry")
    app.main_notebook.add(app.sources_tab, text="Sources")
    app.main_notebook.add(app.barriers_tab, text="Barriers")
    # Results tab hidden for MVP: duplicate of Barriers tab; output generation moved to Barriers.
    # app.main_notebook.add(app.results_tab, text="Results")

    app._build_project_tab()
    app._build_sources_tab()
    app._build_barriers_tab()
    app._build_results_tab()

    app.status_var = tk.StringVar(value="Ready.")
    ttk.Label(app, textvariable=app.status_var, anchor="w").grid(
        row=2,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 8),
    )
