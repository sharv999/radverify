"""Read-only non-production SPECT Step 6 preview panel.

This module is presentation/adaptation only.  It converts the selected room's
existing barrier metadata into the Step 5 headless schedule request contract and
renders the returned schedule.  It deliberately contains no shielding equations
or attenuation coefficients. Step 23 may persist validated source/workload
inputs as explicitly non-production room working state, while preview geometry,
production dispatch, Results, exports, and reports remain isolated.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from math import isfinite
from tkinter import filedialog, messagebox, ttk
from typing import Any

from geometry.spect_preview_overlay import build_spect_geometry_overlay, wall_key_for_spect_preview_name
from geometry.spect_preview_position import (
    SpectPreviewPositionError,
    build_spect_preview_position,
    cardinal_distances_for_spect_preview,
)

from engine.spect_barrier_schedule import (
    SpectBarrierScheduleError,
    SpectBarrierScheduleRequest,
    SpectBarrierScheduleResult,
    calculate_spect_tc99m_barrier_schedule,
)
from modalities.spect import SpectSourceDomain, spect_source_dose_rate_constant_display
from serialization.spect_preview_state import (
    SPECT_PREVIEW_FILE_EXTENSION,
    SpectPreviewRoomPositionSnapshot,
    SpectPreviewStateSnapshot,
    load_spect_preview_state_with_status,
    save_spect_preview_state,
)
from services.unified_modality_output_sync import sync_unified_modality_outputs
from serialization.spect_working_project_state import (
    get_room_spect_working_state,
    new_spect_working_project_state,
    set_room_spect_working_state,
)


SPECT_UI_PREVIEW_CONTRACT_VERSION = 1
SPECT_UI_PREVIEW_BASELINE = "spect-ui-preview-v1-readonly-step5"
SPECT_UI_PREVIEW_STATUS = "development_nonproduction"
SPECT_UI_EDITABLE_PREVIEW_CONTRACT_VERSION = 2
SPECT_UI_EDITABLE_PREVIEW_BASELINE = "spect-ui-preview-v2-editable-source-nonpersistent"
SPECT_UI_SESSION_PREVIEW_CONTRACT_VERSION = 3
SPECT_UI_SESSION_PREVIEW_BASELINE = "spect-ui-preview-v3-session-only-state"
SPECT_UI_SESSION_PREVIEW_LABEL = "Step 8 (editable, non-production, not saved; session-only)"
SPECT_UI_PERSISTED_PREVIEW_CONTRACT_VERSION = 4
SPECT_UI_PERSISTED_PREVIEW_BASELINE = "spect-ui-preview-v4-dedicated-save-load"
SPECT_UI_GEOMETRY_EDIT_CONTRACT_VERSION = 6
SPECT_UI_GEOMETRY_EDIT_BASELINE = "spect-ui-preview-v6-source-position-edit"
SPECT_UI_PERSISTED_GEOMETRY_CONTRACT_VERSION = 7
SPECT_UI_PERSISTED_GEOMETRY_BASELINE = "spect-ui-preview-v7-persisted-source-position"
SPECT_UI_COMPATIBILITY_STATUS_CONTRACT_VERSION = 10
SPECT_UI_COMPATIBILITY_STATUS_BASELINE = "spect-ui-preview-v10-compatibility-status"
SPECT_UI_WORKFLOW_HARDENING_CONTRACT_VERSION = 11
SPECT_UI_WORKFLOW_HARDENING_BASELINE = "spect-ui-preview-v11-workflow-hardening"
SPECT_UI_DECISION_SUMMARY_CONTRACT_VERSION = 12
SPECT_UI_DECISION_SUMMARY_BASELINE = "spect-ui-preview-v12-decision-summary"

# Step 6 deliberately does not introduce editable/persisted SPECT source state.
# These values are visible in the UI as fixed development-preview assumptions.
SPECT_UI_PREVIEW_SOURCE = SpectSourceDomain(
    radionuclide="Tc99m",
    administered_activity_mbq=600.0,
    patients_per_week=20.0,
    imaging_duration_h=0.5,
)

SPECT_PREVIEW_COLUMNS = (
    ("barrier_name", "Barrier", 120),
    ("material_key", "Material", 130),
    ("distance_m", "Distance (m)", 90),
    ("occupancy_factor", "Occupancy", 80),
    ("design_goal_uSv_per_week", "Goal (µSv/wk)", 105),
    ("required_thickness_mm", "Required (mm)", 105),
    ("provided_thickness_mm", "Provided (mm)", 105),
    ("transmitted_weekly_dose_uSv", "Transmitted (µSv/wk)", 135),
    ("compliance_status", "Status", 90),
    ("caution", "Caution", 155),
)




@dataclass
class SpectPreviewSessionState:
    """Transient Step 8 UI state that must never enter project persistence.

    Raw strings are retained deliberately so the user's in-progress edits survive
    panel/tab rebuilds even when a value is temporarily invalid. Calculation
    remains gated by ``build_spect_preview_source`` on refresh.
    """

    administered_activity_mbq: str = f"{SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq:g}"
    patients_per_week: str = f"{SPECT_UI_PREVIEW_SOURCE.patients_per_week:g}"
    imaging_duration_h: str = f"{SPECT_UI_PREVIEW_SOURCE.imaging_duration_h:g}"


@dataclass

class SpectPreviewRoomPositionState:

    """Session-only source position for one SPECT room."""



    source_x_m: str

    source_y_m: str





@dataclass(frozen=True)
class SpectPreviewDecisionSummary:
    """Presentation-only summary derived entirely from a Step 5 schedule result."""

    overall_status: str
    barrier_count: int
    pass_count: int
    fail_count: int
    not_assessed_count: int
    critical_barrier_name: str | None
    maximum_required_thickness_mm: float | None
    highest_transmitted_barrier_name: str | None
    highest_transmitted_weekly_dose_uSv: float | None
    room_scatter_caution_count: int
    source_model_extrapolation_count: int


def build_spect_preview_decision_summary(
    result: SpectBarrierScheduleResult,
) -> SpectPreviewDecisionSummary:
    """Summarise existing Step 5 outputs without performing shielding physics."""

    if not isinstance(result, SpectBarrierScheduleResult):
        raise SpectPreviewError("result must be a SpectBarrierScheduleResult.")

    rows = tuple(result.rows)
    if result.fail_count:
        overall_status = "ONE OR MORE BARRIERS FAIL"
    elif result.not_assessed_count:
        overall_status = "INCOMPLETE ASSESSMENT"
    elif rows and result.pass_count == len(rows):
        overall_status = "ALL ASSESSED BARRIERS PASS"
    elif not rows:
        overall_status = "NO BARRIERS TO ASSESS"
    else:
        overall_status = "INCOMPLETE ASSESSMENT"

    critical = max(rows, key=lambda row: row.required_thickness_mm, default=None)
    transmitted_rows = tuple(
        row for row in rows if row.transmitted_weekly_dose_uSv is not None
    )
    highest_transmitted = max(
        transmitted_rows,
        key=lambda row: row.transmitted_weekly_dose_uSv,
        default=None,
    )

    return SpectPreviewDecisionSummary(
        overall_status=overall_status,
        barrier_count=len(rows),
        pass_count=result.pass_count,
        fail_count=result.fail_count,
        not_assessed_count=result.not_assessed_count,
        critical_barrier_name=critical.barrier_name if critical is not None else None,
        maximum_required_thickness_mm=(
            critical.required_thickness_mm if critical is not None else None
        ),
        highest_transmitted_barrier_name=(
            highest_transmitted.barrier_name if highest_transmitted is not None else None
        ),
        highest_transmitted_weekly_dose_uSv=(
            highest_transmitted.transmitted_weekly_dose_uSv
            if highest_transmitted is not None
            else None
        ),
        room_scatter_caution_count=sum(
            row.required_room_scatter_caution
            or row.provided_room_scatter_caution is True
            for row in rows
        ),
        source_model_extrapolation_count=sum(
            row.required_source_model_extrapolation for row in rows
        ),
    )


def spect_preview_decision_summary_lines(
    summary: SpectPreviewDecisionSummary,
) -> tuple[str, ...]:
    """Return compact UI strings for the Step 18 decision panel."""

    if not isinstance(summary, SpectPreviewDecisionSummary):
        raise SpectPreviewError("summary must be a SpectPreviewDecisionSummary.")

    critical = "—"
    if summary.critical_barrier_name is not None:
        critical = (
            f"{summary.critical_barrier_name} "
            f"({_display(summary.maximum_required_thickness_mm)} mm required)"
        )

    transmitted = "—"
    if summary.highest_transmitted_barrier_name is not None:
        transmitted = (
            f"{summary.highest_transmitted_barrier_name} "
            f"({_display(summary.highest_transmitted_weekly_dose_uSv)} µSv/week)"
        )

    return (
        f"Overall: {summary.overall_status}",
        (
            f"Barriers: {summary.barrier_count} — PASS {summary.pass_count}, "
            f"FAIL {summary.fail_count}, NOT ASSESSED {summary.not_assessed_count}"
        ),
        f"Critical barrier: {critical}",
        f"Highest transmitted dose: {transmitted}",
        (
            f"Cautions: scatter review {summary.room_scatter_caution_count}; "
            f"model extrapolation {summary.source_model_extrapolation_count}"
        ),
    )


def get_spect_preview_room_position_state(app: Any, room: Any) -> SpectPreviewRoomPositionState:
    """Return/create the transient what-if source position for ``room``."""

    if room is None:
        raise SpectPreviewError("Select a SPECT room before editing source position.")
    geometry = getattr(room, "geometry", None)
    source = getattr(geometry, "source", None)
    if geometry is None or source is None:
        raise SpectPreviewError("Selected SPECT room has no geometry source position.")
    room_name = str(getattr(room, "name", "") or getattr(geometry, "room_name", "") or "")
    states = getattr(app, "_spect_preview_room_positions", None)
    if states is None:
        states = {}
        setattr(app, "_spect_preview_room_positions", states)
    if not isinstance(states, dict):
        raise SpectPreviewError("Invalid SPECT preview room-position state.")
    state = states.get(room_name)
    if state is None:
        state = SpectPreviewRoomPositionState(
            source_x_m=f"{float(source.x_m):g}",
            source_y_m=f"{float(source.y_m):g}",
        )
        states[room_name] = state
    elif not isinstance(state, SpectPreviewRoomPositionState):
        raise SpectPreviewError("Invalid SPECT preview room-position entry.")
    return state


def capture_spect_preview_room_position_state(app: Any, room: Any) -> SpectPreviewRoomPositionState:
    state = get_spect_preview_room_position_state(app, room)
    x_var = getattr(app, "spect_preview_source_x_var", None)
    y_var = getattr(app, "spect_preview_source_y_var", None)
    if x_var is not None:
        state.source_x_m = str(x_var.get())
    if y_var is not None:
        state.source_y_m = str(y_var.get())
    return state


def _bind_spect_preview_room_position_var(app: Any, var: Any, attribute: str) -> None:
    """Mirror X/Y edits immediately into the currently selected room's session state."""

    def _capture(*_args):
        room_var = getattr(app, "sources_room_var", None)
        get_room = getattr(app, "get_room_by_name", None)
        if room_var is None or not callable(get_room):
            return
        room = get_room(room_var.get())
        if room is None:
            return
        state = get_spect_preview_room_position_state(app, room)
        setattr(state, attribute, str(var.get()))
        _set_spect_preview_state_badge(app, spect_preview_state_badge_text(app, room))

    var.trace_add("write", _capture)


