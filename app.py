from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from radverify.models import RadVerifyProject
from radverify.tabs import RoomDetailsTab, FloorPlanTab, BarrierInspectionTab, MeasurementPointsTab


APP_NAME = "RadVerify"
APP_VERSION = "0.1 field prototype"
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
        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.room_tab = RoomDetailsTab(self.notebook, self)
        self.floor_tab = FloorPlanTab(self.notebook, self)
        self.barrier_tab = BarrierInspectionTab(self.notebook, self)
        self.measurement_tab = MeasurementPointsTab(self.notebook, self)
        self.notebook.add(self.room_tab, text="1  Room Details")
        self.notebook.add(self.floor_tab, text="2  Floor Plan")
        self.notebook.add(self.barrier_tab, text="3  Barrier Inspection")
        self.notebook.add(self.measurement_tab, text="4  Measurement Points")
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
        file_menu.add_command(label="Export RadStatus payload…", command=self.export_radstatus_payload)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
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

    def load_project_into_ui(self):
        self._loading = True
        try:
            self.room_tab.load()
            self.floor_tab.refresh_openings()
            self.barrier_tab.refresh()
            self.measurement_tab.refresh()
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
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            self.project = RadVerifyProject.from_dict(data)
        except Exception as exc:
            messagebox.showerror("Open project", f"Could not open project:\n{exc}")
            return
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
        self.current_file = Path(filename)
        return self._write_project(self.current_file)

    def _write_project(self, path: Path):
        self.room_tab.apply_to_model()
        try:
            path.write_text(json.dumps(self.project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save project", f"Could not save project:\n{exc}")
            return False
        self._dirty = False
        self._update_title()
        self.set_status(f"Saved {path.name}")
        return True

    def export_radstatus_payload(self):
        filename = filedialog.asksaveasfilename(title="Export RadStatus payload", defaultextension=".json", initialfile=f"{self.project.details.project_id or 'radverify'}_radstatus.json", filetypes=(("JSON", "*.json"),))
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps(self.project.to_radstatus_payload(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Export", f"Could not export RadStatus payload:\n{exc}")
            return
        self.set_status(f"Exported RadStatus payload: {Path(filename).name}")

    def on_close(self):
        if self._confirm_discard():
            self.destroy()


if __name__ == "__main__":
    RadVerifyApp().mainloop()
