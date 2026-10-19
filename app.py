from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from radverify.models import RadVerifyProject
from radverify.safe_io import atomic_write_json, read_native_project
from radverify.reporting import build_verification_pdf
from radverify.packaging import (
    FieldPackageError, build_field_package, default_restore_folder,
    project_json_for_save, resolve_evidence_paths, restore_field_package,
)
from radverify.radtwin import (
    RADTWIN_EXTENSION,
    project_from_radtwin,
    project_to_radtwin,
)
from radverify.tabs import RoomDetailsTab, FloorPlanTab, BarrierInspectionTab, MeasurementPointsTab, RoomSummaryTab


APP_NAME = "RadVerify"
APP_VERSION = "0.4 Step 4 field deployment readiness audit"
PROJECT_EXTENSION = ".radverify.json"


class RadVerifyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.geometry("1500x900")
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.current_file: Path | None = None
        self.project = RadVerifyProject()
        self._dirty = False
        self._loading = False
        self._configure_style()
        self._build_ui()
        self.load_project_into_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Bahnschrift", 14, "bold"))
        style.configure("Section.TLabel", font=("Bahnschrift", 10, "bold"))
        style.configure("Status.TLabel", padding=(8, 3))

    def _build_ui(self):
        self._build_menu()
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)

        topbar = ttk.Frame(shell)
        topbar.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(topbar, text="Quit", command=self.on_close).pack(side="right")
        ttk.Button(topbar, text="Export verification PDF…", command=self.export_verification_pdf).pack(side="right", padx=(0, 8))
        ttk.Button(topbar, text="Export field package ZIP…", command=self.export_field_package).pack(side="right", padx=(0, 8))
        ttk.Button(topbar, text="Import field package ZIP…", command=self.import_field_package).pack(side="right", padx=(0, 8))

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        self.room_tab = RoomDetailsTab(self.notebook, self)
        self.floor_tab = FloorPlanTab(self.notebook, self)
        self.barrier_tab = BarrierInspectionTab(self.notebook, self)
        self.measurement_tab = MeasurementPointsTab(self.notebook, self)
        self.summary_tab = RoomSummaryTab(self.notebook, self)
        self.notebook.add(self.room_tab, text="1  Room Details")
        self.notebook.add(self.floor_tab, text="2  Floor Plan")
        self.notebook.add(self.barrier_tab, text="3  Barrier Inspection")
        self.notebook.add(self.measurement_tab, text="4  Measurement Points")
        self.notebook.add(self.summary_tab, text="5  Room Summary")
        self.notebook.bind("<<NotebookTabChanged>>", self._notebook_tab_changed)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(shell, textvariable=self.status_var, style="Status.TLabel", anchor="w").pack(fill="x", padx=8, pady=(2, 5))

    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Open…", command=self.open_project, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As…", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Import Radiation Room Digital Twin…", command=self.import_radtwin)
        file_menu.add_command(label="Export Radiation Room Digital Twin…", command=self.export_radtwin)
        file_menu.add_separator()
        file_menu.add_command(label="Export RadStatus payload…", command=self.export_radstatus_payload)
        file_menu.add_command(label="Export draft verification report (PDF)…", command=self.export_verification_pdf)
        file_menu.add_command(label="Export portable field package (ZIP)…", command=self.export_field_package)
        file_menu.add_command(label="Import / restore field package (ZIP)…", command=self.import_field_package)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Export field readiness audit…", command=self.export_readiness_audit)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo("RadVerify", f"{APP_NAME}\n{APP_VERSION}\n\nField verification prototype derived from the RadShield room/floor-plan GUI."))
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)
        self.bind_all("<Control-n>", lambda _e: self.new_project())
        self.bind_all("<Control-o>", lambda _e: self.open_project())
        self.bind_all("<Control-s>", lambda _e: self.save_project())

    def set_status(self, text: str):
        self.status_var.set(text)

    def mark_dirty(self):
        if self._loading:
            return
        self._dirty = True
        self._update_title()

    def _update_title(self):
        name = self.current_file.name if self.current_file else "Untitled"
        star = " *" if self._dirty else ""
        self.title(f"{APP_NAME} — {name}{star} — {APP_VERSION}")

    def refresh_visuals(self):
        if hasattr(self, "floor_tab"):
            self.floor_tab.redraw()
        if hasattr(self, "summary_tab"):
            self.summary_tab.refresh()

    def _notebook_tab_changed(self, _event=None):
        if not hasattr(self, "summary_tab"):
            return
        try:
            selected = self.notebook.nametowidget(self.notebook.select())
        except Exception:
            return
        if selected is self.summary_tab:
            self.summary_tab.refresh()

    def load_project_into_ui(self):
        self._loading = True
        try:
            self.room_tab.load()
            self.floor_tab.load_dimensions()
            self.floor_tab.reset_selection()
            self.floor_tab.refresh_openings()
            self.barrier_tab.refresh()
            self.measurement_tab.refresh()
            self.summary_tab.refresh()
            self.after_idle(self.floor_tab.redraw)
        finally:
            self._loading = False
        self._update_title()

    def _confirm_discard(self):
        if not self._dirty:
            return True
        result = messagebox.askyesnocancel("Unsaved changes", "Save changes before continuing?")
        if result is None:
            return False
        if result:
            return self.save_project()
        return True

    def new_project(self):
        if not self._confirm_discard():
            return
        self.project = RadVerifyProject()
        self.current_file = None
        self._dirty = False
        self.load_project_into_ui()
        self.set_status("New RadVerify project")

    def open_project(self):
        if not self._confirm_discard():
            return
        filename = filedialog.askopenfilename(title="Open RadVerify project", filetypes=(("RadVerify JSON", "*.radverify.json *.json"), ("All files", "*.*")))
        if not filename:
            return
        try:
            loaded = read_native_project(filename)
        except Exception as exc:
            messagebox.showerror("Open project", f"Could not open project:\n{exc}")
            return
        self.project = loaded
        self.current_file = Path(filename)
        self._dirty = False
        self.load_project_into_ui()
        self.set_status(f"Opened {self.current_file.name}")

    def save_project(self):
        if self.current_file is None:
            return self.save_project_as()
        return self._write_project(self.current_file)

    def save_project_as(self):
        filename = filedialog.asksaveasfilename(title="Save RadVerify project", defaultextension=PROJECT_EXTENSION, filetypes=(("RadVerify JSON", "*.radverify.json"), ("JSON", "*.json")))
        if not filename:
            return False
        return self._write_project(Path(filename))

    def _write_project(self, path: Path):
        try:
            self.room_tab.apply_to_model()
            atomic_write_json(path, project_json_for_save(self.project, path))
        except Exception as exc:
            messagebox.showerror("Save project", f"Could not save project:\n{exc}")
            return False
        self.current_file = path
        self._dirty = False
        self._update_title()
        self.set_status(f"Saved {path.name}")
        return True


    def import_radtwin(self):
        if not self._confirm_discard():
            return
        filename = filedialog.askopenfilename(
            title="Import Radiation Room Digital Twin",
            filetypes=(("Radiation Room Digital Twin", "*.radtwin.json *.json"), ("All files", "*.*")),
        )
        if not filename:
            return
        try:
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            imported = project_from_radtwin(data)
            resolve_evidence_paths(imported, Path(filename).parent)
        except Exception as exc:
            messagebox.showerror("Import digital twin", f"Could not import Radiation Room Digital Twin:\n{exc}")
            return
        # A twin is an interchange record rather than a native RadVerify project.
        # Import it into a new unsaved working project so the original twin is not
        # silently overwritten by File > Save.
        self.project = imported
        self.current_file = None
        self._dirty = True
        self.load_project_into_ui()
        self._dirty = True
        self._update_title()
        self.set_status(f"Imported Radiation Room Digital Twin: {Path(filename).name}")

    def export_radtwin(self):
        self.room_tab.apply_to_model()
        project_id = self.project.details.project_id or "radiation-room"
        filename = filedialog.asksaveasfilename(
            title="Export Radiation Room Digital Twin",
            defaultextension=RADTWIN_EXTENSION,
            initialfile=f"{project_id}{RADTWIN_EXTENSION}",
            filetypes=(("Radiation Room Digital Twin", "*.radtwin.json"), ("JSON", "*.json")),
        )
        if not filename:
            return
        try:
            atomic_write_json(filename, project_to_radtwin(self.project))
        except Exception as exc:
            messagebox.showerror("Export digital twin", f"Could not export Radiation Room Digital Twin:\n{exc}")
            return
        self.set_status(f"Exported Radiation Room Digital Twin: {Path(filename).name}")

    def export_radstatus_payload(self):
        filename = filedialog.asksaveasfilename(title="Export RadStatus payload", defaultextension=".json", initialfile=f"{self.project.details.project_id or 'radverify'}_radstatus.json", filetypes=(("JSON", "*.json"),))
        if not filename:
            return
        try:
            atomic_write_json(filename, self.project.to_radstatus_payload())
        except Exception as exc:
            messagebox.showerror("Export", f"Could not export RadStatus payload:\n{exc}")
            return
        self.set_status(f"Exported RadStatus payload: {Path(filename).name}")

    def export_verification_pdf(self):
        """Generate a non-certifying field record without changing project-file state."""
        self.room_tab.apply_to_model()
        project_id = self.project.details.project_id or "radverify"
        filename = filedialog.asksaveasfilename(
            title="Export draft Radiation Room Verification PDF",
            defaultextension=".pdf",
            initialfile=f"{project_id}_field_verification_DRAFT.pdf",
            filetypes=(("PDF report", "*.pdf"),),
        )
        if not filename:
            return
        try:
            build_verification_pdf(self.project, filename)
        except Exception as exc:
            messagebox.showerror("Export verification PDF", f"Could not create report:\n{exc}")
            return
        self.set_status(f"Exported DRAFT field report: {Path(filename).name}")

    def export_field_package(self):
        """Create a complete transfer archive, without changing the working project."""
        self.room_tab.apply_to_model()
        project_id = self.project.details.project_id or "radverify"
        filename = filedialog.asksaveasfilename(
            title="Export portable RadVerify field package",
            defaultextension=".zip",
            initialfile=f"{project_id}_field_record.zip",
            filetypes=(("RadVerify field package", "*.zip"),),
        )
        if not filename:
            return
        try:
            build_field_package(self.project, filename)
        except Exception as exc:
            messagebox.showerror("Export field package", f"Could not package field record:\n{exc}")
            return
        self.set_status(f"Exported portable field package: {Path(filename).name}")

    def import_field_package(self):
        """Restore to an isolated folder, then open only after integrity checks pass."""
        if not self._confirm_discard():
            return
        archive = filedialog.askopenfilename(
            title="Select portable RadVerify field package",
            filetypes=(("RadVerify field package", "*.zip"),),
        )
        if not archive:
            return
        parent = filedialog.askdirectory(title="Choose a folder to contain the restored project")
        if not parent:
            return
        destination = default_restore_folder(archive, parent)
        try:
            restored_path = restore_field_package(archive, destination)
            data = json.loads(restored_path.read_text(encoding="utf-8"))
            project = RadVerifyProject.from_dict(data)
            resolve_evidence_paths(project, restored_path.parent)
        except Exception as exc:
            messagebox.showerror("Restore field package", f"Field package could not be restored:\n{exc}")
            return
        self.project = project
        self.current_file = restored_path
        self._dirty = False
        self.load_project_into_ui()
        self.set_status(f"Restored verified field package: {restored_path} — unsigned SHA-256 integrity")
        messagebox.showinfo(
            "Field package restored",
            f"Project and evidence restored to:\n{destination}\n\n"
            "SHA-256 integrity verified. This does not authenticate the package's author.",
        )

    def export_readiness_audit(self):
        """Run independent synthetic preflight; never mark field release approved."""
        filename = filedialog.asksaveasfilename(
            title="Export V0.4 field readiness audit and manual checklist",
            defaultextension=".md",
            initialfile="RadVerify_V0.4_field_readiness_audit.md",
            filetypes=(("Markdown checklist", "*.md"),),
        )
        if not filename:
            return
        try:
            from radverify.deployment import run_field_readiness_audit, write_audit_files
            result = run_field_readiness_audit()
            report, inventory = write_audit_files(result, filename)
        except Exception as exc:
            messagebox.showerror("Field readiness audit", f"Audit could not complete:\n{exc}")
            return
        self.set_status(f"Field readiness audit: {result['automated_result']} — manual site checks outstanding")
        messagebox.showinfo(
            "Field readiness audit",
            f"Automated: {result['automated_pass']}/{result['automated_total']} {result['automated_result']}\n"
            f"Manual field acceptance: NOT CLEARED\n\n"
            f"Checklist: {report}\nMachine record: {inventory}",
        )

    def on_close(self):
        if self._confirm_discard():
            self.destroy()


if __name__ == "__main__":
    RadVerifyApp().mainloop()
