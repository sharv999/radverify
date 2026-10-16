from __future__ import annotations

"""
UI source/geometry synchronisation guard.

MVP risk protected:
    Prevent the visible Geometry/Sources/Barriers/Results state from drifting
    away from the model used for calculations, save and output generation.

This module is intentionally UI-toolkit-light. It coordinates existing app
methods in one guarded order and preserves documented manual CT ksec overrides
when geometry-only edits re-enforce source inventory.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from modalities.registry import ct_ksec_source_types


def _ct_like_source_types() -> set[str]:
    return set(ct_ksec_source_types())

MANUAL_KSEC_KEYS = (
    "ksec_mGy_per_100mAs_at_1m",
    "ct_ksec_mGy_per_100mAs_at_1m",
    "worst_case_ksec_mGy_per_100mAs_at_1m",
    "manual_ksec_override",
    "manual_ksec_entered_by",
    "manual_ksec_reason",
    "manual_ksec_reference",
    "manual_ksec_source_reference",
    "manual_ksec_last_updated",
    "scanner_source",
    "scanner_ksec_status",
    "ksec_definition",
    "ksec_reference_distance_m",
)


@dataclass
class UISyncGuardResult:
    ok: bool = True
    room_name: str = ""
    actions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def selected_geometry_room(app: Any) -> Any | None:
    """Return the room currently driving Geometry/Sources/Barriers UI sync."""
    room = None

    if hasattr(app, "geometry_tab"):
        try:
            room_name = str(app.geometry_tab.room_select_var.get()).strip()
            if room_name:
                room = app.get_room_by_name(room_name)
        except Exception:
            room = None

    if room is None and hasattr(app, "barriers_room_var"):
        try:
            room_name = str(app.barriers_room_var.get()).strip()
            if room_name:
                room = app.get_room_by_name(room_name)
        except Exception:
            room = None

    if room is None and hasattr(app, "sources_room_var"):
        try:
            room_name = str(app.sources_room_var.get()).strip()
            if room_name:
                room = app.get_room_by_name(room_name)
        except Exception:
            room = None

    project = getattr(app, "project", None)
    rooms = list(getattr(project, "rooms", []) or [])
    if room is None and rooms:
        room = rooms[0]

    return room


def sync_geometry_source_barriers_for_room(
    app: Any,
    room: Any | None = None,
    *,
    update_geometry_fields: bool = False,
    refresh_sources: bool = True,
    refresh_barriers: bool = True,
    refresh_results: bool = True,
    update_status: bool = True,
    ignore_errors: bool = True,
) -> UISyncGuardResult:
    """
    Synchronise one room through the UI-visible model path.

    Order is deliberate:
      1. optionally push Geometry fields into the RoomGeometry model;
      2. align selected Sources/Barriers room variables;
      3. snapshot manual CT ksec overrides;
      4. regenerate geometry-owned barrier distances and locked source types;
      5. re-apply Geometry-owned scanner/source selection;
      6. restore manual CT ksec override fields if the scanner family did not change;
      7. refresh Sources, Barriers and Results from the same updated model.
    """
    if getattr(app, "_ui_sync_guard_in_progress", False):
        return UISyncGuardResult(ok=True, room_name=_room_name(room), actions=["sync_already_in_progress"])

    if room is None:
        room = selected_geometry_room(app)

    result = UISyncGuardResult(room_name=_room_name(room))
    if room is None:
        result.ok = False
        result.errors.append("No room available for Geometry/Sources sync.")
        return result

    app._ui_sync_guard_in_progress = True

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

    try:
        if update_geometry_fields and hasattr(app, "geometry_tab"):
            geometry_tab = getattr(app, "geometry_tab", None)
            if geometry_tab is not None and hasattr(geometry_tab, "update_model_from_fields"):
                run(
                    "geometry_tab.update_model_from_fields",
                    lambda: geometry_tab.update_model_from_fields(show_errors=False),
                )

        _set_room_selection_vars(app, room, result)

        manual_snapshot = _capture_manual_ct_ksec_overrides(app, room)
        if manual_snapshot:
            result.actions.append("capture_manual_ct_ksec_overrides")

        if hasattr(app, "_apply_geometry_to_selected_room_barriers"):
            run(
                "_apply_geometry_to_selected_room_barriers",
                lambda: app._apply_geometry_to_selected_room_barriers(room),
            )

        geometry_tab = getattr(app, "geometry_tab", None)
        if geometry_tab is not None and hasattr(geometry_tab, "apply_geometry_source_to_project"):
            run(
                "geometry_tab.apply_geometry_source_to_project",
                lambda: geometry_tab.apply_geometry_source_to_project(room),
            )

        restored = _restore_manual_ct_ksec_overrides(app, room, manual_snapshot)
        if restored:
            result.actions.append(f"restore_manual_ct_ksec_overrides[{restored}]")

        _clear_stale_analysis_state(app, result)

        if refresh_sources and hasattr(app, "refresh_sources_list"):
            run("refresh_sources_list", lambda: app.refresh_sources_list(preserve_index=0))
            _select_first_source(app, result)

        if refresh_barriers and hasattr(app, "refresh_barrier_schedule"):
            run("refresh_barrier_schedule", app.refresh_barrier_schedule)

        if refresh_results and hasattr(app, "refresh_results_tab"):
            run("refresh_results_tab", app.refresh_results_tab)

        if update_status and hasattr(app, "set_status"):
            run("set_status", lambda: app.set_status("Geometry, sources, barriers and results synced."))

    finally:
        app._ui_sync_guard_in_progress = False

    if result.errors:
        result.ok = False
    return result


def sync_output_relevant_ui_state(app: Any) -> UISyncGuardResult:
    """Best-effort final UI sync hook before building payload/output artifacts."""
    room = selected_geometry_room(app)
    return sync_geometry_source_barriers_for_room(
        app,
        room,
        update_geometry_fields=True,
        refresh_sources=False,
        refresh_barriers=False,
        refresh_results=False,
        update_status=False,
        ignore_errors=True,
    )


def _set_room_selection_vars(app: Any, room: Any, result: UISyncGuardResult) -> None:
    room_name = _room_name(room)
    for attr in ("sources_room_var", "barriers_room_var"):
        var = getattr(app, attr, None)
        if var is None:
            continue
        try:
            var.set(room_name)
            result.actions.append(f"set_{attr}")
        except Exception as exc:
            result.warnings.append(f"set_{attr}: {exc}")


def _clear_stale_analysis_state(app: Any, result: UISyncGuardResult) -> None:
    try:
        app.optimizer_last_recommendations = []
        result.actions.append("clear_optimizer_recommendations")
    except Exception:
        pass


def _select_first_source(app: Any, result: UISyncGuardResult) -> None:
    if not hasattr(app, "sources_list"):
        return
    try:
        app.sources_list.selection_clear(0, "end")
        app.sources_list.selection_set(0)
        app.sources_list.activate(0)
        app.current_source_index = 0
        if hasattr(app, "load_selected_source"):
            app.load_selected_source()
        result.actions.append("select_first_source")
    except Exception as exc:
        result.warnings.append(f"select_first_source: {exc}")


def _capture_manual_ct_ksec_overrides(app: Any, room: Any) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    snapshot: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for src in _sources_for_room(app, room):
        source_type = str(getattr(src, "source_type", "") or "").strip()
        if source_type not in _ct_like_source_types():
            continue
        params = getattr(src, "params", {}) or {}
        if not isinstance(params, dict):
            continue
        if str(params.get("manual_ksec_override", "") or "").strip() != "1":
            continue
        if not _positive_ksec(params.get("ksec_mGy_per_100mAs_at_1m")):
            continue
        family = str(params.get("scanner_family", "") or "").strip()
        if not family:
            continue
        key = (_room_name(room), source_type, family)
        snapshot[key] = {k: params.get(k) for k in MANUAL_KSEC_KEYS if k in params}
    return snapshot


def _restore_manual_ct_ksec_overrides(app: Any, room: Any, snapshot: Dict[Tuple[str, str, str], Dict[str, Any]]) -> int:
    if not snapshot:
        return 0
    restored = 0
    for src in _sources_for_room(app, room):
        source_type = str(getattr(src, "source_type", "") or "").strip()
        if source_type not in _ct_like_source_types():
            continue
        params = getattr(src, "params", {}) or {}
        if not isinstance(params, dict):
            params = {}
            src.params = params
        family = str(params.get("scanner_family", "") or "").strip()
        key = (_room_name(room), source_type, family)
        manual_values = snapshot.get(key)
        if not manual_values:
            continue
        params.update(manual_values)
        params["manual_ksec_override"] = "1"
        restored += 1
    return restored


def _sources_for_room(app: Any, room: Any) -> List[Any]:
    try:
        sources = list(app.get_sources_for_room(_room_name(room)))
    except Exception:
        sources = []

    # Include room.sources because some legacy workflows still mirror source
    # objects there, and enforce_room_source_types() may inspect both stores.
    for src in list(getattr(room, "sources", []) or []):
        if src not in sources:
            sources.append(src)
    return sources


def _positive_ksec(value: Any) -> bool:
    try:
        if value in (None, "", "NULL", "null", "None", "none"):
            return False
        return float(value) > 0
    except Exception:
        return False


def _room_name(room: Any) -> str:
    return str(getattr(room, "name", "") or "").strip()
