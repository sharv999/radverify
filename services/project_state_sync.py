from __future__ import annotations

"""
Project/UI state synchronisation.

This service is the single pre-calculation / pre-save / pre-output sync path.

It deliberately coordinates existing app methods rather than owning domain logic:
    - app.apply_project_form()
    - app.persist_previous_selected_source()
    - app.sync_current_source_to_model()
    - app.geometry_tab.update_model_from_fields()
    - app._repair_invalid_source_inventory()
    - app.enforce_room_source_types()
    - app._apply_geometry_to_selected_room_barriers()
    - app.sync_room_sources_from_project()
    - app._coerce_barrier_schema()

The goal is to avoid "UI looks correct but saved/report model is stale" bugs.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List

from modalities.registry import ct_ksec_source_types
from services.ui_sync_guard import sync_output_relevant_ui_state


def _ct_like_source_types() -> set[str]:
    return set(ct_ksec_source_types())


def _source_key(src: Any) -> tuple[str, str]:
    return (
        str(getattr(src, "room_name", "") or "").strip(),
        str(getattr(src, "source_type", "") or "").strip(),
    )


def _capture_ct_source_snapshots(app: Any) -> dict[tuple[str, str], dict]:
    """
    Capture CT-like source identity/physics parameters before Geometry field sync.

    Geometry owns room dimensions, source position and barrier distances. It must
    not silently replace the project CT scanner/ksec source during save/output
    sync just because the Geometry scanner combobox is stale.
    """
    snapshots: dict[tuple[str, str], dict] = {}

    project = getattr(app, "project", None)
    sources = list(getattr(project, "sources", []) or [])

    for src in sources:
        source_type = str(getattr(src, "source_type", "") or "").strip()
        if source_type not in _ct_like_source_types():
            continue

        key = _source_key(src)
        if not key[0] or not key[1]:
            continue

        params = getattr(src, "params", {}) or {}
        snapshots[key] = {
            "name": getattr(src, "name", ""),
            "radiation_type": getattr(src, "radiation_type", ""),
            "params": dict(params) if isinstance(params, dict) else {},
        }

    return snapshots


def _restore_ct_source_snapshots(app: Any, snapshots: dict[tuple[str, str], dict]) -> int:
    """
    Restore CT-like source identity/physics after Geometry-only sync.

    This preserves the canonical Sources-tab/project source used by the physics
    engine while still allowing Geometry to update dimensions, source position
    and barrier distances.
    """
    if not snapshots:
        return 0

    restored = 0
    project = getattr(app, "project", None)
    sources = list(getattr(project, "sources", []) or [])

    for src in sources:
        key = _source_key(src)
        snapshot = snapshots.get(key)
        if not snapshot:
            continue

        params = snapshot.get("params", {})
        if isinstance(params, dict):
            src.params = dict(params)

        if snapshot.get("name"):
            src.name = snapshot["name"]

        if snapshot.get("radiation_type"):
            src.radiation_type = snapshot["radiation_type"]

        restored += 1

    # Keep any legacy room mirror and Geometry canvas metadata aligned with the
    # restored project source.
    for room in list(getattr(project, "rooms", []) or []):
        try:
            if hasattr(app, "sync_room_sources_from_project"):
                app.sync_room_sources_from_project(room)
        except Exception:
            pass

        try:
            geometry_tab = getattr(app, "geometry_tab", None)
            if geometry_tab is not None and hasattr(
                geometry_tab,
                "sync_geometry_source_metadata_from_project_source",
            ):
                geometry_tab.sync_geometry_source_metadata_from_project_source(room)
        except Exception:
            pass

    return restored


@dataclass
class ProjectStateSyncResult:
    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "actions": list(self.actions),
        }


def sync_project_state_from_ui(
    app: Any,
    *,
    sync_project_form: bool = True,
    sync_sources: bool = True,
    sync_geometry: bool = True,
    repair_sources: bool = True,
    apply_room_barriers: bool = True,
    sync_room_source_mirrors: bool = True,
    coerce_barriers: bool = True,
    sanitize_nm_sources: bool = True,
    ignore_errors: bool = True,
) -> ProjectStateSyncResult:
    """
    Push latest editable UI state into app.project.

    Use this before Save, Save As, Results refresh, output generation, and
    source-readiness validation.
    """
    result = ProjectStateSyncResult()
    ct_source_snapshots = _capture_ct_source_snapshots(app) if sync_geometry else {}

    def run(label: str, fn: Callable[[], Any], *, critical: bool = False) -> Any:
        try:
            value = fn()
            result.actions.append(label)
            return value
        except Exception as exc:
            message = f"{label}: {exc}"
            if critical or not ignore_errors:
                result.ok = False
                result.errors.append(message)
                if not ignore_errors:
                    raise
            else:
                result.warnings.append(message)
            return None

    if sync_project_form and hasattr(app, "apply_project_form"):
        run("apply_project_form", app.apply_project_form)

    if sync_sources:
        if hasattr(app, "persist_previous_selected_source"):
            run("persist_previous_selected_source", app.persist_previous_selected_source)

        if hasattr(app, "sync_current_source_to_model"):
            run(
                "sync_current_source_to_model",
                lambda: app.sync_current_source_to_model(ignore_errors=True),
            )

    if sync_geometry and hasattr(app, "geometry_tab"):
        geometry_tab = getattr(app, "geometry_tab", None)
        if geometry_tab is not None and hasattr(geometry_tab, "update_model_from_fields"):
            run(
                "geometry_tab.update_model_from_fields",
                lambda: geometry_tab.update_model_from_fields(show_errors=False),
            )

        # Also run the guarded Geometry/Sources sync once before room-level
        # coercion below. This protects save/output paths from stale scanner
        # position/source state without removing the legacy per-room repair
        # actions that existing tests and workflows expect.
        run("sync_output_relevant_ui_state", lambda: sync_output_relevant_ui_state(app))

    if repair_sources and hasattr(app, "_repair_invalid_source_inventory"):
        run("_repair_invalid_source_inventory", app._repair_invalid_source_inventory)

    project = getattr(app, "project", None)
    rooms = list(getattr(project, "rooms", []) or [])

    for room in rooms:
        room_name = str(getattr(room, "name", "") or "<unnamed room>")

        if repair_sources and hasattr(app, "enforce_room_source_types"):
            run(
                f"enforce_room_source_types[{room_name}]",
                lambda room=room: app.enforce_room_source_types(room),
            )

        if apply_room_barriers and hasattr(app, "_apply_geometry_to_selected_room_barriers"):
            run(
                f"_apply_geometry_to_selected_room_barriers[{room_name}]",
                lambda room=room: app._apply_geometry_to_selected_room_barriers(room),
            )

        if sync_room_source_mirrors and hasattr(app, "sync_room_sources_from_project"):
            run(
                f"sync_room_sources_from_project[{room_name}]",
                lambda room=room: app.sync_room_sources_from_project(room),
            )

        if coerce_barriers and hasattr(app, "_coerce_barrier_schema"):
            for barrier in list(getattr(room, "barriers", []) or []):
                barrier_name = str(getattr(barrier, "name", "") or "<unnamed barrier>")
                run(
                    f"_coerce_barrier_schema[{room_name}/{barrier_name}]",
                    lambda barrier=barrier: app._coerce_barrier_schema(barrier),
                )

    if sanitize_nm_sources and hasattr(app, "_sanitize_all_nm_patient_sources"):
        run("_sanitize_all_nm_patient_sources", app._sanitize_all_nm_patient_sources)

    restored_ct_sources = _restore_ct_source_snapshots(app, ct_source_snapshots)
    if restored_ct_sources:
        result.actions.append(f"restore_ct_source_snapshots[{restored_ct_sources}]")

    if result.errors:
        result.ok = False

    return result


def sync_project_state_for_save(app: Any) -> ProjectStateSyncResult:
    return sync_project_state_from_ui(
        app,
        sync_project_form=True,
        sync_sources=True,
        sync_geometry=True,
        repair_sources=True,
        apply_room_barriers=True,
        sync_room_source_mirrors=True,
        coerce_barriers=True,
        sanitize_nm_sources=True,
        ignore_errors=True,
    )


def sync_project_state_for_outputs(app: Any) -> ProjectStateSyncResult:
    return sync_project_state_from_ui(
        app,
        sync_project_form=True,
        sync_sources=True,
        sync_geometry=True,
        repair_sources=True,
        apply_room_barriers=True,
        sync_room_source_mirrors=True,
        coerce_barriers=True,
        sanitize_nm_sources=True,
        ignore_errors=True,
    )


def sync_project_state_for_results(app: Any) -> ProjectStateSyncResult:
    return sync_project_state_from_ui(
        app,
        sync_project_form=True,
        sync_sources=True,
        sync_geometry=True,
        repair_sources=True,
        apply_room_barriers=True,
        sync_room_source_mirrors=True,
        coerce_barriers=True,
        sanitize_nm_sources=True,
        ignore_errors=True,
    )