def spect_preview_position_from_app(app: Any, room: Any):
    """Return validated preview geometry without mutating ``RoomGeometry``."""

    state = capture_spect_preview_room_position_state(app, room)
    geometry = getattr(room, "geometry", None)
    try:
        return build_spect_preview_position(
            geometry, source_x_m=state.source_x_m, source_y_m=state.source_y_m
        )
    except SpectPreviewPositionError as exc:
        raise SpectPreviewError(str(exc)) from exc


def load_spect_preview_room_position_vars(app: Any, room: Any) -> None:
    """Load the selected room's transient X/Y state into existing UI variables."""

    if room is None:
        return
    state = get_spect_preview_room_position_state(app, room)
    for attr, value in (("spect_preview_source_x_var", state.source_x_m), ("spect_preview_source_y_var", state.source_y_m)):
        var = getattr(app, attr, None)
        if var is not None and str(var.get()) != value:
            var.set(value)


def get_spect_preview_session_state(app: Any) -> SpectPreviewSessionState:
    """Return the app-owned, session-only SPECT preview state."""

    state = getattr(app, "_spect_preview_session_state", None)
    if state is None:
        state = SpectPreviewSessionState()
        setattr(app, "_spect_preview_session_state", state)
    elif not isinstance(state, SpectPreviewSessionState):
        raise SpectPreviewError("Invalid SPECT preview session state.")
    return state


