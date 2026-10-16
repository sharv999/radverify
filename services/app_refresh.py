"""Application-wide refresh orchestration."""

from geometry.barrier_sync import safe_refresh_barrier_schedule


def refresh_all(app):
    """Refresh all app tabs and derived UI state after project-level changes."""
    app._sanitize_all_nm_patient_sources()
    app._coerce_project_barrier_schema()
    app.optimizer_last_recommendations = []

    for room in app.project.rooms:
        app.enforce_room_source_types(room)

    app.refresh_project_form()
    app.refresh_single_room_state()

    if app.project.rooms:
        room = app.project.rooms[0]
        app.current_room_index = 0
        app.sources_room_var.set(room.name)
        app.barriers_room_var.set(room.name)
        app.refresh_sources_list(preserve_index=0)
        safe_refresh_barrier_schedule(app)
    else:
        app.refresh_source_calculations()

    app._update_sources_readonly_state()
    app.refresh_results_tab()
    app.render_optimizer_recommendations([])

    if hasattr(app, "barrier_risk_summary_var"):
        app.barrier_risk_summary_var.set("No barrier risk data yet.")
    if hasattr(app, "barrier_risk_table"):
        for item in app.barrier_risk_table.get_children():
            app.barrier_risk_table.delete(item)
