"""
room_defaults.py

Central source of truth for default room geometry, default barrier construction,
and default scanner selections.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional
from config.geometry_constants import DEFAULT_ROOM_HEIGHT_M, DEFAULT_WALL_SHIELDING_HEIGHT_M

DEFAULT_CT_ROOM_SPEC: Dict[str, Any] = {
    "room_type": "CT",
    "display_name": "CT",
    "geometry": {"length_m": 4.0, "width_m": 6.0, "height_m": DEFAULT_ROOM_HEIGHT_M},
    "default_scanner": {"vendor": "GE Healthcare", "model": "Revolution Apex Elite"},
    "barrier_defaults": {
        "wall": {
            "material": "Pb",
            "material_detail": "Plasterboard + Pb",
            "pb_mm": 0.88,
            "shielding_start_height_m": 0.0,
            "shielding_end_height_m": DEFAULT_WALL_SHIELDING_HEIGHT_M,
        },
        "door": {
            "material": "Pb",
            "pb_mm": 0.88,
            "sill_height_above_ffl_m": 0.0,
            "head_height_above_ffl_m": DEFAULT_WALL_SHIELDING_HEIGHT_M,
        },
        "viewing_panel": {
            "material": "Pb equivalent glass",
            "pb_mm": 2.20,
            "kvp_basis": 120,
            "sill_height_above_ffl_m": 0.9,
            "head_height_above_ffl_m": 1.8,
        },
        "floor": {"material": "150 mm solid concrete", "pb_mm": None},
        "ceiling": {"material": "150 mm solid concrete", "pb_mm": None},
    },
}

DEFAULT_SPECT_CT_ROOM_SPEC: Dict[str, Any] = deepcopy(DEFAULT_CT_ROOM_SPEC)
DEFAULT_SPECT_CT_ROOM_SPEC.update({
    "room_type": "SPECT/CT",
    "display_name": "SPECT/CT",
    "default_scanner": {"vendor": "GE Healthcare", "model": "Discovery NM/CT 670"},
})

DEFAULT_XRAY_ROOM_SPEC: Dict[str, Any] = {
    "room_type": "X-ray",
    "display_name": "General X-ray",
    "geometry": {"length_m": 5.0, "width_m": 4.0, "height_m": DEFAULT_ROOM_HEIGHT_M},
    "default_scanner": {"vendor": "Generic", "model": "General radiography room"},
    "barrier_defaults": {
        "wall": {
            "material": "Pb",
            "material_detail": "Plasterboard + Pb",
            "pb_mm": 0.88,
            "shielding_start_height_m": 0.0,
            "shielding_end_height_m": DEFAULT_WALL_SHIELDING_HEIGHT_M,
        },
        "door": {
            "material": "Pb",
            "pb_mm": 0.88,
            "sill_height_above_ffl_m": 0.0,
            "head_height_above_ffl_m": DEFAULT_WALL_SHIELDING_HEIGHT_M,
        },
        "viewing_panel": {
            "material": "Pb equivalent glass",
            "pb_mm": 2.20,
            "kvp_basis": 120,
            "sill_height_above_ffl_m": 0.9,
            "head_height_above_ffl_m": 1.8,
        },
        "floor": {"material": "150 mm solid concrete", "pb_mm": None},
        "ceiling": {"material": "150 mm solid concrete", "pb_mm": None},
        "wall_bucky": {
            "material": "Wall bucky / vertical image receptor",
            "width_m": 0.6,
            "height_m": 1.2,
            "sill_height_above_ffl_m": 0.9,
            "head_height_above_ffl_m": DEFAULT_WALL_SHIELDING_HEIGHT_M,
            "max_per_room": 1,
        },
    },
}

DEFAULT_ROOM_SPECS: Dict[str, Dict[str, Any]] = {
    "ct": DEFAULT_CT_ROOM_SPEC,
    "spect_ct": DEFAULT_SPECT_CT_ROOM_SPEC,
    "xray": DEFAULT_XRAY_ROOM_SPEC,
}

WALL_MATERIALS = ["Pb", "Concrete", "Pb glass"]
DOOR_MATERIALS = ["Solid timber", "Solid timber + Pb", "Steel + Pb", "Lead-lined door"]
VIEWING_PANEL_MATERIALS = ["Pb equivalent glass", "Lead acrylic"]
OPENING_TYPES = ["door", "viewing_panel"]


def normalize_room_type(room_type: str) -> str:
    text = str(room_type or "").strip().lower().replace("_", " ")
    aliases = {
        "ct": "ct",
        "diagnostic ct": "ct",
        "spect/ct": "spect_ct",
        "spect ct": "spect_ct",
        "spect-ct": "spect_ct",
        "general x-ray": "xray",
        "general xray": "xray",
        "x-ray": "xray",
        "xray": "xray",
    }
    return aliases.get(text, "ct")


def get_default_room_spec(room_type: str = "CT") -> Dict[str, Any]:
    return deepcopy(DEFAULT_ROOM_SPECS[normalize_room_type(room_type)])


def get_default_scanner(room_type: str = "CT") -> Optional[Dict[str, str]]:
    return get_default_room_spec(room_type).get("default_scanner")


def get_barrier_default(room_type: str, barrier_kind: str) -> Dict[str, Any]:
    spec = get_default_room_spec(room_type)
    return deepcopy(spec.get("barrier_defaults", {}).get(barrier_kind, {}))


def get_standard_construction_for_material(material: str) -> tuple[str, float]:
    """Return the standard starting construction for a selected material.

    This is an editor default only; persisted project values are not migrated.
    """
    key = str(material or "").strip().lower()
    if key == "concrete":
        return "Concrete", 150.0
    if key in {"pb glass", "pb equivalent glass", "lead glass"}:
        return "Pb glass", 2.20
    return "Pb", 0.88
