"""Application style/theme configuration for the RadShield Tk UI."""

from __future__ import annotations

from tkinter import ttk


def configure_app_style(app) -> None:
    """
    Central UI typography + spacing.
    Uses Windows-native Bahnschrift for a clean technical/medical software look.
    """
    app.ui_font = ("Bahnschrift", 9)
    app.ui_font_small = ("Bahnschrift", 8)
    app.ui_font_heading = ("Bahnschrift", 12, "bold")
    app.ui_font_section = ("Bahnschrift", 10, "bold")
    app.ui_font_table = ("Bahnschrift", 9)
    app.ui_font_table_heading = ("Bahnschrift", 9, "bold")
    app.ui_font_mono = ("Consolas", 9)

    style = ttk.Style(app)

    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", font=app.ui_font)

    style.configure("TFrame", background="#f3f4f6")
    style.configure("TLabel", font=app.ui_font, background="#f3f4f6", foreground="#111827")
    style.configure("Muted.TLabel", font=app.ui_font_small, foreground="#6b7280", background="#f3f4f6")
    style.configure("Heading.TLabel", font=app.ui_font_heading, background="#f3f4f6", foreground="#111827")
    style.configure("Section.TLabel", font=app.ui_font_section, background="#f3f4f6", foreground="#111827")

    style.configure("TButton", font=app.ui_font, padding=(8, 4))
    style.configure("TEntry", font=app.ui_font, padding=(4, 3))
    style.configure("TCombobox", font=app.ui_font, padding=(4, 3))
    style.configure("TCheckbutton", font=app.ui_font, background="#f3f4f6")

    style.configure("TLabelframe", background="#f3f4f6", padding=(8, 6))
    style.configure("TLabelframe.Label", font=app.ui_font_section, background="#f3f4f6", foreground="#111827")

    style.configure("TNotebook", background="#f3f4f6")
    style.configure("TNotebook.Tab", font=app.ui_font, padding=(10, 5))

    style.configure(
        "Treeview",
        font=app.ui_font_table,
        rowheight=24,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        font=app.ui_font_table_heading,
        padding=(4, 5),
    )

    try:
        app.option_add("*Listbox.Font", app.ui_font)
        app.option_add("*Text.Font", app.ui_font_mono)
        app.option_add("*Entry.Font", app.ui_font)
        app.option_add("*TCombobox*Listbox.Font", app.ui_font)
    except Exception:
        pass


