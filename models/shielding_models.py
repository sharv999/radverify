from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List

from geometry.geometry_model import RoomGeometry


DEFAULT_TVL_LIBRARY_MM_PB = {
    "xray_80kvp": 0.25,
    "xray_100kvp": 0.27,
    "xray_120kvp": 0.30,
    "xray_140kvp": 0.33,
    "ct_120kvp": 0.30,
    "ct_140kvp": 0.33,
    "tc99m": 0.30,
    "i131": 3.0,
}

@dataclass
class Source:
    name: str = "Source"
    source_type: str = "ct_scatter"
    radiation_type: str = "xray_140kvp"
    params: Dict[str, Any] = field(default_factory=dict)
    room_name: str = ""


@dataclass
class Barrier:
    name: str = "N wall"
    material: str = "Pb"
    thickness_mm: float = 0.88
    adjacent_area: str = "Corridor"
    barrier_role: str = "secondary_wall"
    distance_m: float = 2.0
    occupancy_factor: float = 0.2
    design_goal_uSv_per_week: float = 10.0
    material_legacy: str = "Pb 0.88 mm (10 kg/m2)"
    notes: str = ""
    # Floor/Ceiling distances are initially derived from room geometry, but may
    # be explicitly overridden in Geometry. Persist the override so later
    # Results/Barriers refreshes do not silently replace a user-entered value.
    distance_is_manual: bool = False


@dataclass
class Room:
    name: str = "CT Room 1"
    modality: str = "CT"
    sources: List[Source] = field(default_factory=list)  # legacy only
    barriers: List[Barrier] = field(default_factory=list)
    geometry: RoomGeometry = field(default_factory=RoomGeometry)
    # Modality-owned editable working state. This is persisted with the normal
    # project file but is intentionally ignored by production calculation/report
    # paths unless a modality boundary explicitly opts in.
    modality_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    project_name: str = ""
    project_type: str = "new_build"
    client: str = ""
    site: str = ""
    assessor: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    modality: str = ""
    notes: str = ""
    tvl_library_mm_pb: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TVL_LIBRARY_MM_PB))
    patient_dose_constants: Dict[str, Any] = field(default_factory=dict)
    rooms: List[Room] = field(default_factory=list)

    # New source-of-truth source inventory.
    # Sources are project-level and assigned to rooms by Source.room_name.
    sources: List[Source] = field(default_factory=list)


def _parse_legacy_material(material_text: str) -> tuple[str, float]:
    text = str(material_text or "").strip()

    if "Concrete" in text:
        for token in text.replace("(", " ").replace(")", " ").split():
            try:
                value = float(token)
                if value > 10:
                    return "Concrete", value
            except Exception:
                pass
        return "Concrete", 150.0

    if "glass" in text.lower():
        for token in text.replace("(", " ").replace(")", " ").split():
            try:
                value = float(token)
                return "Pb glass", value
            except Exception:
                pass
        return "Pb glass", 2.20

    for token in text.replace("(", " ").replace(")", " ").split():
        try:
            value = float(token)
            return "Pb", value
        except Exception:
            pass

    return "Pb", 0.88


def _barrier_from_dict(data: Dict[str, Any]) -> Barrier:
    bd = dict(data or {})

    # Drop legacy/result-only fields that should not be passed to Barrier().
    for key in [
        "barrier_type",
        "existing_lead_mm",
        "existing_lead_kg_m2",
        "material_thickness_mm",
        "energy_label",
        "unshielded_weekly_dose_uSv",
        "barrier_transmission_factor_B",
        "linear_attenuation_coefficient_cm_inv",
        "required_lead_mm",
        "required_concrete_mm",
        "recommended_commercial_lead_mm",
        "ct_required_mm",
        "dominant_component",
        "solver_used",
        "ct_solver_used",
        "compliance_status",
        "required_thickness_mm",
        "confidence",
        "mm_shortfall",
        "margin_mm",
        "notes",
    ]:
        bd.pop(key, None)

    legacy_material = str(
        bd.get("material_legacy")
        or bd.get("material")
        or "Pb 0.88 mm (10 kg/m2)"
    )

    family, inferred_thickness = _parse_legacy_material(legacy_material)

    raw_material = str(bd.get("material") or "").strip()
    if raw_material in {"Pb", "Concrete", "Pb glass"}:
        material_family = raw_material
    else:
        material_family = family

    try:
        thickness_mm = float(bd.get("thickness_mm", inferred_thickness))
    except Exception:
        thickness_mm = float(inferred_thickness)

    bd["material"] = material_family
    bd["thickness_mm"] = thickness_mm
    bd["material_legacy"] = legacy_material
    bd["barrier_role"] = bd.get("barrier_role", "secondary_wall")

    allowed = {f.name for f in Barrier.__dataclass_fields__.values()}
    clean = {k: v for k, v in bd.items() if k in allowed}

    return Barrier(**clean)


