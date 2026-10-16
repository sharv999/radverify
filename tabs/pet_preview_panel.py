"""Non-production PET source-domain preview panel for the Sources tab.

This module is the first deliberately isolated PET UI integration layer.  It
uses the frozen PET source-domain/physics contracts and the isolated PET
calculation service to provide source and multiple-barrier previews. It does not
create project sources, enter production dispatch, or generate reports. Preview
state persistence uses a separate explicitly non-production file contract.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from serialization.pet_calculation_request_contract import PetCalculationRequestEnvelope
from serialization.pet_working_project_state import (
    PetWorkingProjectState,
    get_room_pet_working_state,
    set_room_pet_working_state,
)

from serialization.pet_preview_state import (
    PET_PREVIEW_FILE_EXTENSION,
    PET_PREVIEW_STATE_BASELINE,
    PetPreviewStateSnapshot,
    load_pet_preview_state,
    save_pet_preview_state,
)

from services.pet_calculation_service import (
    PetBarrierCalculationRequest,
    run_pet_calculation_service,
)
from services.pet_combined_report_payload_harness import (
    build_non_issueable_pet_combined_report_payload_envelope,
)
from services.pet_report_payload_harness import build_non_issueable_pet_report_payload
from services.pet_report_plain_text_preview import (
    render_non_issueable_pet_plain_text_preview,
)
from services.pet_report_section_view_model import (
    build_non_issueable_pet_report_section_view_model,
)
from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.unified_modality_output_sync import sync_unified_modality_outputs

from geometry.pet_preview_overlay import build_pet_input_geometry_overlay
from geometry.pet_preview_position import PetPreviewPosition, default_pet_preview_position

from tabs.pet_preview_output_contract import (
    PET_PREVIEW_OUTPUT_BASELINE,
    PET_PREVIEW_OUTPUT_CONTRACT_VERSION,
    build_pet_preview_output_contract,
)

from tabs.pet_preview_ui_contract import (
    PET_POSITION_UI_FIELDS,
    PET_PREVIEW_UI_BASELINE,
    PET_PREVIEW_UI_CONTRACT_VERSION,
    PET_SOURCE_UI_DEFAULTS,
    PET_SOURCE_UI_FIELDS,
    PET_ROOM_MODE_OPTIONS,
    display_label,
)

from modalities.pet import (
    PET_RADIONUCLIDES,
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST,
    PET_RADIONUCLIDE_DATASET_METADATA,
    PetContractError,
    PetExposurePhase,
    PetSourceDomain,
    calculate_pet_weekly_dose_at_1m,
    calculate_pet_decay_factor_at_time,
)

PET_UI_PREVIEW_CONTRACT_VERSION = 14
PET_UI_PREVIEW_BASELINE = "pet-ui-preview-v14-activity-retention"
PET_PREVIEW_MATERIALS = ("lead", "concrete_2350kg_m3", "iron")

PET_BARRIER_RESULTS_PREVIEW_COLUMNS = (
    ("barrier_name", "Barrier", 120),
    ("material", "Material", 100),
    ("distance_m", "Distance (m)", 90),
    ("occupancy_factor", "Occupancy", 80),
    ("design_goal_uSv_per_week", "Design goal (µSv/wk)", 130),
    ("unshielded_weekly_dose_uSv", "Unshielded dose (µSv/wk)", 155),
    ("required_thickness_mm", "Required thickness (mm)", 145),
    ("provided_thickness_mm", "Provided thickness (mm)", 145),
    ("margin_mm", "Margin (mm)", 95),
    ("transmitted_dose_uSv_per_week", "Transmitted dose (µSv/wk)", 160),
    ("barrier_transmission_factor_B", "Transmission B", 105),
    ("required_tvl_count", "Required TVLs", 95),
    ("compliance_status", "Status", 80),
)


def _pet_barrier_preview_text(value: Any, *, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}g}"
    return str(value)


def build_pet_barrier_results_preview_rows(app, room: Any | None = None) -> tuple[dict[str, str], ...]:
    """Return read-only PET barrier display rows from the canonical Results model only."""
    selected_room = room
    if selected_room is None:
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        selected_room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    if selected_room is None:
        raise PetContractError("Select a room before displaying PET barrier results.")
    if not hasattr(app, "get_room_results_model"):
        raise PetContractError("Canonical PET Results are unavailable for preview.")

    rows = app.get_room_results_model(selected_room)
    preview_rows = []
    for row in rows:
        if str(row.get("results_source", "")) != "persisted_pet_single_source":
            raise PetContractError("PET barrier preview received a non-PET canonical Results row.")
        preview_rows.append({
            key: _pet_barrier_preview_text(row.get(key))
            for key, _heading, _width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS
        })
    if not preview_rows:
        raise PetContractError("Canonical PET Results contain no barrier rows.")
    return tuple(preview_rows)


def refresh_pet_barrier_results_preview(app, room: Any | None = None) -> None:
    """Refresh the non-production PET barrier Treeview without opening output paths."""
    tree = getattr(app, "pet_barrier_results_preview_tree", None)
    status_var = getattr(app, "pet_barrier_results_preview_status_var", None)
    if tree is None:
        return
    for item in tree.get_children():
        tree.delete(item)
    try:
        rows = build_pet_barrier_results_preview_rows(app, room=room)
    except Exception as exc:
        if status_var is not None:
            status_var.set(f"PET barrier results unavailable: {exc}")
        return

    for row in rows:
        values = tuple(row[key] for key, _heading, _width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS)
        tree.insert("", "end", values=values)
    if status_var is not None:
        status_var.set(
            f"Canonical PET Results model — {len(rows)} barriers — read-only non-production preview."
        )


def pet_material_key_for_room_barrier(barrier: Any) -> str:
    """Map a room barrier material to the approved PET attenuation dataset key."""

    material = str(getattr(barrier, "material", "") or "").strip().lower()
    legacy = str(getattr(barrier, "material_legacy", "") or "").strip().lower()
    text = material or legacy
    if "concrete" in text:
        return "concrete_2350kg_m3"
    if any(token in text for token in ("iron", "steel")):
        return "iron"
    if any(token in text for token in ("pb", "lead")):
        return "lead"
    raise PetContractError(
        f"Barrier {getattr(barrier, 'name', '')!r} uses unsupported PET preview material "
        f"{getattr(barrier, 'material', '')!r}."
    )


def _pet_distance_key_for_barrier(barrier: Any) -> str | None:
    name = str(getattr(barrier, "name", "") or "").strip().lower()
    role = str(getattr(barrier, "barrier_role", "") or "").strip().lower()
    aliases = {
        "n": "N", "north": "N", "n wall": "N", "north wall": "N",
        "e": "E", "east": "E", "e wall": "E", "east wall": "E",
        "s": "S", "south": "S", "s wall": "S", "south wall": "S",
        "w": "W", "west": "W", "w wall": "W", "west wall": "W",
        "floor": "Floor", "ceiling": "Ceiling",
    }
    if name in aliases:
        return aliases[name]
    if role in {"floor", "ceiling"}:
        return role.title()
    return None


def build_pet_preview_barrier_values_from_room(
    room: Any,
    position: PetPreviewPosition | None = None,
) -> tuple[dict[str, str], ...]:
    """Build transient PET requests using an independent PET preview position."""

    if room is None:
        raise PetContractError("Select a room before calculating the PET preview.")
    barriers = tuple(getattr(room, "barriers", ()) or ())
    if not barriers:
        raise PetContractError("The selected room has no barriers for PET preview.")
    geometry = getattr(room, "geometry", None)
    if geometry is None:
        raise PetContractError("The selected room has no geometry for PET preview.")
    pet_position = position or default_pet_preview_position(geometry)
    try:
        distances = pet_position.barrier_distances(geometry)
    except ValueError as exc:
        raise PetContractError(str(exc)) from exc

    values = []
    for barrier in barriers:
        distance_key = _pet_distance_key_for_barrier(barrier)
        distance_m = (
            distances[distance_key]
            if distance_key is not None
            else float(getattr(barrier, "distance_m", 0.0))
        )
        values.append({
            "source_name": str(getattr(barrier, "name", "") or "Barrier"),
            "material_key": pet_material_key_for_room_barrier(barrier),
            "distance_m": str(float(distance_m)),
            "occupancy_factor": str(float(getattr(barrier, "occupancy_factor", 0.0))),
            "design_goal_uSv_per_week": str(float(getattr(barrier, "design_goal_uSv_per_week", 0.0))),
            "provided_thickness_mm": str(float(getattr(barrier, "thickness_mm", 0.0))),
        })
    return tuple(values)


def _float_value(value: Any, label: str) -> float:
    text = str(value or "").strip()
    if not text:
        raise PetContractError(f"{label} is required.")
    try:
        return float(text)
    except ValueError as exc:
        raise PetContractError(f"{label} must be numeric.") from exc


def build_pet_preview_source_domain(values: dict[str, Any]) -> PetSourceDomain:
    """Build the validated PET domain object from preview-form values.

    The desktop preview exposes two explicit room modes:

    * Uptake Room: integrates physical decay from administration for the full
      uptake interval. No voiding or imaging-time factor is applied.
    * Imaging Room: starts the phase after the uptake delay, applies the
      phase-specific voiding/activity-retention factor, and integrates physical
      decay over the imaging interval.
    """

    room_mode = str(values.get("room_mode", "Imaging Room") or "").strip()
    if room_mode not in PET_ROOM_MODE_OPTIONS:
        raise PetContractError(
            f"PET room mode must be one of: {', '.join(PET_ROOM_MODE_OPTIONS)}."
        )

    uptake_time_h = _float_value(values.get("phase_1_start_h"), "Uptake time")
    if room_mode == "Uptake Room":
        phase = PetExposurePhase(
            name="Uptake",
            start_time_h=0.0,
            duration_h=uptake_time_h,
            activity_retention_factor=1.0,
        )
    else:
        phase = PetExposurePhase(
            name="Imaging",
            start_time_h=uptake_time_h,
            duration_h=_float_value(values.get("phase_1_duration_h"), "Imaging time"),
            activity_retention_factor=_float_value(
                values.get("phase_1_activity_retention_factor"), "Voiding factor"
            ),
        )

    return PetSourceDomain(
        radionuclide=str(values.get("radionuclide", "") or "").strip(),
        injected_activity_mbq=_float_value(
            values.get("injected_activity_mbq"), "Injected activity"
        ),
        patients_per_week=_float_value(
            values.get("patients_per_week"), "Patients per week"
        ),
        residual_activity_factor=1.0,
        exposure_phases=(phase,),
    )


def calculate_pet_preview(values: dict[str, Any]) -> dict[str, Any]:
    """Return a small UI-safe preview payload from raw form values."""

    source = build_pet_preview_source_domain(values)
    result = calculate_pet_weekly_dose_at_1m(source)
    return {
        "contract_version": PET_UI_PREVIEW_CONTRACT_VERSION,
        "baseline": PET_UI_PREVIEW_BASELINE,
        "ui_contract_version": PET_PREVIEW_UI_CONTRACT_VERSION,
        "ui_baseline": PET_PREVIEW_UI_BASELINE,
        "radionuclide": source.radionuclide_spec.display_name,
        "radiation_type": result.radiation_type,
        "tvl_key": result.tvl_key,
        "weekly_dose_uSv_at_1m": result.weekly_dose_uSv_at_1m,
        "phase_count": len(result.phase_results),
        "phase_results": result.phase_results,
        "calculation_basis": result.calculation_basis,
        "single_source_per_room": True,
        "production_eligible": False,
    }



def build_pet_preview_barrier_request(values: dict[str, Any]) -> PetBarrierCalculationRequest:
    """Build one validated non-production barrier request from preview values."""

    provided_text = str(values.get("provided_thickness_mm", "") or "").strip()
    provided_thickness = (
        None
        if not provided_text
        else _float_value(provided_text, "Provided thickness")
    )
    return PetBarrierCalculationRequest(
        material_key=str(values.get("material_key", "") or "").strip(),
        distance_m=_float_value(values.get("distance_m"), "Source-to-barrier distance"),
        occupancy_factor=_float_value(values.get("occupancy_factor"), "Occupancy factor"),
        design_goal_uSv_per_week=_float_value(
            values.get("design_goal_uSv_per_week"), "Design goal"
        ),
        provided_thickness_mm=provided_thickness,
        source_name="PET Patient Source Preview",
    )


def calculate_pet_barrier_preview(values: dict[str, Any]) -> dict[str, Any]:
    """Calculate one replay-verified PET barrier preview from UI-safe values."""

    source = build_pet_preview_source_domain(values)
    request = build_pet_preview_barrier_request(values)
    service_result = run_pet_calculation_service(source, (request,))
    barrier = service_result.snapshot.barrier_results[0]
    solver = barrier.solver_result
    return {
        "contract_version": PET_UI_PREVIEW_CONTRACT_VERSION,
        "baseline": PET_UI_PREVIEW_BASELINE,
        "ui_contract_version": PET_PREVIEW_UI_CONTRACT_VERSION,
        "ui_baseline": PET_PREVIEW_UI_BASELINE,
        "production_eligible": False,
        "replay_verified": service_result.replay_verified,
        "radionuclide": source.radionuclide_spec.display_name,
        "material_key": solver.material_key,
        "distance_m": solver.distance_m,
        "occupancy_factor": solver.occupancy_factor,
        "design_goal_uSv_per_week": solver.design_goal_uSv_per_week,
        "required_tvl_count": solver.required_tvl_count,
        "required_thickness_mm": solver.required_thickness_mm,
        "provided_thickness_mm": solver.provided_thickness_mm,
        "transmitted_weekly_dose_uSv": solver.transmitted_weekly_dose_uSv,
        "compliance_status": solver.compliance_status,
        "attenuation_record_id": solver.attenuation_record_id,
        "dataset_id": barrier.dataset_id,
        "dataset_revision": barrier.dataset_revision,
    }



def build_pet_preview_barrier_requests(
    barrier_values: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[PetBarrierCalculationRequest, ...]:
    """Build validated independent barrier requests for the preview schedule."""

    if not barrier_values:
        raise PetContractError("At least one PET barrier preview row is required.")
    requests: list[PetBarrierCalculationRequest] = []
    for index, values in enumerate(barrier_values, start=1):
        row = dict(values)
        row.setdefault("source_name", f"PET Patient Source Preview {index}")
        request = build_pet_preview_barrier_request(row)
        requests.append(
            PetBarrierCalculationRequest(
                material_key=request.material_key,
                distance_m=request.distance_m,
                occupancy_factor=request.occupancy_factor,
                design_goal_uSv_per_week=request.design_goal_uSv_per_week,
                provided_thickness_mm=request.provided_thickness_mm,
                source_name=str(row["source_name"]),
            )
        )
    return tuple(requests)


def calculate_pet_barrier_schedule_preview(
    source_values: dict[str, Any],
    barrier_values: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate a replay-verified read-only schedule for multiple barriers."""

    source = build_pet_preview_source_domain(source_values)
    requests = build_pet_preview_barrier_requests(barrier_values)
    service_result = run_pet_calculation_service(source, requests)
    rows = []
    for request, barrier in zip(requests, service_result.snapshot.barrier_results):
        solver = barrier.solver_result
        rows.append(
            {
                "source_name": request.source_name,
                "material_key": solver.material_key,
                "distance_m": solver.distance_m,
                "occupancy_factor": solver.occupancy_factor,
                "design_goal_uSv_per_week": solver.design_goal_uSv_per_week,
                "unshielded_weekly_dose_uSv_at_barrier": solver.unshielded_weekly_dose_uSv_at_barrier,
                "occupied_unshielded_weekly_dose_uSv": solver.occupied_unshielded_weekly_dose_uSv,
                "required_transmission": solver.required_transmission,
                "required_tvl_count": solver.required_tvl_count,
                "required_thickness_mm": solver.required_thickness_mm,
                "provided_thickness_mm": solver.provided_thickness_mm,
                "provided_transmission": solver.provided_transmission,
                "transmitted_weekly_dose_uSv": solver.transmitted_weekly_dose_uSv,
                "compliance_status": solver.compliance_status,
                "attenuation_record_id": solver.attenuation_record_id,
                "attenuation_provenance": solver.attenuation_provenance,
                "dataset_id": barrier.dataset_id,
                "dataset_revision": barrier.dataset_revision,
                "approved_by": barrier.approved_by,
                "approved_date": barrier.approved_date,
            }
        )
    output = build_pet_preview_output_contract(
        source=source,
        physics_result=service_result.snapshot.physics_result,
        barrier_rows=rows,
        replay_verified=service_result.replay_verified,
    )
    return {
        "contract_version": PET_UI_PREVIEW_CONTRACT_VERSION,
        "baseline": PET_UI_PREVIEW_BASELINE,
        "ui_contract_version": PET_PREVIEW_UI_CONTRACT_VERSION,
        "ui_baseline": PET_PREVIEW_UI_BASELINE,
        "production_eligible": False,
        "replay_verified": service_result.replay_verified,
        "radionuclide": source.radionuclide_spec.display_name,
        "weekly_dose_uSv_at_1m": service_result.snapshot.physics_result.weekly_dose_uSv_at_1m,
        "single_source_per_room": True,
        "output_contract_version": PET_PREVIEW_OUTPUT_CONTRACT_VERSION,
        "output_baseline": PET_PREVIEW_OUTPUT_BASELINE,
        "calculation_basis": output["calculation_basis"],
        "displayed_assumptions": output["displayed_assumptions"],
        "radionuclide_data": output["radionuclide_data"],
        "attenuation_datasets": output["attenuation_datasets"],
        "rows": output["rows"],
    }