def capture_spect_preview_session_state(app: Any) -> SpectPreviewSessionState:
    """Mirror current editable StringVars into session-only state, if present."""

    state = get_spect_preview_session_state(app)
    activity_var = getattr(app, "spect_preview_activity_var", None)
    patients_var = getattr(app, "spect_preview_patients_var", None)
    duration_var = getattr(app, "spect_preview_duration_var", None)
    if activity_var is not None:
        state.administered_activity_mbq = str(activity_var.get())
    if patients_var is not None:
        state.patients_per_week = str(patients_var.get())
    if duration_var is not None:
        state.imaging_duration_h = str(duration_var.get())
    return state



def _selected_spect_preview_room(app: Any, room: Any | None = None) -> Any:
    """Resolve the selected room for preview-only UI actions."""

    if room is not None:
        return room
    room_var = getattr(app, "sources_room_var", None)
    get_room = getattr(app, "get_room_by_name", None)
    if room_var is None or not callable(get_room):
        raise SpectPreviewError("Select a SPECT room before using preview controls.")
    selected = get_room(room_var.get())
    if selected is None:
        raise SpectPreviewError("Select a SPECT room before using preview controls.")
    if str(getattr(selected, "modality", "") or "").strip().upper() != "SPECT":
        raise SpectPreviewError("The selected room is not a SPECT room.")
    return selected


def _set_spect_preview_state_badge(app: Any, text: str) -> None:
    var = getattr(app, "spect_preview_state_badge_var", None)
    if var is not None:
        var.set(text)


def spect_preview_state_badge_text(app: Any, room: Any | None = None) -> str:
    """Summarise transient preview state without entering calculation/report paths."""

    try:
        selected = _selected_spect_preview_room(app, room)
        state = capture_spect_preview_session_state(app)
        position_state = capture_spect_preview_room_position_state(app, selected)
        source = getattr(getattr(selected, "geometry", None), "source", None)
        if source is None:
            raise SpectPreviewError("Selected SPECT room has no geometry source position.")

        # Validate source inputs through the same transient source-domain adapter used
        # by refresh. Invalid raw edits are retained but surfaced clearly.
        build_spect_preview_source(
            state.administered_activity_mbq,
            state.patients_per_week,
            state.imaging_duration_h,
        )
        position = build_spect_preview_position(
            getattr(selected, "geometry", None),
            source_x_m=position_state.source_x_m,
            source_y_m=position_state.source_y_m,
        )

        source_modified = (
            float(state.administered_activity_mbq) != SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq
            or float(state.patients_per_week) != SPECT_UI_PREVIEW_SOURCE.patients_per_week
            or float(state.imaging_duration_h) != SPECT_UI_PREVIEW_SOURCE.imaging_duration_h
        )
        position_modified = (
            position.source_x_m != float(source.x_m)
            or position.source_y_m != float(source.y_m)
        )
    except Exception as exc:
        return f"INVALID INPUT — {exc}"

    if source_modified or position_modified:
        parts = []
        if source_modified:
            parts.append("source inputs")
        if position_modified:
            parts.append("source position")
        return f"PREVIEW MODIFIED — {' + '.join(parts)} differ from baseline."
    return "ROOM BASELINE — default source inputs and saved room source position."


def reset_spect_preview_source_to_defaults(app: Any, *, refresh: bool = True) -> None:
    """Reset transient source inputs to the Step 6 defaults only."""

    state = get_spect_preview_session_state(app)
    values = (
        ("administered_activity_mbq", "spect_preview_activity_var", f"{SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq:g}"),
        ("patients_per_week", "spect_preview_patients_var", f"{SPECT_UI_PREVIEW_SOURCE.patients_per_week:g}"),
        ("imaging_duration_h", "spect_preview_duration_var", f"{SPECT_UI_PREVIEW_SOURCE.imaging_duration_h:g}"),
    )
    for state_attr, var_attr, value in values:
        setattr(state, state_attr, value)
        var = getattr(app, var_attr, None)
        if var is not None:
            var.set(value)
    _set_spect_preview_state_badge(app, spect_preview_state_badge_text(app))
    if refresh:
        refresh_spect_preview(app)


def reset_spect_preview_position_to_room_geometry(
    app: Any, room: Any | None = None, *, refresh: bool = True
) -> None:
    """Reset one room's transient preview position to saved RoomGeometry."""

    selected = _selected_spect_preview_room(app, room)
    geometry = getattr(selected, "geometry", None)
    source = getattr(geometry, "source", None)
    if geometry is None or source is None:
        raise SpectPreviewError("Selected SPECT room has no geometry source position.")
    room_name = str(getattr(selected, "name", "") or getattr(geometry, "room_name", "") or "")
    state = get_spect_preview_room_position_state(app, selected)
    state.source_x_m = f"{float(source.x_m):g}"
    state.source_y_m = f"{float(source.y_m):g}"

    for attr, value in (
        ("spect_preview_source_x_var", state.source_x_m),
        ("spect_preview_source_y_var", state.source_y_m),
    ):
        var = getattr(app, attr, None)
        if var is not None:
            var.set(value)

    _set_spect_preview_state_badge(app, spect_preview_state_badge_text(app, selected))
    if refresh:
        refresh_spect_preview(app, selected)


def _friendly_spect_source_domain_error(message: str) -> str:
    """Translate internal source-domain field names into UI-facing labels."""

    replacements = {
        "administered_activity_mbq": "Tc-99m activity",
        "patients_per_week": "Patients/week",
        "imaging_duration_h": "Imaging interval",
    }
    friendly = str(message)
    for internal, label in replacements.items():
        friendly = friendly.replace(internal, label)
    return friendly


