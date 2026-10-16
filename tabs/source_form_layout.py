from __future__ import annotations

from tkinter import ttk

from engine.shielding_engine import auto_select_tvl_key
from modalities.registry import (
    default_source_type_for_modality,
    handle_source_form_event,
    source_form_schema_for_type,
    source_form_tvl_params_for_type,
    source_form_kind_for_type,
)


def clear_source_form_container(app):
    for child in app.source_form_container.winfo_children():
        child.destroy()


def validate_integer_input(app, proposed: str) -> bool:
    return proposed == "" or proposed.isdigit()


def format_integer_var_on_focus_out(app, variable):
    try:
        value = str(variable.get()).strip()
        if value == "":
            return
        variable.set(str(int(float(value))))
    except Exception:
        pass


def make_readonly_entry(app, parent, variable):
    return ttk.Entry(parent, textvariable=variable, state="readonly")


def add_labeled_readonly_entry(app, parent, row, label, variable):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
    app._make_readonly_entry(parent, variable).grid(
        row=row, column=1, sticky="ew", padx=4, pady=4
    )


def make_integer_entry(app, parent, variable):
    vcmd = (app.register(app._validate_integer_input), "%P")
    entry = ttk.Entry(
        parent, textvariable=variable, validate="key", validatecommand=vcmd
    )
    entry.bind(
        "<FocusOut>",
        lambda event, var=variable: app._format_integer_var_on_focus_out(var),
    )
    return entry


def add_labeled_entry(app, parent, row, label, variable):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
    ttk.Entry(parent, textvariable=variable).grid(
        row=row, column=1, sticky="ew", padx=4, pady=4
    )


def add_labeled_integer_entry(app, parent, row, label, variable):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
    app._make_integer_entry(parent, variable).grid(
        row=row, column=1, sticky="ew", padx=4, pady=4
    )


def render_plugin_source_form(app, parent, source_type: str, schema) -> None:
    """Render a plugin-prepared source form without modality-specific branches."""

    for field in schema.fields:
        variables = getattr(app, field.variable_group)
        variable = variables[field.key]
        ttk.Label(parent, text=field.label).grid(
            row=field.row, column=0, sticky="w", padx=4, pady=4
        )

        if field.widget_kind == "combobox":
            widget = ttk.Combobox(
                parent,
                textvariable=variable,
                values=field.values,
                state=field.state,
            )
        elif field.widget_kind == "readonly_entry":
            widget = app._make_readonly_entry(parent, variable)
        elif field.widget_kind == "integer_entry":
            widget = app._make_integer_entry(parent, variable)
        else:
            widget = ttk.Entry(parent, textvariable=variable, state=field.state)

        widget.grid(row=field.row, column=1, sticky="ew", padx=4, pady=4)
        if field.widget_attr:
            setattr(app, field.widget_attr, widget)
        if field.event_sequence and field.event_kind:
            widget.bind(
                field.event_sequence,
                lambda event, kind=field.event_kind: handle_source_form_event(
                    app, kind, source_type
                ),
            )

    for text_row in schema.text_rows:
        ttk.Label(parent, text=text_row.text).grid(
            row=text_row.row,
            column=text_row.column,
            columnspan=text_row.columnspan,
            sticky=text_row.sticky,
            padx=4,
            pady=4,
        )


def refresh_source_form_by_type(app):
    app._clear_source_form_container()
    room = (
        app.get_room_by_name(app.sources_room_var.get())
        if hasattr(app, "sources_room_var")
        else None
    )
    allowed = app._allowed_source_types_for_room(room)
    fallback_source_type = allowed[0] if allowed else (
        default_source_type_for_modality("CT") or "ct_scatter"
    )
    stype = app.source_type_var.get().strip() or fallback_source_type
    if stype not in allowed:
        stype = fallback_source_type
        app.source_type_var.set(stype)
    app._configure_source_type_combo_for_room(room)

    f = app.source_form_container
    f.columnconfigure(1, weight=1)
    form_kind = source_form_kind_for_type(stype)
    if form_kind == "pet_working_state":
        from tabs.pet_preview_panel import build_pet_source_controls

        try:
            app.source_form_container.configure(text="PET Source Parameters")
        except Exception:
            pass
        build_pet_source_controls(app, f)
        return

    if form_kind == "spect_working_state":
        from tabs.spect_preview_panel import build_spect_source_controls

        try:
            app.source_form_container.configure(text="SPECT Source Parameters")
        except Exception:
            pass
        build_spect_source_controls(app, f)
        return

    try:
        app.source_form_container.configure(text="CT Source Parameters")
    except Exception:
        pass
    schema = source_form_schema_for_type(stype, app)
    if schema is not None:
        render_plugin_source_form(app, f, stype, schema)


def update_auto_tvl_key_display(app):
    source_type = app.source_type_var.get().strip()
    try:
        params = source_form_tvl_params_for_type(source_type, app)
        if params is None:
            return
        app.radiation_type_var.set(
            auto_select_tvl_key(
                source_type,
                params,
                app.radiation_type_var.get(),
            )
        )
    except Exception:
        pass