def build_pet_preview_request_envelope(
    source_values: dict[str, Any],
    barrier_values: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> PetCalculationRequestEnvelope:
    """Build the validated request stored by the separate preview-state file."""
    return PetCalculationRequestEnvelope(
        source=build_pet_preview_source_domain(source_values),
        barrier_requests=build_pet_preview_barrier_requests(barrier_values),
    )


def pet_preview_request_to_form_values(
    request: PetCalculationRequestEnvelope,
) -> tuple[dict[str, str], tuple[dict[str, str], ...]]:
    """Convert a validated preview request back into Tk-friendly string values."""
    source = request.source
    phases = list(source.exposure_phases)
    imaging_phase = next(
        (phase for phase in phases if str(phase.name).strip().casefold() == "imaging"),
        None,
    )
    uptake_phase = next(
        (phase for phase in phases if str(phase.name).strip().casefold() == "uptake"),
        None,
    )
    if len(phases) == 1 and uptake_phase is not None:
        room_mode = "Uptake Room"
        selected_phase = uptake_phase
        uptake_time_h = selected_phase.duration_h
        imaging_time_h = ""
        retention_factor = ""
    else:
        room_mode = "Imaging Room"
        selected_phase = imaging_phase or phases[0]
        uptake_time_h = selected_phase.start_time_h
        imaging_time_h = str(selected_phase.duration_h)
        retention_factor = str(selected_phase.activity_retention_factor)

    source_values = {
        "room_mode": room_mode,
        "radionuclide": source.radionuclide_spec.code,
        "injected_activity_mbq": str(source.injected_activity_mbq),
        "patients_per_week": str(source.patients_per_week),
        "residual_activity_factor": str(source.residual_activity_factor),
        "phase_1_name": selected_phase.name,
        "phase_1_start_h": str(uptake_time_h),
        "phase_1_duration_h": imaging_time_h,
        "phase_1_activity_retention_factor": retention_factor,
        "phase_2_name": "",
        "phase_2_start_h": "",
        "phase_2_duration_h": "",
        "phase_2_activity_retention_factor": "",
    }
    barriers = tuple({
        "source_name": item.source_name,
        "material_key": item.material_key,
        "distance_m": str(item.distance_m),
        "occupancy_factor": str(item.occupancy_factor),
        "design_goal_uSv_per_week": str(item.design_goal_uSv_per_week),
        "provided_thickness_mm": "" if item.provided_thickness_mm is None else str(item.provided_thickness_mm),
    } for item in request.barrier_requests)
    return source_values, barriers


def pet_source_domain_to_form_values(source: PetSourceDomain) -> dict[str, str]:
    """Convert the persisted single PET source to frozen UI-form values."""
    request = PetCalculationRequestEnvelope(source=source, barrier_requests=())
    values, _barriers = pet_preview_request_to_form_values(request)
    return values


def persist_pet_preview_to_room(app, room: Any | None = None) -> bool:
    """Persist the current valid single-source PET inputs into normal room state.

    Invalid/incomplete edits are never written over the last valid persisted
    state. This function changes editable project state only; it does not add a
    production Source or calculation result.
    """
    if getattr(app, "_loading_pet_working_state", False):
        return False
    if room is None:
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    if room is None:
        return False
    try:
        state = PetWorkingProjectState(
            source=build_pet_preview_source_domain(_preview_values(app)),
            position=_preview_position(app, room),
        )
        set_room_pet_working_state(room, state)
    except Exception:
        return False
    return True


def load_pet_working_state_into_preview(app, room: Any | None) -> bool:
    """Restore one room's persisted PET source into the transient preview UI."""
    if room is None or not hasattr(app, "pet_preview_vars"):
        return False
    try:
        state = get_room_pet_working_state(room)
    except Exception:
        return False
    if state is None:
        geometry = getattr(room, "geometry", None)
        if geometry is None:
            return False
        position = default_pet_preview_position(geometry)
        source_values = dict(PET_SOURCE_UI_DEFAULTS)
    else:
        position = state.position
        source_values = pet_source_domain_to_form_values(state.source)

    app._loading_pet_working_state = True
    try:
        for key, value in source_values.items():
            if key in app.pet_preview_vars:
                app.pet_preview_vars[key].set(value)
        app.pet_preview_position_vars["x_from_west_m"].set(f"{position.x_from_west_m:g}")
        app.pet_preview_position_vars["y_from_south_m"].set(f"{position.y_from_south_m:g}")
        app.pet_preview_position_vars["height_above_ffl_m"].set(f"{position.height_above_ffl_m:g}")
    finally:
        app._loading_pet_working_state = False
    return state is not None


def save_pet_preview_from_app(app) -> None:
    """Save the current validated preview state outside the production project schema."""
    try:
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
        position = _preview_position(app, room)
        request = build_pet_preview_request_envelope(
            _preview_values(app), build_pet_preview_barrier_values_from_room(room, position)
        )
        state = PetPreviewStateSnapshot(request=request, position=position)
    except Exception as exc:
        messagebox.showerror("PET Preview", f"Cannot save invalid PET preview state:\n{exc}")
        return
    filename = filedialog.asksaveasfilename(
        title="Save PET development preview",
        defaultextension=PET_PREVIEW_FILE_EXTENSION,
        filetypes=(("PET preview files", f"*{PET_PREVIEW_FILE_EXTENSION}"), ("JSON files", "*.json")),
    )
    if not filename:
        return
    try:
        save_pet_preview_state(filename, state)
    except Exception as exc:
        messagebox.showerror("PET Preview", f"Unable to save PET preview state:\n{exc}")
        return
    app.pet_preview_file_var.set(str(filename))


def restore_pet_preview_barrier_snapshot_to_room(
    room: Any,
    barrier_values: tuple[dict[str, str], ...] | list[dict[str, str]],
) -> None:
    """Restore saved PET-preview barrier inputs into the selected live room.

    The preview snapshot already stores the room-derived barrier input rows used
    for deterministic replay. During interactive flight testing these values
    must round-trip with the preview file as well; otherwise provided shielding
    silently falls back to whatever the currently selected room happens to
    contain.

    Only editable barrier inputs are restored here. PET barrier distances are
    deliberately *not* restored from the snapshot because they are derived from
    the loaded PET position plus the current room geometry. The restore is
    fail-closed: saved and live barrier names must match exactly.
    """
    if room is None:
        raise PetContractError("Select a room before loading PET preview barrier inputs.")

    live_barriers = list(getattr(room, "barriers", ()) or ())
    if not live_barriers:
        raise PetContractError("The selected room has no barriers for PET preview restore.")

    saved_rows = [dict(row) for row in barrier_values]
    live_by_name = {str(getattr(b, "name", "") or "").strip(): b for b in live_barriers}
    saved_by_name = {str(row.get("source_name", "") or "").strip(): row for row in saved_rows}

    if "" in live_by_name or "" in saved_by_name:
        raise PetContractError("PET preview barrier names must not be blank.")
    if len(live_by_name) != len(live_barriers) or len(saved_by_name) != len(saved_rows):
        raise PetContractError("PET preview barrier names must be unique.")
    if set(saved_by_name) != set(live_by_name):
        raise PetContractError(
            "Saved PET preview barrier inventory does not match the selected room; "
            "barrier inputs were not restored."
        )

    material_labels = {
        "lead": "Pb",
        "concrete_2350kg_m3": "Concrete",
        "iron": "Iron",
    }

    for name, barrier in live_by_name.items():
        row = saved_by_name[name]
        material_key = str(row.get("material_key", "") or "").strip()
        if material_key not in material_labels:
            raise PetContractError(
                f"Saved PET preview barrier {name!r} uses unsupported material key {material_key!r}."
            )
        try:
            provided = float(row["provided_thickness_mm"])
            occupancy = float(row["occupancy_factor"])
            design_goal = float(row["design_goal_uSv_per_week"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PetContractError(
                f"Saved PET preview barrier {name!r} contains invalid barrier inputs."
            ) from exc

        if provided < 0 or occupancy < 0 or design_goal <= 0:
            raise PetContractError(
                f"Saved PET preview barrier {name!r} contains out-of-range barrier inputs."
            )

        barrier.material = material_labels[material_key]
        barrier.thickness_mm = provided
        barrier.occupancy_factor = occupancy
        barrier.design_goal_uSv_per_week = design_goal


def load_pet_preview_into_app(app) -> None:
    """Load a separate PET preview file and repopulate only preview controls."""
    filename = filedialog.askopenfilename(
        title="Open PET development preview",
        filetypes=(("PET preview files", f"*{PET_PREVIEW_FILE_EXTENSION}"), ("JSON files", "*.json")),
    )
    if not filename:
        return
    try:
        state = load_pet_preview_state(filename)
        source_values, barrier_values = pet_preview_request_to_form_values(state.request)
        for key, value in source_values.items():
            if key in app.pet_preview_vars:
                app.pet_preview_vars[key].set(value)
        app.pet_preview_position_vars["x_from_west_m"].set(str(state.position.x_from_west_m))
        app.pet_preview_position_vars["y_from_south_m"].set(str(state.position.y_from_south_m))
        app.pet_preview_position_vars["height_above_ffl_m"].set(str(state.position.height_above_ffl_m))
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
        restore_pet_preview_barrier_snapshot_to_room(room, barrier_values)

        # Keep the Geometry controls/canvas aligned with the restored barrier
        # inputs. This is UI synchronisation only; production Barriers/output
        # paths remain unchanged and PET distances are re-derived below.
        geometry_tab = getattr(app, "geometry_tab", None)
        if geometry_tab is not None:
            try:
                geometry_tab.load_selected_barrier_fields()
                geometry_tab.request_redraw()
            except Exception:
                pass
    except Exception as exc:
        messagebox.showerror("PET Preview", f"Unable to load PET preview state:\n{exc}")
        return
    app.pet_preview_file_var.set(str(filename))
    update_pet_preview(app)

def _preview_values(app) -> dict[str, str]:
    return {key: variable.get() for key, variable in app.pet_preview_vars.items()}


def _preview_position(app, room: Any) -> PetPreviewPosition:
    geometry = getattr(room, "geometry", None)
    if geometry is None:
        raise PetContractError("The selected room has no geometry for PET preview.")
    return PetPreviewPosition(
        x_from_west_m=_float_value(app.pet_preview_position_vars["x_from_west_m"].get(), "PET position from West"),
        y_from_south_m=_float_value(app.pet_preview_position_vars["y_from_south_m"].get(), "PET position from South"),
        height_above_ffl_m=_float_value(app.pet_preview_position_vars["height_above_ffl_m"].get(), "PET position height"),
    ).validate_for_room(geometry)


def _preview_barrier_values(app) -> tuple[dict[str, str], ...]:
    room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
    room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    return build_pet_preview_barrier_values_from_room(room, _preview_position(app, room))


def build_pet_report_preview_lines_for_app(app, room: Any | None = None) -> list[str]:
    """Build the frozen Step 27 PET report preview entirely in memory.

    This UI adapter is deliberately one-way and non-issueable. It consumes the
    persisted PET working state plus the canonical in-app Results model, then
    passes those values through the frozen Step 23-27 harness chain. No report,
    export, certification, print, or file-writing service is called here.
    """
    selected_room = room
    if selected_room is None:
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        selected_room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    if selected_room is None:
        raise PetContractError("Select a room before opening the PET report preview.")
    if not hasattr(app, "get_room_results_model"):
        raise PetContractError("Canonical PET Results are unavailable for preview.")

    rows = app.get_room_results_model(selected_room)
    source_payload = build_non_issueable_pet_source_summary(selected_room)
    barrier_payload = build_non_issueable_pet_report_payload(rows)
    envelope = build_non_issueable_pet_combined_report_payload_envelope(
        source_payload=source_payload,
        barrier_payload=barrier_payload,
    )
    view_model = build_non_issueable_pet_report_section_view_model(envelope)
    return render_non_issueable_pet_plain_text_preview(view_model)


def show_pet_report_preview(app) -> None:
    """Open a read-only, non-production PET report preview window."""
    try:
        lines = build_pet_report_preview_lines_for_app(app)
    except Exception as exc:
        messagebox.showerror("PET Report Preview", f"Unable to build PET report preview:\n{exc}")
        return

    window = tk.Toplevel(app)
    window.title("PET Report Preview — non-production, read-only")
    window.geometry("1100x720")
    try:
        window.transient(app)
    except Exception:
        pass

    container = ttk.Frame(window, padding=10)
    container.pack(fill="both", expand=True)
    container.rowconfigure(1, weight=1)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text=(
            "NON-ISSUEABLE PET REPORT PREVIEW — read-only, in-memory display only. "
            "Save, print, PDF, CSV/JSON, certification and normal report output remain disabled."
        ),
        wraplength=1040,
        justify="left",
    ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=0, sticky="nsew")
    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)
    preview_text = tk.Text(text_frame, wrap="none", undo=False)
    y_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=preview_text.yview)
    x_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=preview_text.xview)
    preview_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
    preview_text.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    x_scroll.grid(row=1, column=0, sticky="ew")
    preview_text.insert("1.0", "\n".join(lines))
    preview_text.configure(state="disabled")

    controls = ttk.Frame(container)
    controls.grid(row=2, column=0, sticky="e", pady=(8, 0))
    ttk.Button(controls, text="Close", command=window.destroy).pack(side="right")