def _validate_persisted_preview_room_position(app: Any, position: SpectPreviewRoomPositionSnapshot) -> None:
    """Validate persisted preview geometry against the current SPECT room identity."""

    get_room = getattr(app, "get_room_by_name", None)
    if not callable(get_room):
        return
    room = get_room(position.room_name)
    if room is None:
        raise SpectPreviewError(
            f"SPECT preview position refers to missing room {position.room_name!r}."
        )
    modality = str(getattr(room, "modality", "") or "").strip().upper()
    if modality != "SPECT":
        raise SpectPreviewError(
            f"SPECT preview position room {position.room_name!r} is not a SPECT room."
        )
    try:
        build_spect_preview_position(
            getattr(room, "geometry", None),
            source_x_m=position.source_x_m,
            source_y_m=position.source_y_m,
        )
    except SpectPreviewPositionError as exc:
        raise SpectPreviewError(
            f"Invalid persisted SPECT preview position for room {position.room_name!r}: {exc}"
        ) from exc


def _bind_spect_preview_session_var(app: Any, var: Any, attribute: str) -> None:
    """Keep one Tk variable mirrored into the session-only state."""

    def _capture(*_args):
        setattr(get_spect_preview_session_state(app), attribute, str(var.get()))
        _set_spect_preview_state_badge(app, spect_preview_state_badge_text(app))

    var.trace_add("write", _capture)


def spect_preview_snapshot_from_app(app: Any) -> SpectPreviewStateSnapshot:
    """Capture the dedicated non-production source and preview-position state."""

    state = capture_spect_preview_session_state(app)
    room_var = getattr(app, "sources_room_var", None)
    get_room = getattr(app, "get_room_by_name", None)
    if room_var is not None and callable(get_room):
        selected_room = get_room(room_var.get())
        if selected_room is not None:
            capture_spect_preview_room_position_state(app, selected_room)

    positions = getattr(app, "_spect_preview_room_positions", {})
    if positions is None:
        positions = {}
    if not isinstance(positions, dict):
        raise SpectPreviewError("Invalid SPECT preview room-position state.")

    room_positions = []
    for room_name in sorted(positions, key=lambda value: str(value).casefold()):
        position = positions[room_name]
        if not isinstance(position, SpectPreviewRoomPositionState):
            raise SpectPreviewError("Invalid SPECT preview room-position entry.")
        snapshot_position = SpectPreviewRoomPositionSnapshot(
            room_name=str(room_name),
            source_x_m=position.source_x_m,
            source_y_m=position.source_y_m,
        )
        _validate_persisted_preview_room_position(app, snapshot_position)
        room_positions.append(snapshot_position)

    return SpectPreviewStateSnapshot(
        administered_activity_mbq=state.administered_activity_mbq,
        patients_per_week=state.patients_per_week,
        imaging_duration_h=state.imaging_duration_h,
        room_positions=tuple(room_positions),
    )


def apply_spect_preview_snapshot(app: Any, snapshot: SpectPreviewStateSnapshot) -> None:
    """Restore a dedicated preview snapshot into preview session/UI state only."""

    if not isinstance(snapshot, SpectPreviewStateSnapshot):
        raise SpectPreviewError("snapshot must be a SpectPreviewStateSnapshot.")
    for position in snapshot.room_positions:
        _validate_persisted_preview_room_position(app, position)

    state = get_spect_preview_session_state(app)
    state.administered_activity_mbq = snapshot.administered_activity_mbq
    state.patients_per_week = snapshot.patients_per_week
    state.imaging_duration_h = snapshot.imaging_duration_h

    restored_positions = {
        position.room_name: SpectPreviewRoomPositionState(
            source_x_m=position.source_x_m,
            source_y_m=position.source_y_m,
        )
        for position in snapshot.room_positions
    }
    setattr(app, "_spect_preview_room_positions", restored_positions)

    for attr, value in (
        ("spect_preview_activity_var", snapshot.administered_activity_mbq),
        ("spect_preview_patients_var", snapshot.patients_per_week),
        ("spect_preview_duration_var", snapshot.imaging_duration_h),
    ):
        var = getattr(app, attr, None)
        if var is not None:
            var.set(value)

    room_var = getattr(app, "sources_room_var", None)
    get_room = getattr(app, "get_room_by_name", None)
    if room_var is not None and callable(get_room):
        room = get_room(room_var.get())
        if room is not None:
            load_spect_preview_room_position_vars(app, room)



def reset_spect_preview_source_from_ui(app: Any) -> None:
    """UI-safe source reset with actionable feedback instead of callback tracebacks."""

    try:
        reset_spect_preview_source_to_defaults(app)
    except Exception as exc:
        _set_spect_preview_state_badge(app, f"RESET FAILED — {exc}")
        messagebox.showerror("Reset SPECT Preview Source failed", str(exc))


def reset_spect_preview_position_from_ui(app: Any) -> None:
    """UI-safe geometry reset with actionable feedback instead of callback tracebacks."""

    try:
        reset_spect_preview_position_to_room_geometry(app)
    except Exception as exc:
        _set_spect_preview_state_badge(app, f"RESET FAILED — {exc}")
        messagebox.showerror("Reset SPECT Preview Position failed", str(exc))


def save_spect_preview_from_ui(app: Any) -> None:
    """Save preview-only source inputs and what-if positions to .spectpreview.json."""

    filename = filedialog.asksaveasfilename(
        defaultextension=SPECT_PREVIEW_FILE_EXTENSION,
        filetypes=[
            ("SPECT Preview", f"*{SPECT_PREVIEW_FILE_EXTENSION}"),
            ("JSON Files", "*.json"),
            ("All Files", "*.*"),
        ],
    )
    if not filename:
        return
    try:
        save_spect_preview_state(filename, spect_preview_snapshot_from_app(app))
        status = getattr(app, "spect_preview_status_var", None)
        if status is not None:
            status.set(f"Saved non-production SPECT preview: {filename}")
        compatibility_status = getattr(app, "spect_preview_compatibility_status_var", None)
        if compatibility_status is not None:
            compatibility_status.set(
                "Current — saved with the installed SPECT preview physics provenance."
            )
    except Exception as exc:
        messagebox.showerror("Save SPECT Preview failed", str(exc))


def load_spect_preview_from_ui(app: Any) -> None:
    """Load a dedicated preview file without touching normal project state."""

    filename = filedialog.askopenfilename(
        filetypes=[
            ("SPECT Preview", f"*{SPECT_PREVIEW_FILE_EXTENSION}"),
            ("JSON Files", "*.json"),
            ("All Files", "*.*"),
        ],
    )
    if not filename:
        return
    try:
        load_result = load_spect_preview_state_with_status(filename)
        apply_spect_preview_snapshot(app, load_result.snapshot)
        compatibility_status = getattr(app, "spect_preview_compatibility_status_var", None)
        if compatibility_status is not None:
            compatibility_status.set(load_result.message)
        refresh_spect_preview(app)
    except Exception as exc:
        compatibility_status = getattr(app, "spect_preview_compatibility_status_var", None)
        if compatibility_status is not None:
            compatibility_status.set(f"Rejected — preview not loaded: {exc}")
        messagebox.showerror("Load SPECT Preview failed", str(exc))


