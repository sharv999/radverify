from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tabs.results_tab_help import on_results_text_click


def build_results_tab(app) -> None:
    """Build the Results tab widgets and bind result-display events."""
    frame = app.results_tab
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    top = ttk.Frame(frame)
    top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))

    ttk.Button(
        top,
        text="Generate Outputs",
        command=app.generate_outputs,
    ).pack(side="left")

    app.results_text = tk.Text(
        frame,
        wrap="word",
        background="#f8fafc",
        foreground="#111827",
        font=app.ui_font_mono,
        padx=10,
        pady=8,
        spacing1=2,
        spacing3=4,
        cursor="hand2",
    )
    app.results_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    app.results_text.tag_configure("result_fail", foreground="#b00020")
    app.results_text.tag_configure("result_review", foreground="#8a6d00")
    app.results_text.tag_configure("result_pass", foreground="#1f6f1f")
    app.results_text.tag_configure("result_heading", font=("TkDefaultFont", 10, "bold"))
    app.results_text.tag_configure("result_clickable", underline=False)
    app.results_text.tag_configure("muted", foreground="#666666")
    app.results_text.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
    app.results_text.tag_configure(
        "dominant",
        foreground="#0b6e4f",
        font=("Courier New", 10, "bold"),
    )

    app.results_text.bind(
    "<Button-1>",
    lambda event: on_results_text_click(app, event),
    )

    app.results_text.configure(state="disabled")