def build_pet_input_provenance_summary(source: PetSourceDomain) -> str:
    """Return the frozen input/provenance summary shown on the Sources tab."""
    manifest = PET_CALCULATION_INPUT_PROVENANCE_MANIFEST
    rad_meta = PET_RADIONUCLIDE_DATASET_METADATA
    spec = source.radionuclide_spec
    return "\n".join((
        f"Input validation: PASS — one persisted PET source for this room",
        f"Selected radionuclide: {spec.display_name} | half-life {spec.half_life_h:g} h | "
        f"patient dose-rate constant {spec.dose_rate_constant_uSv_h_per_MBq_at_1m:g} "
        "µSv·h⁻¹·MBq⁻¹ at 1 m",
        f"Half-life source: {spec.half_life_provenance.source_title} "
        f"({spec.half_life_provenance.reference_id})",
        f"Dose-rate source: {spec.dose_rate_provenance.source_title} "
        f"({spec.dose_rate_provenance.reference_id})",
        f"Provenance manifest: {manifest.manifest_id} | revision {manifest.revision}",
        f"Radionuclide dataset: {rad_meta.dataset_id} | revision {rad_meta.revision} | "
        f"SHA-256 {rad_meta.records_sha256}",
        f"Attenuation dataset: {manifest.attenuation_dataset.dataset_id} | "
        f"revision {manifest.attenuation_dataset.revision} | "
        f"SHA-256 {manifest.attenuation_dataset.records_sha256}",
        f"Physics contract v{manifest.physics_contract_version} | "
        f"solver contract v{manifest.solver_contract_version}",
        "Canonical barrier calculations are displayed only through the normal Results model. "
        "Normal export, certification and report generation remain blocked.",
    ))


