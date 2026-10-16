"""Production calculation dispatch for persisted PET working state.

This boundary deliberately opens PET calculation execution for the ordinary
working-project model without opening normal Results, export, certification or
report generation.  PET remains stored as room-owned ``modality_state`` rather
than as a production ``Source`` object.

Callers must opt into this dispatcher explicitly.  Existing CT/X-ray
``calc_barrier_result`` and report/result pipelines do not call this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.shielding_models import Project, Room
from modalities.pet import PetContractError
from serialization.pet_working_project_state import get_room_pet_working_state
from services.pet_calculation_service import (
    PetBarrierCalculationRequest,
    PetCalculationServiceError,
    run_pet_calculation_service,
)


PET_PROJECT_DISPATCH_CONTRACT_VERSION = 1


class PetProjectDispatchError(ValueError):
    """Raised when persisted PET state cannot be dispatched safely."""


@dataclass(frozen=True)
class PetDispatchedBarrierResult:
    room_name: str
    barrier_name: str
    material_key: str
    distance_m: float
    occupancy_factor: float
    design_goal_uSv_per_week: float
    provided_thickness_mm: float
    solver_result: Any
    attenuation_dataset_id: str
    attenuation_dataset_revision: str
    attenuation_approved_by: str
    attenuation_approved_date: str


@dataclass(frozen=True)
class PetRoomDispatchResult:
    contract_version: int
    room_name: str
    source_type: str
    replay_verified: bool
    physics_result: Any
    barrier_results: tuple[PetDispatchedBarrierResult, ...]


def _material_key_for_barrier(barrier: Any) -> str:
    material = str(getattr(barrier, "material", "") or "").strip().lower()
    legacy = str(getattr(barrier, "material_legacy", "") or "").strip().lower()
    text = material or legacy
    if "concrete" in text:
        return "concrete_2350kg_m3"
    if any(token in text for token in ("iron", "steel")):
        return "iron"
    if any(token in text for token in ("pb", "lead")):
        return "lead"
    raise PetProjectDispatchError(
        f"Barrier {getattr(barrier, 'name', '')!r} uses unsupported PET material "
        f"{getattr(barrier, 'material', '')!r}."
    )


def _distance_key_for_barrier(barrier: Any) -> str | None:
    name = str(getattr(barrier, "name", "") or "").strip().lower()
    role = str(getattr(barrier, "barrier_role", "") or "").strip().lower()
    aliases = {
        "n": "N",
        "north": "N",
        "n wall": "N",
        "north wall": "N",
        "e": "E",
        "east": "E",
        "e wall": "E",
        "east wall": "E",
        "s": "S",
        "south": "S",
        "s wall": "S",
        "south wall": "S",
        "w": "W",
        "west": "W",
        "w wall": "W",
        "west wall": "W",
        "floor": "Floor",
        "ceiling": "Ceiling",
    }
    if name in aliases:
        return aliases[name]
    if role in {"floor", "ceiling"}:
        return role.title()
    return None


def _room_by_name(project: Project, room_name: str) -> Room:
    room = next((room for room in project.rooms if room.name == room_name), None)
    if room is None:
        raise PetProjectDispatchError(f"Room {room_name!r} was not found in the project.")
    return room


def dispatch_persisted_pet_working_state(
    project: Project,
    room_name: str,
) -> PetRoomDispatchResult | None:
    """Calculate persisted PET working state for one room.

    ``None`` means that the room has no persisted PET working state.  If PET
    state is present, every input is revalidated from the persisted canonical
    envelope and the frozen PET provenance/dataset boundaries are exercised by
    the existing PET calculation service.  Invalid state fails closed.
    """

    if not isinstance(project, Project):
        raise PetProjectDispatchError("project must be a Project instance.")
    room = _room_by_name(project, str(room_name or ""))

    try:
        state = get_room_pet_working_state(room)
    except Exception as exc:
        raise PetProjectDispatchError(f"Persisted PET working state is invalid: {exc}") from exc
    if state is None:
        return None

    geometry = getattr(room, "geometry", None)
    if geometry is None:
        raise PetProjectDispatchError("PET dispatch requires room geometry.")
    try:
        distances = state.position.barrier_distances(geometry)
    except ValueError as exc:
        raise PetProjectDispatchError(str(exc)) from exc

    barriers = tuple(getattr(room, "barriers", ()) or ())
    if not barriers:
        raise PetProjectDispatchError("PET dispatch requires at least one room barrier.")

    requests: list[PetBarrierCalculationRequest] = []
    request_meta: list[tuple[str, str, float, float, float, float]] = []
    for barrier in barriers:
        key = _distance_key_for_barrier(barrier)
        try:
            distance_m = (
                float(distances[key])
                if key is not None
                else float(getattr(barrier, "distance_m", 0.0))
            )
            occupancy = float(getattr(barrier, "occupancy_factor", 0.0))
            design_goal = float(getattr(barrier, "design_goal_uSv_per_week", 0.0))
            provided = float(getattr(barrier, "thickness_mm", 0.0))
            material_key = _material_key_for_barrier(barrier)
            barrier_name = str(getattr(barrier, "name", "") or "Barrier")
            requests.append(
                PetBarrierCalculationRequest(
                    material_key=material_key,
                    distance_m=distance_m,
                    occupancy_factor=occupancy,
                    design_goal_uSv_per_week=design_goal,
                    provided_thickness_mm=provided,
                    source_name=f"PET Patient Source — {barrier_name}",
                )
            )
            request_meta.append(
                (barrier_name, material_key, distance_m, occupancy, design_goal, provided)
            )
        except (TypeError, ValueError, PetCalculationServiceError, PetContractError) as exc:
            raise PetProjectDispatchError(
                f"PET dispatch input is invalid for barrier {getattr(barrier, 'name', '')!r}: {exc}"
            ) from exc

    try:
        service_result = run_pet_calculation_service(state.source, tuple(requests))
    except (PetCalculationServiceError, PetContractError) as exc:
        raise PetProjectDispatchError(str(exc)) from exc

    barrier_results: list[PetDispatchedBarrierResult] = []
    for meta, calculated in zip(request_meta, service_result.snapshot.barrier_results):
        barrier_name, material_key, distance_m, occupancy, design_goal, provided = meta
        barrier_results.append(
            PetDispatchedBarrierResult(
                room_name=room.name,
                barrier_name=barrier_name,
                material_key=material_key,
                distance_m=distance_m,
                occupancy_factor=occupancy,
                design_goal_uSv_per_week=design_goal,
                provided_thickness_mm=provided,
                solver_result=calculated.solver_result,
                attenuation_dataset_id=calculated.dataset_id,
                attenuation_dataset_revision=calculated.dataset_revision,
                attenuation_approved_by=calculated.approved_by,
                attenuation_approved_date=calculated.approved_date,
            )
        )

    return PetRoomDispatchResult(
        contract_version=PET_PROJECT_DISPATCH_CONTRACT_VERSION,
        room_name=room.name,
        source_type=service_result.source_type,
        replay_verified=service_result.replay_verified,
        physics_result=service_result.snapshot.physics_result,
        barrier_results=tuple(barrier_results),
    )
