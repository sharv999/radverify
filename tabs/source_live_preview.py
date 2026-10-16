from __future__ import annotations

from modalities.registry import source_live_preview_lines


def update_live_source_preview_from_form(app):
    if not hasattr(app, "source_calc_text"):
        return
    app.source_calc_text.configure(state="normal")
    app.source_calc_text.delete("1.0", "end")

    room = app.get_room_by_name(app.sources_room_var.get())
    src = app._get_current_source()
    if room and app._room_sources_are_locked(room) and src is not None:
        source_type = src.source_type
        source_name = src.name
    else:
        source_type = app.source_type_var.get().strip()
        source_name = app.source_name_var.get().strip() or "(unsaved source)"

    if not room or not source_type:
        app.source_calc_text.configure(state="disabled")
        return

    lines = [
        f"Room: {room.name}",
        f"Editing source: {source_name} [{source_type}]",
        f"Auto TVL key: {app.radiation_type_var.get().strip()}",
        "",
    ]

    try:
        prepared = source_live_preview_lines(
            app,
            source_type,
            source_name,
            app.radiation_type_var.get().strip(),
        )
        if prepared:
            lines.extend(prepared)
        else:
            lines.append("No live preview is defined for this source type.")
    except Exception as exc:
        lines.append(f"Preview unavailable: {exc}")

    insert_source_calc_lines(app, lines)
    app.source_calc_text.configure(state="disabled")


def configure_source_calc_text_tags(app) -> None:
    """Configure emphasis tags for the Live Source Calculations panel."""
    if not hasattr(app, "source_calc_text"):
        return
    try:
        app.source_calc_text.tag_configure(
            "ksec_highlight",
            font=("TkDefaultFont", 10, "bold"),
            background="#fff4bf",
            foreground="#7a5200",
        )
        app.source_calc_text.tag_configure(
            "source_header_highlight",
            font=("TkDefaultFont", 10, "bold"),
            foreground="#0b6e4f",
        )
    except Exception:
        pass


def source_calc_line_tags(app, line: str) -> tuple[str, ...]:
    """Return display tags for a Live Source Calculations line."""
    return tuple()


def insert_source_calc_lines(app, lines: list[str]) -> None:
    """Insert Live Source Calculation lines with per-line emphasis."""
    if not hasattr(app, "source_calc_text"):
        return
    configure_source_calc_text_tags(app)
    for line in lines:
        tags = source_calc_line_tags(app, str(line))
        if tags:
            app.source_calc_text.insert("end", str(line) + "\n", tags)
        else:
            app.source_calc_text.insert("end", str(line) + "\n")