def _source_from_dict(data: Dict[str, Any], fallback_room_name: str = "") -> Source:
    sd = dict(data or {})

    allowed = {f.name for f in Source.__dataclass_fields__.values()}
    clean = {k: v for k, v in sd.items() if k in allowed}

    src = Source(**clean)

    if not isinstance(src.params, dict):
        src.params = {}

    if not str(src.room_name or "").strip():
        src.room_name = fallback_room_name

    return src


def project_from_dict(data: Dict[str, Any]) -> Project:
    data = dict(data or {})

    rooms: List[Room] = []
    project_sources: List[Source] = []

    # New format: project-level sources.
    for s in data.get("sources", []) or []:
        if isinstance(s, dict):
            project_sources.append(_source_from_dict(s))

    # Rooms, with legacy nested-source migration.
    for r in data.get("rooms", []) or []:
        if not isinstance(r, dict):
            continue

        room_name = r.get("name", "Room")

        # Legacy format: sources nested inside rooms.
        for s in r.get("sources", []) or []:
            if isinstance(s, dict):
                project_sources.append(_source_from_dict(s, fallback_room_name=room_name))

        barriers = [
            _barrier_from_dict(b)
            for b in r.get("barriers", []) or []
            if isinstance(b, dict)
        ]

        geom_data = r.get("geometry", None)
        if isinstance(geom_data, dict):
            try:
                geometry = RoomGeometry.from_dict(geom_data)
            except Exception:
                geometry = RoomGeometry(room_name=room_name)
        else:
            geometry = RoomGeometry(room_name=room_name)

        geometry.room_name = room_name

        rooms.append(
            Room(
                name=room_name,
                modality=r.get("modality", ""),
                sources=[],  # legacy only; do not use as source of truth
                barriers=barriers,
                geometry=geometry,
                modality_state=(dict(r.get("modality_state", {}) or {}) if isinstance(r.get("modality_state", {}), dict) else {}),
            )
        )

    return Project(
        project_name=data.get("project_name", ""),
        project_type=(
            "refurbishment"
            if str(data.get("project_type", "new_build") or "new_build").strip().lower() == "refurbishment"
            else "new_build"
        ),
        client=data.get("client", ""),
        site=data.get("site", ""),
        assessor=data.get("assessor", ""),
        date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
        modality=data.get("modality", ""),
        notes=data.get("notes", ""),
        tvl_library_mm_pb=data.get("tvl_library_mm_pb", dict(DEFAULT_TVL_LIBRARY_MM_PB)),
        patient_dose_constants=data.get("patient_dose_constants", {}),
        rooms=rooms,
        sources=project_sources,
    )


def project_to_dict(project: Project) -> Dict[str, Any]:
    return {
        "project_name": project.project_name,
        "project_type": (
            "refurbishment"
            if str(getattr(project, "project_type", "new_build") or "new_build").strip().lower() == "refurbishment"
            else "new_build"
        ),
        "client": project.client,
        "site": project.site,
        "assessor": project.assessor,
        "date": project.date,
        "modality": project.modality,
        "notes": project.notes,
        "tvl_library_mm_pb": project.tvl_library_mm_pb,
        "patient_dose_constants": project.patient_dose_constants,

        # New source-of-truth source storage.
        "sources": [asdict(s) for s in getattr(project, "sources", []) or []],

        "rooms": [
            {
                "name": room.name,
                "modality": room.modality,
                "sources": [],  # legacy placeholder only
                "barriers": [asdict(b) for b in room.barriers],
                "geometry": (
                    room.geometry.to_dict()
                    if getattr(room, "geometry", None)
                    else RoomGeometry(room_name=room.name).to_dict()
                ),
                "modality_state": dict(getattr(room, "modality_state", {}) or {}),
            }
            for room in project.rooms
        ],
    }


