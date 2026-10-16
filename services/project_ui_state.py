from __future__ import annotations

from pathlib import Path
from typing import Any
from geometry.barrier_sync import safe_refresh_barrier_schedule


def reset_project_selection_state(app: Any) -> None:
    """Reset transient UI selections after replacing the active project."""
    app.current_room_index = 0
    app.current_source_index = 0
    app.last_selected_source_index = None
    app.last_selected_source_room_name = None


def apply_loaded_project_to_ui(app: Any, project: Any, filename: str | Path) -> None:
    """Install a loaded single-room project and re-establish safe UI selections."""
    app.project = project
    app.current_file = Path(filename)

    reset_project_selection_state(app)
    app._prune_unsupported_rooms()
    app.refresh_all()
    ensure_valid_post_open_selection(app)

    # Room identity/modality now live on Project, so return there after Open.
    if hasattr(app, "main_notebook") and hasattr(app, "project_tab"):
        try:
            app.main_notebook.select(app.project_tab)
        except Exception:
            pass

    app.set_status(f"Opened {filename}")


def ensure_valid_post_open_selection(app: Any) -> None:
    """Ensure the single room/source selection is valid after loading."""
    if not getattr(app.project, "rooms", None):
        app.refresh_all()
        return

    room = app.project.rooms[0]
    app.current_room_index = 0
    app.current_source_index = 0

    try:
        if hasattr(app, "sources_room_var"):
            app.sources_room_var.set(room.name)
        if hasattr(app, "barriers_room_var"):
            app.barriers_room_var.set(room.name)
    except Exception:
        pass

    app.refresh_all()

    try:
        app.geometry_tab.refresh_room_list(preferred_room_name=room.name)
    except Exception:
        pass

    try:
        app.refresh_sources_list(preserve_index=0)
        app._reload_source_ui_from_model(room, 0, refresh_live=True)
    except Exception:
        pass

    try:
        safe_refresh_barrier_schedule(app)
        app.refresh_results_tab()
    except Exception:
        pass