class SpectPreviewError(ValueError):
    """Raised when room metadata cannot be adapted to the Step 5 preview."""


def spect_material_key_for_room_barrier(barrier: Any) -> str:
    """Map room construction labels to Step 3/5 material keys without physics."""

    material = str(getattr(barrier, "material", "") or "").strip().lower()
    legacy = str(getattr(barrier, "material_legacy", "") or "").strip().lower()

    # Prefer the canonical material-family field. Legacy text is consulted only
    # for density/variant detail or when the canonical field is blank.
    if material in {"pb", "lead"} or "lead" in material:
        return "lead"
    if "gypsum" in material or "plasterboard" in material or "drywall" in material:
        return "gypsum"
    if "concrete" in material:
        detail = f"{material} {legacy}"
        if "light" in detail or "1600" in detail:
            return "concrete_1600kg_m3"
        return "concrete_2300kg_m3"
    if "glass" in material:
        return "glass"
    if "steel" in material or "a514" in material:
        return "steel_a514"

    if not material:
        if "lead" in legacy or " pb" in f" {legacy}":
            return "lead"
        if "gypsum" in legacy or "plasterboard" in legacy or "drywall" in legacy:
            return "gypsum"
        if "concrete" in legacy:
            if "light" in legacy or "1600" in legacy:
                return "concrete_1600kg_m3"
            return "concrete_2300kg_m3"
        if "glass" in legacy:
            return "glass"
        if "steel" in legacy or "a514" in legacy:
            return "steel_a514"

    raise SpectPreviewError(
        f"Barrier {getattr(barrier, 'name', '')!r} uses unsupported SPECT preview "
        f"material {getattr(barrier, 'material', '')!r}."
    )


def build_spect_preview_barrier_requests(
    room: Any, *, source_x_m: float | None = None, source_y_m: float | None = None
) -> tuple[SpectBarrierScheduleRequest, ...]:
    """Adapt existing room barrier fields into the canonical Step 5 requests."""

    if room is None:
        raise SpectPreviewError("Select a SPECT room before refreshing the preview.")
    modality = str(getattr(room, "modality", "") or "").strip().upper()
    if modality != "SPECT":
        raise SpectPreviewError("The selected room is not a SPECT room.")

    barriers = tuple(getattr(room, "barriers", ()) or ())
    distance_overrides = None
    if source_x_m is not None or source_y_m is not None:
        if source_x_m is None or source_y_m is None:
            raise SpectPreviewError("Both preview source coordinates are required.")
        try:
            distance_overrides = cardinal_distances_for_spect_preview(
                getattr(room, "geometry", None), source_x_m=source_x_m, source_y_m=source_y_m
            )
        except SpectPreviewPositionError as exc:
            raise SpectPreviewError(str(exc)) from exc
    if not barriers:
        raise SpectPreviewError("The selected SPECT room has no barriers to preview.")

    requests: list[SpectBarrierScheduleRequest] = []
    for index, barrier in enumerate(barriers):
        name = str(getattr(barrier, "name", "") or f"Barrier {index + 1}").strip()
        try:
            request = SpectBarrierScheduleRequest(
                barrier_id=f"room-barrier-{index + 1}",
                barrier_name=name,
                material_key=spect_material_key_for_room_barrier(barrier),
                distance_m=(
                    float(distance_overrides[wall_key_for_spect_preview_name(name)])
                    if distance_overrides is not None and wall_key_for_spect_preview_name(name) in distance_overrides
                    else float(getattr(barrier, "distance_m", 0.0))
                ),
                occupancy_factor=float(getattr(barrier, "occupancy_factor", 0.0)),
                design_goal_uSv_per_week=float(
                    getattr(barrier, "design_goal_uSv_per_week", 0.0)
                ),
                provided_thickness_mm=float(getattr(barrier, "thickness_mm", 0.0)),
                source_name="SPECT Patient Source — read-only preview",
            )
        except (TypeError, ValueError, SpectBarrierScheduleError) as exc:
            raise SpectPreviewError(f"Barrier {name!r}: {exc}") from exc
        requests.append(request)
    return tuple(requests)


def build_spect_preview_source(
    administered_activity_mbq: Any,
    patients_per_week: Any,
    imaging_duration_h: Any,
    *,
    radionuclide: str = "Tc99m",
) -> SpectSourceDomain:
    """Build a validated preview-only source from editable presentation values.

    This function creates transient calculation input only.  It does not read or
    write project sources, room state, serialization payloads, Results, or reports.
    """

    raw_fields = (
        ("Tc-99m activity", administered_activity_mbq),
        ("Patients/week", patients_per_week),
        ("Imaging interval", imaging_duration_h),
    )
    parsed = []
    for label, raw_value in raw_fields:
        if str(raw_value).strip() == "":
            raise SpectPreviewError(
                f"Invalid SPECT preview source input: {label} is required."
            )
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise SpectPreviewError(
                f"Invalid SPECT preview source input: {label} must be numeric."
            ) from exc
        if not isfinite(numeric):
            raise SpectPreviewError(
                f"Invalid SPECT preview source input: {label} must be finite."
            )
        parsed.append(numeric)

    try:
        return SpectSourceDomain(
            radionuclide=radionuclide,
            administered_activity_mbq=parsed[0],
            patients_per_week=parsed[1],
            imaging_duration_h=parsed[2],
        )
    except (TypeError, ValueError) as exc:
        raise SpectPreviewError(
            f"Invalid SPECT preview source input: {_friendly_spect_source_domain_error(str(exc))}"
        ) from exc


