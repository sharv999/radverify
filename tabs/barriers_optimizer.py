from __future__ import annotations

import traceback
from typing import Any, Dict, Optional
from tkinter import messagebox

from engine.barrier_optimizer import optimise_flagged_barriers
from geometry.barrier_sync import safe_refresh_barrier_schedule
from tabs.barrier_risk_ui import flash_barrier_row


def jump_to_barrier(app, room_name: str, barrier_name: str):
    room_name = str(room_name or "").strip()
    barrier_name = str(barrier_name or "").strip()
    if not room_name or not barrier_name:
        return

    room = app.get_room_by_name(room_name)
    if room is None:
        return

    room_index = None
    for i, r in enumerate(app.project.rooms):
        if r.name == room_name:
            room_index = i
            break

    if room_index is None:
        return

    # Sync room selections
    app.current_room_index = room_index
    app.barriers_room_var.set(room_name)
    app.sources_room_var.set(room_name)

    if hasattr(app, "rooms_list"):
        app.rooms_list.selection_clear(0, "end")
        app.rooms_list.selection_set(room_index)
        app.rooms_list.activate(room_index)

    app.load_selected_room()
    app.refresh_sources_list()
    safe_refresh_barrier_schedule(app)

    # Switch to Barriers tab
    try:
        app.results_tab.master.select(app.barriers_tab)
    except Exception:
        pass

    # Find visible row by barrier name rather than assuming iid == barrier index
    if hasattr(app, "barrier_table"):
        target_item = None
        for item in app.barrier_table.get_children():
            vals = app.barrier_table.item(item, "values")
            if not vals:
                continue
            try:
                name_idx = app.BARRIER_COLUMNS.index("name")
                if str(vals[name_idx]).strip() == barrier_name:
                    target_item = item
                    break
            except Exception:
                pass

        if target_item:
            try:
                app.barrier_table.see(target_item)
                flash_barrier_row(app, target_item)
            except Exception:
                pass

    app.set_status(f"Jumped to {room_name} / {barrier_name}")


def optimise_barriers(app, room_name: Optional[str] = None):
    try:
        recommendations = optimise_flagged_barriers(
            app.project,
            energy_label=app.global_energy_var.get(),
            solver_mode=app.solver_mode_var.get(),
            room_name=room_name,
        )
        app.optimizer_last_recommendations = recommendations
        app.render_optimizer_recommendations(recommendations)
        count = len(recommendations)
        scope = room_name if room_name else "all rooms"
        app.set_status(f"Generated {count} optimisation recommendation(s) for {scope}.")
        return recommendations
    except Exception as e:
        app.set_status(f"Barrier optimisation failed: {e}")
        messagebox.showerror("Barrier optimisation failed", f"{e}\n\n{traceback.format_exc()}")
        return []


def optimise_selected_room(app):
    room_name = str(app.barriers_room_var.get() or app.sources_room_var.get() or "").strip()
    if not room_name and getattr(app.project, "rooms", None):
        room_name = app.project.rooms[0].name
    return app._optimise_barriers(room_name=room_name if room_name else None)


def optimise_all_rooms(app):
    return app._optimise_barriers(room_name=None)


def render_optimizer_recommendations(app, recommendations: list[Dict[str, Any]]):
    if not hasattr(app, "optimizer_table"):
        return

    for item in app.optimizer_table.get_children():
        app.optimizer_table.delete(item)

    for idx, rec in enumerate(recommendations or []):
        baseline = rec.get("baseline", {}) or {}
        best = rec.get("best_candidate", {}) or {}
        rationale_list = best.get("rationale", []) or []
        rationale = "; ".join(str(x) for x in rationale_list[:3])
        predicted_status = best.get("expected_status", "")
        values = (
            rec.get("room_name", ""),
            rec.get("barrier_name", ""),
            baseline.get("compliance_status", ""),
            best.get("material", ""),
            best.get("thickness_mm", ""),
            predicted_status,
            best.get("predicted_confidence", ""),
            rationale,
        )
        app.optimizer_table.insert(
            "",
            "end",
            iid=str(idx),
            values=values,
            tags=(app._optimizer_row_tag(predicted_status),),
        )
