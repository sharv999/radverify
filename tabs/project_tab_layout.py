from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from services.client_database import add_client, delete_client, load_clients


PROJECT_FIELD_LABELS = ["Project Name", "Client", "Site", "Assessor", "Date"]


def _refresh_client_combo(app, *, include_current: bool = True) -> list[str]:
    clients = load_clients()
    current = str(app.project_vars["Client"].get() or "").strip()
    values = list(clients)
    if include_current and current and current.casefold() not in {item.casefold() for item in values}:
        values.append(current)
        values.sort(key=str.casefold)
    app.project_client_combo["values"] = tuple(values)
    return clients


def _add_client_from_ui(app) -> None:
    name = simpledialog.askstring("Add Client", "Client name:", parent=app)
    if name is None:
        return
    try:
        _clients, canonical = add_client(name)
    except ValueError as exc:
        messagebox.showwarning("Add Client", str(exc), parent=app)
        return
    except OSError as exc:
        messagebox.showerror("Add Client", f"Could not save client database:\n{exc}", parent=app)
        return

    _refresh_client_combo(app, include_current=False)
    app.project_vars["Client"].set(canonical)


def _delete_client_from_ui(app) -> None:
    selected = str(app.project_vars["Client"].get() or "").strip()
    stored = load_clients()
    canonical = next((item for item in stored if item.casefold() == selected.casefold()), "")
    if not canonical:
        messagebox.showinfo("Delete Client", "Select a stored client to delete.", parent=app)
        return

    if not messagebox.askyesno(
        "Delete Client",
        f'Delete "{canonical}" from the client database?',
        parent=app,
    ):
        return

    try:
        delete_client(canonical)
    except OSError as exc:
        messagebox.showerror("Delete Client", f"Could not save client database:\n{exc}", parent=app)
        return

    if selected.casefold() == canonical.casefold():
        app.project_vars["Client"].set("")
    _refresh_client_combo(app, include_current=False)


def build_project_tab(app) -> None:
    """Build the Project tab widgets and attach them to the app instance."""
    frame = app.project_tab
    for i in range(2):
        frame.columnconfigure(i, weight=1)

    app.project_vars = {label: tk.StringVar() for label in PROJECT_FIELD_LABELS}
    app.project_refurbishment_var = tk.BooleanVar(value=False)
    app.room_name_var = tk.StringVar()
    app.room_modality_var = tk.StringVar()
    app.room_name_var.trace_add("write", app.on_room_form_change)
    app.room_modality_var.trace_add("write", app.on_room_form_change)

    row = 0
    for label in PROJECT_FIELD_LABELS:
        ttk.Label(frame, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        if label == "Client":
            client_frame = ttk.Frame(frame)
            client_frame.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
            client_frame.columnconfigure(0, weight=1)

            app.project_client_combo = ttk.Combobox(
                client_frame,
                textvariable=app.project_vars[label],
                values=tuple(load_clients()),
                state="readonly",
                width=48,
            )
            app.project_client_combo.grid(row=0, column=0, sticky="ew")
            ttk.Button(
                client_frame,
                text="Add...",
                command=lambda: _add_client_from_ui(app),
            ).grid(row=0, column=1, padx=(6, 0))
            ttk.Button(
                client_frame,
                text="Delete",
                command=lambda: _delete_client_from_ui(app),
            ).grid(row=0, column=2, padx=(6, 0))
        else:
            ttk.Entry(
                frame,
                textvariable=app.project_vars[label],
                width=60,
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=8,
                pady=4,
            )
        row += 1

    ttk.Label(frame, text="Project Type").grid(
        row=row, column=0, sticky="w", padx=8, pady=4
    )
    ttk.Checkbutton(
        frame,
        text="Refurbishment / existing facility (unchecked = New build)",
        variable=app.project_refurbishment_var,
    ).grid(row=row, column=1, sticky="w", padx=8, pady=4)
    row += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 8)
    )
    row += 1

    ttk.Label(frame, text="Room Name").grid(
        row=row, column=0, sticky="w", padx=8, pady=4
    )
    ttk.Entry(frame, textvariable=app.room_name_var, width=60).grid(
        row=row, column=1, sticky="ew", padx=8, pady=4
    )
    row += 1

    ttk.Label(frame, text="Modality").grid(
        row=row, column=0, sticky="w", padx=8, pady=4
    )
    app.project_room_modality_combo = ttk.Combobox(
        frame,
        textvariable=app.room_modality_var,
        values=tuple(app.ROOM_TYPES),
        state="readonly",
        width=57,
    )
    app.project_room_modality_combo.grid(
        row=row, column=1, sticky="ew", padx=8, pady=4
    )
    row += 1

    ttk.Label(frame, text="Notes").grid(
        row=row,
        column=0,
        sticky="nw",
        padx=8,
        pady=4,
    )
    app.project_notes = tk.Text(frame, height=8)
    app.project_notes.grid(
        row=row,
        column=1,
        sticky="nsew",
        padx=8,
        pady=4,
    )

    row += 1
    ttk.Button(
        frame,
        text="Apply Project Changes",
        command=app.apply_project_form,
    ).grid(
        row=row,
        column=1,
        sticky="e",
        padx=8,
        pady=8,
    )