def _update_pet_calculated_decay_factor(app, source: PetSourceDomain | None = None) -> None:
    """Refresh the read-only physical-decay factor shown for imaging start."""
    variable = getattr(app, "pet_calculated_decay_factor_var", None)
    if variable is None:
        return
    if source is None:
        try:
            source = build_pet_preview_source_domain(_preview_values(app))
        except Exception:
            variable.set("—")
            return
    if not source.exposure_phases:
        variable.set("—")
        return
    factor = calculate_pet_decay_factor_at_time(
        source.radionuclide_spec.half_life_h,
        source.exposure_phases[0].start_time_h,
    )
    variable.set(f"{factor:.4f}")


def update_pet_preview(app, *_args) -> None:
    """Validate and persist PET inputs; show provenance, not duplicate results."""
    if not hasattr(app, "pet_preview_provenance_var"):
        return
    room = None
    try:
        values = _preview_values(app)
        source = build_pet_preview_source_domain(values)
        room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
        room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
        position = _preview_position(app, room)
        barriers = build_pet_preview_barrier_values_from_room(room, position)
    except Exception as exc:
        _update_pet_calculated_decay_factor(app, None)
        app.pet_preview_validation_var.set("Input validation: INPUT REQUIRED / INVALID")
        app.pet_preview_provenance_var.set(str(exc))
        app.pet_preview_geometry_overlay = None
        if hasattr(app, "pet_preview_room_barriers_var"):
            app.pet_preview_room_barriers_var.set(str(exc))
        refresh_pet_barrier_results_preview(app, room=room)
        sync_unified_modality_outputs(app)
        return

    _update_pet_calculated_decay_factor(app, source)
    app.pet_preview_validation_var.set("Input validation: PASS — persisted non-production working state")
    app.pet_preview_provenance_var.set(build_pet_input_provenance_summary(source))
    if hasattr(app, "pet_preview_room_barriers_var"):
        app.pet_preview_room_barriers_var.set(
            f"Live room: {room_name or 'none'} | PET position: "
            f"W {position.x_from_west_m:g} m, S {position.y_from_south_m:g} m, "
            f"H {position.height_above_ffl_m:g} m | "
            f"{len(barriers)} geometry-synchronised barriers | canonical results in Results model"
        )
    pet_physics = calculate_pet_weekly_dose_at_1m(source)
    app.pet_preview_geometry_overlay = build_pet_input_geometry_overlay(
        source.radionuclide_spec.display_name,
        position,
        weekly_dose_uSv_at_1m=pet_physics.weekly_dose_uSv_at_1m,
    )
    persist_pet_preview_to_room(app, room)
    refresh_pet_barrier_results_preview(app, room=room)

    sync_unified_modality_outputs(app)



