from __future__ import annotations

import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

from reports.output_pipeline import generate_outputs_from_app
from services.output_status_messages import build_output_status_message
from tabs.results_output_helpers import (
    default_report_filename,
    resolve_logo_path,
    build_generation_summary_lines,
)


def generate_outputs(app) -> None:
    """Generate report outputs from the Results tab action."""
    try:
        pdf_filename = filedialog.asksaveasfilename(
            title="Save PDF report as",
            defaultextension=".pdf",
            initialfile=default_report_filename(app),
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if not pdf_filename:
            return

        pdf_path = Path(pdf_filename)
        logo_path = resolve_logo_path(app)

        def confirm_report_gate(message: str, blocking: bool) -> bool:
            title = "Report gate warning" if blocking else "Report gate review"
            return bool(messagebox.askyesno(title, message))

        app.set_status("Generating PDF report...")
        result = generate_outputs_from_app(
            app=app,
            output_path=pdf_path,
            logo_path=logo_path,
            report_revision="Rev 0",
            report_status="Draft",
            reviewer_name="",
            company_name="healthphysics.ai",
            confirm_callback=confirm_report_gate,
        )

        status_message = build_output_status_message(result)

        if result.cancelled:
            app.set_status(status_message.status_line)
            return

        app.set_status(status_message.status_line)

        # Output generation performs a final project/results sync. Redraw Geometry so
        # its risk overlay and Tx labels reflect the same current calculation state as
        # the Barriers/Results tabs.
        try:
            geometry_tab = getattr(app, "geometry_tab", None)
            if geometry_tab is not None:
                if hasattr(geometry_tab, "draw_room_with_risk"):
                    geometry_tab.draw_room_with_risk()
                elif hasattr(geometry_tab, "request_redraw"):
                    geometry_tab.request_redraw()
        except Exception:
            pass

        if status_message.severity == "warning":
            messagebox.showwarning(status_message.title, status_message.body)
        else:
            messagebox.showinfo(status_message.title, status_message.body)

    except Exception as e:
        app.set_status("Generation failed.")
        messagebox.showerror("Generation failed", f"{e}\n\n{traceback.format_exc()}")