def persist_spect_preview_source_to_room(app: Any, room: Any | None = None) -> bool:
    """Persist the current valid Tc-99m source/workload as SPECT working state.

    Step 23 stores source/workload only. Preview X/Y what-if positions remain
    transient or in the dedicated .spectpreview.json format; normal project
    geometry remains the authoritative durable geometry.
    """

    if getattr(app, "_loading_spect_working_state", False):
        return False
    selected = _selected_spect_preview_room(app, room)
    if selected is None:
        return False
    if str(getattr(selected, "modality", "") or "").strip().upper() != "SPECT":
        return False
    try:
        state = new_spect_working_project_state(spect_preview_source_from_app(app))
        set_room_spect_working_state(selected, state)
    except Exception:
        # Invalid/incomplete UI edits must never overwrite the last validated
        # durable working state.
        return False
    return True


def load_spect_working_state_into_preview(app: Any, room: Any | None) -> bool:
    """Restore durable SPECT source/workload inputs into transient preview vars."""

    if room is None:
        return False
    if str(getattr(room, "modality", "") or "").strip().upper() != "SPECT":
        return False
    try:
        state = get_room_spect_working_state(room)
    except Exception:
        # Normal project loading validates persisted state fail-closed. UI
        # refresh therefore does not try to repair or reinterpret invalid state.
        return False
    if state is None:
        return False

    app._loading_spect_working_state = True
    try:
        session = get_spect_preview_session_state(app)
        values = {
            "administered_activity_mbq": f"{state.source.administered_activity_mbq:g}",
            "patients_per_week": f"{state.source.patients_per_week:g}",
            "imaging_duration_h": f"{state.source.imaging_duration_h:g}",
        }
        for state_attr, var_attr in (
            ("administered_activity_mbq", "spect_preview_activity_var"),
            ("patients_per_week", "spect_preview_patients_var"),
            ("imaging_duration_h", "spect_preview_duration_var"),
        ):
            value = values[state_attr]
            setattr(session, state_attr, value)
            var = getattr(app, var_attr, None)
            if var is not None:
                var.set(value)
    finally:
        app._loading_spect_working_state = False
    return True


def spect_preview_source_from_app(app: Any) -> SpectSourceDomain:
    """Read transient Step 7 StringVars and return a validated source.

    Apps without the Step 7 variables retain the Step 6 fixed-source behaviour,
    which keeps the presentation adapter backwards compatible for tests/helpers.
    """

    activity_var = getattr(app, "spect_preview_activity_var", None)
    patients_var = getattr(app, "spect_preview_patients_var", None)
    duration_var = getattr(app, "spect_preview_duration_var", None)
    if activity_var is None or patients_var is None or duration_var is None:
        state = getattr(app, "_spect_preview_session_state", None)
        if isinstance(state, SpectPreviewSessionState):
            return build_spect_preview_source(
                state.administered_activity_mbq,
                state.patients_per_week,
                state.imaging_duration_h,
            )
        return SPECT_UI_PREVIEW_SOURCE
    state = capture_spect_preview_session_state(app)
    return build_spect_preview_source(
        state.administered_activity_mbq,
        state.patients_per_week,
        state.imaging_duration_h,
    )


def calculate_spect_room_preview(
    room: Any,
    *,
    source: SpectSourceDomain = SPECT_UI_PREVIEW_SOURCE,
    source_x_m: float | None = None,
    source_y_m: float | None = None,
) -> SpectBarrierScheduleResult:
    """Return the Step 5 schedule for the selected room; no UI physics occurs here."""

    requests = build_spect_preview_barrier_requests(
        room, source_x_m=source_x_m, source_y_m=source_y_m
    )
    try:
        return calculate_spect_tc99m_barrier_schedule(source, requests)
    except SpectBarrierScheduleError as exc:
        raise SpectPreviewError(str(exc)) from exc