def _update_pet_room_mode_fields(app) -> None:
    """Show only the fields physically applicable to the selected PET room mode."""
    if not hasattr(app, "pet_preview_vars"):
        return
    mode = str(app.pet_preview_vars["room_mode"].get() or "Imaging Room").strip()
    imaging_only = ("phase_1_duration_h", "phase_1_activity_retention_factor")
    for key in imaging_only:
        label = getattr(app, "pet_preview_field_labels", {}).get(key)
        widget = getattr(app, "pet_preview_field_widgets", {}).get(key)
        if label is None or widget is None:
            continue
        if mode == "Imaging Room":
            label.grid()
            widget.grid()
        else:
            label.grid_remove()
            widget.grid_remove()
    decay_label = getattr(app, "pet_decay_factor_label", None)
    decay_entry = getattr(app, "pet_decay_factor_entry", None)
    if decay_label is not None and decay_entry is not None:
        if mode == "Imaging Room":
            decay_label.grid()
            decay_entry.grid()
        else:
            decay_label.grid_remove()
            decay_entry.grid_remove()


def build_pet_preview_panel(app, parent) -> None:
    """Build isolated PET preview inputs below the normal source UI."""

    frame = ttk.LabelFrame(parent, text="PET Development Preview — non-production")
    frame.grid(row=3, column=0, sticky="nsew", padx=4, pady=8)
    frame.columnconfigure(1, weight=1)

    app.pet_preview_vars = {
        key: tk.StringVar(value=value)
        for key, value in PET_SOURCE_UI_DEFAULTS.items()
    }
    room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
    selected_room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    selected_geometry = getattr(selected_room, "geometry", None)
    if selected_geometry is not None:
        position_default = default_pet_preview_position(selected_geometry)
    else:
        position_default = PetPreviewPosition(0.0, 0.0, 0.0)
    app.pet_preview_position_vars = {
        "x_from_west_m": tk.StringVar(value=f"{position_default.x_from_west_m:g}"),
        "y_from_south_m": tk.StringVar(value=f"{position_default.y_from_south_m:g}"),
        "height_above_ffl_m": tk.StringVar(value=f"{position_default.height_above_ffl_m:g}"),
    }

    source_rows = PET_SOURCE_UI_FIELDS
    source_row_count = len(source_rows) + 1
    app.pet_calculated_decay_factor_var = tk.StringVar(value="1.0000")
    app.pet_preview_field_widgets = {}
    app.pet_preview_field_labels = {}

    # Rows are explicit so the derived decay factor can sit directly below
    # Uptake time while Imaging-only fields can be hidden in Uptake Room mode.
    row_map = {
        "room_mode": 0,
        "radionuclide": 1,
        "injected_activity_mbq": 2,
        "patients_per_week": 3,
        "phase_1_start_h": 4,
        "phase_1_duration_h": 6,
        "phase_1_activity_retention_factor": 7,
    }
    for field in source_rows:
        display_row = row_map[field.key]
        key = field.key
        label = ttk.Label(frame, text=display_label(field))
        label.grid(row=display_row, column=0, sticky="w", padx=4, pady=2)
        app.pet_preview_field_labels[key] = label
        if field.widget_kind == "combobox":
            values = PET_ROOM_MODE_OPTIONS if key == "room_mode" else tuple(PET_RADIONUCLIDES)
            widget = ttk.Combobox(
                frame, textvariable=app.pet_preview_vars[key],
                values=values, state="readonly"
            )
        else:
            widget = ttk.Entry(frame, textvariable=app.pet_preview_vars[key])
        widget.grid(row=display_row, column=1, sticky="ew", padx=4, pady=2)
        app.pet_preview_field_widgets[key] = widget

    app.pet_decay_factor_label = ttk.Label(frame, text="Calculated decay factor")
    app.pet_decay_factor_label.grid(row=5, column=0, sticky="w", padx=4, pady=2)
    app.pet_decay_factor_entry = ttk.Entry(
        frame,
        textvariable=app.pet_calculated_decay_factor_var,
        state="readonly",
    )
    app.pet_decay_factor_entry.grid(row=5, column=1, sticky="ew", padx=4, pady=2)

    position_frame = ttk.LabelFrame(frame, text="Single PET patient/source position — persisted working state")
    position_frame.grid(
        row=source_row_count, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4)
    )
    position_frame.columnconfigure(1, weight=1)
    position_rows = PET_POSITION_UI_FIELDS
    for row, field in enumerate(position_rows):
        key = field.key
        ttk.Label(position_frame, text=display_label(field)).grid(
            row=row, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(position_frame, textvariable=app.pet_preview_position_vars[key]).grid(
            row=row, column=1, sticky="ew", padx=4, pady=2
        )

    barrier_frame = ttk.LabelFrame(frame, text="Room-derived barrier inventory")
    barrier_frame.grid(
        row=source_row_count+1, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4)
    )
    app.pet_preview_room_barriers_var = tk.StringVar(
        value="Uses the currently selected room barriers (N/E/S/W/Floor/Ceiling)."
    )
    ttk.Label(
        barrier_frame,
        textvariable=app.pet_preview_room_barriers_var,
        style="Muted.TLabel",
        wraplength=720,
        justify="left",
    ).grid(row=0, column=0, sticky="w", padx=6, pady=6)

    provenance_frame = ttk.LabelFrame(frame, text="PET input and provenance preview")
    provenance_frame.grid(
        row=source_row_count+2, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4)
    )
    provenance_frame.columnconfigure(0, weight=1)
    app.pet_preview_validation_var = tk.StringVar(value="Input validation: waiting for PET inputs")
    app.pet_preview_provenance_var = tk.StringVar(value="")
    ttk.Label(
        provenance_frame,
        textvariable=app.pet_preview_validation_var,
        justify="left",
    ).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
    ttk.Label(
        provenance_frame,
        textvariable=app.pet_preview_provenance_var,
        style="Muted.TLabel",
        wraplength=760,
        justify="left",
    ).grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 6))

    results_preview_frame = ttk.LabelFrame(
        frame, text="PET Barrier Results Preview — non-production"
    )
    results_preview_frame.grid(
        row=source_row_count+3, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4)
    )
    results_preview_frame.columnconfigure(0, weight=1)
    app.pet_barrier_results_preview_status_var = tk.StringVar(
        value="Canonical PET barrier results will appear here when inputs are valid."
    )
    ttk.Label(
        results_preview_frame,
        textvariable=app.pet_barrier_results_preview_status_var,
        style="Muted.TLabel",
        justify="left",
    ).grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

    table_frame = ttk.Frame(results_preview_frame)
    table_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
    table_frame.columnconfigure(0, weight=1)
    columns = tuple(key for key, _heading, _width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS)
    app.pet_barrier_results_preview_tree = ttk.Treeview(
        table_frame, columns=columns, show="headings", height=8, selectmode="browse"
    )
    for key, heading, width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS:
        app.pet_barrier_results_preview_tree.heading(key, text=heading)
        app.pet_barrier_results_preview_tree.column(
            key, width=width, minwidth=70, stretch=False, anchor="center"
        )
    results_x_scroll = ttk.Scrollbar(
        table_frame, orient="horizontal", command=app.pet_barrier_results_preview_tree.xview
    )
    results_y_scroll = ttk.Scrollbar(
        table_frame, orient="vertical", command=app.pet_barrier_results_preview_tree.yview
    )
    app.pet_barrier_results_preview_tree.configure(
        xscrollcommand=results_x_scroll.set, yscrollcommand=results_y_scroll.set
    )
    app.pet_barrier_results_preview_tree.grid(row=0, column=0, sticky="ew")
    results_y_scroll.grid(row=0, column=1, sticky="ns")
    results_x_scroll.grid(row=1, column=0, sticky="ew")

    file_frame = ttk.Frame(frame)
    file_frame.grid(row=source_row_count+4, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 2))
    ttk.Button(file_frame, text="Save PET Preview...", command=lambda: save_pet_preview_from_app(app)).pack(side="left", padx=(0, 6))
    ttk.Button(file_frame, text="Load PET Preview...", command=lambda: load_pet_preview_into_app(app)).pack(side="left")
    app.pet_preview_file_var = tk.StringVar(value="Not saved")
    ttk.Label(file_frame, textvariable=app.pet_preview_file_var, style="Muted.TLabel", wraplength=500).pack(side="left", padx=10)

    report_preview_frame = ttk.LabelFrame(frame, text="PET report preview — non-production")
    report_preview_frame.grid(
        row=source_row_count+5, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 2)
    )
    ttk.Button(
        report_preview_frame,
        text="Open Read-only PET Report Preview...",
        command=lambda: show_pet_report_preview(app),
    ).pack(side="left", padx=6, pady=6)
    ttk.Label(
        report_preview_frame,
        text="In-memory display only — no save, print, PDF, CSV/JSON, certification or report output.",
        style="Muted.TLabel",
        wraplength=540,
        justify="left",
    ).pack(side="left", padx=(4, 6), pady=6)

    ttk.Label(
        frame,
        text=(
            "Exactly one PET patient/source position is modelled per selected room. PET room mode explicitly selects either an uptake-room exposure from administration through uptake, or a post-uptake imaging-room exposure with decay-to-start and voiding applied. "
            "Validated PET source inputs and position are persisted with the selected room in the normal working-project file, but remain explicitly non-production. "
            "This Sources panel shows inputs, frozen provenance and a read-only non-production PET barrier Results preview sourced from the canonical Results model. "
            "The existing PET readiness/export blocker remains active, and PET report generation remains closed."
        ),
        style="Muted.TLabel",
        wraplength=760,
        justify="left",
    ).grid(row=source_row_count+6, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 6))

    # Restore ordinary working-project PET state before trace callbacks are attached.
    load_pet_working_state_into_preview(app, selected_room)
    _update_pet_room_mode_fields(app)

    for key, variable in app.pet_preview_vars.items():
        if key == "room_mode":
            variable.trace_add(
                "write",
                lambda *_args: (_update_pet_room_mode_fields(app), update_pet_preview(app)),
            )
        else:
            variable.trace_add("write", lambda *_args: update_pet_preview(app))
    for variable in app.pet_preview_position_vars.values():
        variable.trace_add("write", lambda *_args: update_pet_preview(app))
    update_pet_preview(app)