def _display(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def spect_preview_display_rows(
    result: SpectBarrierScheduleResult,
) -> tuple[dict[str, str], ...]:
    """Flatten Step 5 rows into presentation-only strings for the Treeview."""

    if not isinstance(result, SpectBarrierScheduleResult):
        raise SpectPreviewError("result must be a SpectBarrierScheduleResult.")
    rows: list[dict[str, str]] = []
    for row in result.rows:
        cautions = []
        if row.required_room_scatter_caution or row.provided_room_scatter_caution is True:
            cautions.append("scatter review")
        if row.required_source_model_extrapolation:
            cautions.append("model extrapolation")
        rows.append(
            {
                "barrier_name": row.barrier_name,
                "material_key": row.material_key,
                "distance_m": _display(row.distance_m),
                "occupancy_factor": _display(row.occupancy_factor),
                "design_goal_uSv_per_week": _display(row.design_goal_uSv_per_week),
                "required_thickness_mm": _display(row.required_thickness_mm),
                "provided_thickness_mm": _display(row.provided_thickness_mm),
                "transmitted_weekly_dose_uSv": _display(row.transmitted_weekly_dose_uSv),
                "compliance_status": row.compliance_status,
                "caution": "; ".join(cautions) if cautions else "—",
            }
        )
    return tuple(rows)


def refresh_spect_preview(app, room: Any | None = None) -> None:
    """Refresh the read-only Step 6 panel from the selected room."""

    tree = getattr(app, "spect_preview_tree", None)
    status_var = getattr(app, "spect_preview_status_var", None)
    if tree is not None:
        for item in tree.get_children():
            tree.delete(item)

    selected_room = room
    if selected_room is None and hasattr(app, "sources_room_var"):
        selected_room = app.get_room_by_name(app.sources_room_var.get())

    try:
        load_spect_preview_room_position_vars(app, selected_room)
        position = spect_preview_position_from_app(app, selected_room)
        result = calculate_spect_room_preview(
            selected_room,
            source=spect_preview_source_from_app(app),
            source_x_m=position.source_x_m,
            source_y_m=position.source_y_m,
        )
        rows = spect_preview_display_rows(result)
        geometry = getattr(selected_room, "geometry", None)
        app.spect_preview_geometry_overlay = build_spect_geometry_overlay(
            result, geometry, source_x_m=position.source_x_m, source_y_m=position.source_y_m
        )
    except Exception as exc:
        app.spect_preview_geometry_overlay = None
        _set_spect_preview_state_badge(app, f"INVALID INPUT — {exc}")
        summary_var = getattr(app, "spect_preview_decision_summary_var", None)
        if summary_var is not None:
            summary_var.set("Preview summary unavailable until inputs are valid.")
        if status_var is not None:
            status_var.set(f"SPECT preview unavailable: {exc}")
        sync_unified_modality_outputs(app)
        return

    _set_spect_preview_state_badge(
        app, spect_preview_state_badge_text(app, selected_room)
    )

    summary = build_spect_preview_decision_summary(result)
    summary_var = getattr(app, "spect_preview_decision_summary_var", None)
    if summary_var is not None:
        summary_var.set("\n".join(spect_preview_decision_summary_lines(summary)))

    if tree is not None:
        for row in rows:
            tree.insert(
                "",
                "end",
                values=tuple(row[key] for key, _heading, _width in SPECT_PREVIEW_COLUMNS),
            )

    if status_var is not None:
        flags = []
        if result.requires_room_scatter_review:
            flags.append("scatter review required")
        if result.contains_source_model_extrapolation:
            flags.append("model extrapolation present")
        suffix = f" — {'; '.join(flags)}" if flags else ""
        status_var.set(
            f"Step 5 schedule — {len(rows)} barriers — PASS {result.pass_count}, "
            f"FAIL {result.fail_count}, NOT ASSESSED {result.not_assessed_count}{suffix}."
        )

    sync_unified_modality_outputs(app)


def build_spect_preview_panel(app, parent) -> None:
    """Build the isolated editable, non-persistent SPECT Step 7 preview."""

    frame = ttk.LabelFrame(
        parent, text="SPECT Preview — Step 18 (editable, non-production; decision summary preview)"
    )
    frame.grid(row=4, column=0, sticky="nsew", padx=4, pady=8)
    frame.columnconfigure(0, weight=1)

    ttk.Label(
        frame,
        text=(
            "Preview-only Tc-99m source inputs. Values persist only for this running application "
            "session (including room/tab switching) and may optionally be saved/loaded through a "
            "dedicated .spectpreview.json payload. The payload may include per-room preview X/Y "
            "positions, but these remain preview-only and do not modify saved RoomGeometry. Step 23 "
            "allows validated Tc-99m source/workload inputs to persist as non-production working-project "
            "state; preview what-if geometry remains separate. Nothing enters Results, reports, export, "
            "or production calculation dispatch. A transient Geometry-tab overlay is refreshed from the "
            "Step 5 schedule."
        ),
        wraplength=1000,
        justify="left",
    ).grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

    source_frame = ttk.Frame(frame)
    source_frame.grid(row=1, column=0, sticky="w", padx=6, pady=4)

    session_state = get_spect_preview_session_state(app)
    app.spect_preview_activity_var = tk.StringVar(
        value=session_state.administered_activity_mbq
    )
    app.spect_preview_patients_var = tk.StringVar(
        value=session_state.patients_per_week
    )
    app.spect_preview_duration_var = tk.StringVar(
        value=session_state.imaging_duration_h
    )
    _bind_spect_preview_session_var(
        app, app.spect_preview_activity_var, "administered_activity_mbq"
    )
    _bind_spect_preview_session_var(
        app, app.spect_preview_patients_var, "patients_per_week"
    )
    _bind_spect_preview_session_var(
        app, app.spect_preview_duration_var, "imaging_duration_h"
    )

    ttk.Label(source_frame, text="Tc-99m activity (MBq)").grid(
        row=0, column=0, sticky="w", padx=(0, 4)
    )
    ttk.Entry(source_frame, textvariable=app.spect_preview_activity_var, width=10).grid(
        row=0, column=1, sticky="w", padx=(0, 12)
    )
    ttk.Label(source_frame, text="Patients/week").grid(
        row=0, column=2, sticky="w", padx=(0, 4)
    )
    ttk.Entry(source_frame, textvariable=app.spect_preview_patients_var, width=10).grid(
        row=0, column=3, sticky="w", padx=(0, 12)
    )
    ttk.Label(source_frame, text="Imaging interval (h)").grid(
        row=0, column=4, sticky="w", padx=(0, 4)
    )
    ttk.Entry(source_frame, textvariable=app.spect_preview_duration_var, width=10).grid(
        row=0, column=5, sticky="w"
    )

    app.spect_preview_source_x_var = tk.StringVar(value="")
    app.spect_preview_source_y_var = tk.StringVar(value="")
    _bind_spect_preview_room_position_var(app, app.spect_preview_source_x_var, "source_x_m")
    _bind_spect_preview_room_position_var(app, app.spect_preview_source_y_var, "source_y_m")
    ttk.Label(source_frame, text="Preview source X from West (m)").grid(
        row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0)
    )
    ttk.Entry(source_frame, textvariable=app.spect_preview_source_x_var, width=10).grid(
        row=1, column=1, sticky="w", padx=(0, 12), pady=(4, 0)
    )
    ttk.Label(source_frame, text="Preview source Y from South (m)").grid(
        row=1, column=2, sticky="w", padx=(0, 4), pady=(4, 0)
    )
    ttk.Entry(source_frame, textvariable=app.spect_preview_source_y_var, width=10).grid(
        row=1, column=3, sticky="w", padx=(0, 12), pady=(4, 0)
    )

    app.spect_preview_mode_badge_var = tk.StringVar(
        value="NON-PRODUCTION PREVIEW — excluded from normal project save, Results and reports."
    )
    ttk.Label(
        frame,
        textvariable=app.spect_preview_mode_badge_var,
        justify="left",
    ).grid(row=2, column=0, sticky="ew", padx=6, pady=(6, 0))

    app.spect_preview_state_badge_var = tk.StringVar(
        value="ROOM BASELINE — refresh to validate current preview inputs."
    )
    ttk.Label(
        frame,
        textvariable=app.spect_preview_state_badge_var,
        justify="left",
    ).grid(row=3, column=0, sticky="ew", padx=6, pady=(2, 0))

    app.spect_preview_compatibility_status_var = tk.StringVar(
        value="No preview file loaded — current in-session preview state."
    )
    ttk.Label(
        frame,
        textvariable=app.spect_preview_compatibility_status_var,
        wraplength=1000,
        justify="left",
        foreground="#555555",
    ).grid(row=4, column=0, sticky="ew", padx=6, pady=(4, 0))

    app.spect_preview_status_var = tk.StringVar(
        value="Select a SPECT room, then refresh the non-production preview."
    )
    ttk.Label(
        frame,
        textvariable=app.spect_preview_status_var,
        wraplength=1000,
        justify="left",
        foreground="#555555",
    ).grid(row=5, column=0, sticky="ew", padx=6, pady=4)

    summary_frame = ttk.LabelFrame(frame, text="Preview calculation summary — non-production")
    summary_frame.grid(row=6, column=0, sticky="ew", padx=6, pady=(2, 4))
    summary_frame.columnconfigure(0, weight=1)
    app.spect_preview_decision_summary_var = tk.StringVar(
        value="Refresh the SPECT preview to calculate the decision summary."
    )
    ttk.Label(
        summary_frame,
        textvariable=app.spect_preview_decision_summary_var,
        wraplength=1000,
        justify="left",
    ).grid(row=0, column=0, sticky="ew", padx=6, pady=6)

    action_frame = ttk.Frame(frame)
    action_frame.grid(row=7, column=0, sticky="w", padx=6, pady=4)
    ttk.Button(
        action_frame,
        text="Refresh SPECT Preview",
        command=lambda: refresh_spect_preview(app),
    ).grid(row=0, column=0, sticky="w")
    ttk.Button(
        action_frame,
        text="Save SPECT Preview...",
        command=lambda: save_spect_preview_from_ui(app),
    ).grid(row=0, column=1, sticky="w", padx=(8, 0))
    ttk.Button(
        action_frame,
        text="Load SPECT Preview...",
        command=lambda: load_spect_preview_from_ui(app),
    ).grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Button(
        action_frame,
        text="Reset Source Inputs",
        command=lambda: reset_spect_preview_source_from_ui(app),
    ).grid(row=0, column=3, sticky="w", padx=(8, 0))
    ttk.Button(
        action_frame,
        text="Reset Position to Room Geometry",
        command=lambda: reset_spect_preview_position_from_ui(app),
    ).grid(row=0, column=4, sticky="w", padx=(8, 0))

    tree_frame = ttk.Frame(frame)
    tree_frame.grid(row=8, column=0, sticky="nsew", padx=6, pady=(4, 6))
    tree_frame.columnconfigure(0, weight=1)

    keys = tuple(key for key, _heading, _width in SPECT_PREVIEW_COLUMNS)
    tree = ttk.Treeview(tree_frame, columns=keys, show="headings", height=7)
    for key, heading, width in SPECT_PREVIEW_COLUMNS:
        tree.heading(key, text=heading)
        tree.column(key, width=width, minwidth=65, stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")

    scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    scroll.grid(row=1, column=0, sticky="ew")
    tree.configure(xscrollcommand=scroll.set)
    app.spect_preview_tree = tree


def build_spect_source_controls(app, parent) -> None:
    """Build SPECT inputs inside the unified Sources tab without a preview panel."""
    session_state = get_spect_preview_session_state(app)
    if not hasattr(app, "spect_preview_activity_var"):
        app.spect_preview_activity_var = tk.StringVar(value=session_state.administered_activity_mbq)
    if not hasattr(app, "spect_preview_patients_var"):
        app.spect_preview_patients_var = tk.StringVar(value=session_state.patients_per_week)
    if not hasattr(app, "spect_preview_duration_var"):
        app.spect_preview_duration_var = tk.StringVar(value=session_state.imaging_duration_h)
    if not hasattr(app, "spect_preview_source_x_var"):
        app.spect_preview_source_x_var = tk.StringVar(value="")
    if not hasattr(app, "spect_preview_source_y_var"):
        app.spect_preview_source_y_var = tk.StringVar(value="")
    if not hasattr(app, "spect_preview_state_badge_var"):
        app.spect_preview_state_badge_var = tk.StringVar(value="")
    if not hasattr(app, "spect_preview_status_var"):
        app.spect_preview_status_var = tk.StringVar(value="")
    if not hasattr(app, "spect_preview_decision_summary_var"):
        app.spect_preview_decision_summary_var = tk.StringVar(value="")

    room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
    room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    if room is not None:
        load_spect_working_state_into_preview(app, room)
        load_spect_preview_room_position_vars(app, room)

    parent.columnconfigure(1, weight=1)
    ttk.Label(parent, text="Radionuclide").grid(row=0, column=0, sticky="w", padx=4, pady=4)
    radionuclide_var = getattr(app, "spect_source_radionuclide_var", None)
    if radionuclide_var is None:
        radionuclide_var = tk.StringVar(value="Tc-99m")
        app.spect_source_radionuclide_var = radionuclide_var
    ttk.Entry(parent, textvariable=radionuclide_var, state="readonly").grid(
        row=0, column=1, sticky="ew", padx=4, pady=4
    )

    dose_rate_constant_var = getattr(app, "spect_dose_rate_constant_var", None)
    if dose_rate_constant_var is None:
        dose_rate_constant_var = tk.StringVar(value="")
        app.spect_dose_rate_constant_var = dose_rate_constant_var
    try:
        dose_rate_constant_var.set(
            spect_source_dose_rate_constant_display(spect_preview_source_from_app(app))
        )
    except Exception:
        dose_rate_constant_var.set("")
    ttk.Label(parent, text="Dose rate constant").grid(
        row=1, column=0, sticky="w", padx=4, pady=4
    )
    ttk.Entry(parent, textvariable=dose_rate_constant_var, state="readonly").grid(
        row=1, column=1, sticky="ew", padx=4, pady=4
    )

    rows = (
        ("Administered activity (MBq)", app.spect_preview_activity_var),
        ("Patients per week", app.spect_preview_patients_var),
        ("Imaging duration (h)", app.spect_preview_duration_var),
    )
    for row, (label, variable) in enumerate(rows, start=2):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=4, pady=4)

    ttk.Separator(parent, orient="horizontal").grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 6)
    )
    ttk.Label(
        parent,
        text="Patient/source position is controlled in Geometry. Barrier results are shown in Results.",
        foreground="#555555",
        wraplength=760,
        justify="left",
    ).grid(row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 6))

    if not getattr(app, "_spect_unified_source_traces_bound", False):
        def _changed(*_args):
            if getattr(app, "_loading_spect_working_state", False):
                return
            capture_spect_preview_session_state(app)
            selected = _selected_spect_preview_room(app)
            if selected is not None:
                persist_spect_preview_source_to_room(app, selected)
                refresh_spect_preview(app, selected)

        for variable in (
            app.spect_preview_activity_var,
            app.spect_preview_patients_var,
            app.spect_preview_duration_var,
        ):
            variable.trace_add("write", _changed)
        app._spect_unified_source_traces_bound = True

    if room is not None:
        persist_spect_preview_source_to_room(app, room)
        refresh_spect_preview(app, room)