def build_pet_source_controls(app, parent) -> None:
    """Build the production-facing PET source editor inside the unified Sources tab.

    The legacy PET preview module remains the calculation/persistence adapter for
    compatibility, but no separate preview/test panel is rendered. Barrier results
    are shown only in the shared Results tab.
    """
    if not hasattr(app, "pet_preview_vars"):
        app.pet_preview_vars = {
            key: tk.StringVar(value=value)
            for key, value in PET_SOURCE_UI_DEFAULTS.items()
        }
    if not hasattr(app, "pet_preview_position_vars"):
        app.pet_preview_position_vars = {
            "x_from_west_m": tk.StringVar(value="0"),
            "y_from_south_m": tk.StringVar(value="0"),
            "height_above_ffl_m": tk.StringVar(value="1"),
        }
    if not hasattr(app, "pet_calculated_decay_factor_var"):
        app.pet_calculated_decay_factor_var = tk.StringVar(value="1.0000")
    if not hasattr(app, "pet_preview_validation_var"):
        app.pet_preview_validation_var = tk.StringVar(value="Input validation: waiting for PET inputs")
    if not hasattr(app, "pet_preview_provenance_var"):
        app.pet_preview_provenance_var = tk.StringVar(value="")
    if not hasattr(app, "pet_preview_room_barriers_var"):
        app.pet_preview_room_barriers_var = tk.StringVar(value="")

    room_name = app.sources_room_var.get() if hasattr(app, "sources_room_var") else ""
    room = app.get_room_by_name(room_name) if hasattr(app, "get_room_by_name") else None
    if room is not None:
        load_pet_working_state_into_preview(app, room)
        # Geometry owns the patient/source X/Y position in the unified workflow.
        geometry = getattr(room, "geometry", None)
        source = getattr(geometry, "source", None)
        if source is not None:
            app.pet_preview_position_vars["x_from_west_m"].set(f"{float(source.x_m):g}")
            app.pet_preview_position_vars["y_from_south_m"].set(f"{float(source.y_m):g}")

    parent.columnconfigure(1, weight=1)
    app.pet_preview_field_widgets = {}
    app.pet_preview_field_labels = {}
    row_map = {
        "room_mode": 0,
        "radionuclide": 1,
        "injected_activity_mbq": 2,
        "patients_per_week": 3,
        "phase_1_start_h": 4,
        "phase_1_duration_h": 6,
        "phase_1_activity_retention_factor": 7,
    }
    for field in PET_SOURCE_UI_FIELDS:
        row = row_map[field.key]
        label = ttk.Label(parent, text=display_label(field))
        label.grid(row=row, column=0, sticky="w", padx=4, pady=4)
        app.pet_preview_field_labels[field.key] = label
        if field.widget_kind == "combobox":
            values = PET_ROOM_MODE_OPTIONS if field.key == "room_mode" else tuple(PET_RADIONUCLIDES)
            widget = ttk.Combobox(
                parent,
                textvariable=app.pet_preview_vars[field.key],
                values=values,
                state="readonly",
            )
        else:
            widget = ttk.Entry(parent, textvariable=app.pet_preview_vars[field.key])
        widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        app.pet_preview_field_widgets[field.key] = widget

    app.pet_decay_factor_label = ttk.Label(parent, text="Calculated decay factor")
    app.pet_decay_factor_label.grid(row=5, column=0, sticky="w", padx=4, pady=4)
    app.pet_decay_factor_entry = ttk.Entry(
        parent, textvariable=app.pet_calculated_decay_factor_var, state="readonly"
    )
    app.pet_decay_factor_entry.grid(row=5, column=1, sticky="ew", padx=4, pady=4)

    ttk.Separator(parent, orient="horizontal").grid(
        row=8, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 6)
    )
    ttk.Label(parent, textvariable=app.pet_preview_validation_var).grid(
        row=9, column=0, columnspan=2, sticky="w", padx=4, pady=2
    )
    ttk.Label(
        parent,
        textvariable=app.pet_preview_provenance_var,
        wraplength=760,
        justify="left",
        foreground="#555555",
    ).grid(row=10, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 6))

    if not getattr(app, "_pet_unified_source_traces_bound", False):
        def _changed(*_args):
            if getattr(app, "_loading_pet_working_state", False):
                return
            _update_pet_room_mode_fields(app)
            update_pet_preview(app)

        for variable in app.pet_preview_vars.values():
            variable.trace_add("write", _changed)
        app._pet_unified_source_traces_bound = True

    _update_pet_room_mode_fields(app)
    update_pet_preview(app)
