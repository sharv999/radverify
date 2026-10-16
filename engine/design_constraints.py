from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from modalities.registry import registered_modalities


@dataclass
class DesignConstraintProfile:
    room_type: str
    classification: str
    default_energy_label: str
    default_solver_mode: str
    expected_source_types: List[str] = field(default_factory=list)

    controlled_area_required: bool = False
    patient_radioactivity_present: bool = False
    xray_generator_present: bool = False
    hybrid_ct_present: bool = False
    compliance_only: bool = False

    default_internal_design_goal_uSv_per_week: float = 50.0
    default_external_design_goal_uSv_per_week: float = 10.0
    default_internal_occupancy_factor: float = 1.0
    default_external_occupancy_factor: float = 0.2

    notes: str = ""


ROOM_TYPE_CONSTRAINTS: Dict[str, DesignConstraintProfile] = {
    spec.modality_id: DesignConstraintProfile(
        room_type=spec.modality_id,
        classification=spec.classification,
        default_energy_label=spec.default_energy_label,
        default_solver_mode=spec.default_solver_mode,
        expected_source_types=spec.expected_source_types,
        controlled_area_required=spec.controlled_area_required,
        patient_radioactivity_present=spec.patient_radioactivity_present,
        xray_generator_present=spec.xray_generator_present,
        hybrid_ct_present=spec.hybrid_ct_present,
        compliance_only=spec.compliance_only,
        default_internal_design_goal_uSv_per_week=spec.default_internal_design_goal_uSv_per_week,
        default_external_design_goal_uSv_per_week=spec.default_external_design_goal_uSv_per_week,
        default_internal_occupancy_factor=spec.default_internal_occupancy_factor,
        default_external_occupancy_factor=spec.default_external_occupancy_factor,
        notes=spec.notes,
    )
    for spec in registered_modalities()
}


AREA_CLASSIFICATION_DEFAULTS = {
    "public": {
        "adjacent_area_labels": ["Office", "Waiting Area", "Corridor", "Outdoor Area", "Toilet", "Store"],
        "occupancy_factor": 0.2,
        "design_goal_uSv_per_week": 10.0,
        "classification_logic": "non-controlled",
    },
    "controlled": {
        "adjacent_area_labels": ["Control Room", "Controlled Area"],
        "occupancy_factor": 1.0,
        "design_goal_uSv_per_week": 50.0,
        "classification_logic": "controlled",
    },
    "clinical": {
        "adjacent_area_labels": ["Clinical Area"],
        "occupancy_factor": 1.0,
        "design_goal_uSv_per_week": 10.0,
        "classification_logic": "clinical_noncontrolled_default",
    },
}


def get_room_constraint_profile(room_modality: str) -> DesignConstraintProfile:
    text = (room_modality or "").strip()
    return ROOM_TYPE_CONSTRAINTS.get(
        text,
        DesignConstraintProfile(
            room_type=text or "Unknown",
            classification="generic",
            default_energy_label="140 kVp",
            default_solver_mode="auto",
            notes="Fallback generic constraint profile.",
        ),
    )


def classify_adjacent_area(adjacent_area: str) -> str:
    text = (adjacent_area or "").strip().lower()

    controlled = {"control room", "controlled area"}
    public = {"office", "waiting area", "corridor", "outdoor area", "toilet", "store"}
    clinical = {"clinical area"}

    if text in controlled:
        return "controlled"
    if text in clinical:
        return "clinical"
    if text in public:
        return "public"
    return "public"


def get_barrier_design_defaults(room_modality: str, adjacent_area: str) -> dict:
    profile = get_room_constraint_profile(room_modality)
    area_class = classify_adjacent_area(adjacent_area)

    if area_class == "controlled":
        return {
            "occupancy_factor": profile.default_internal_occupancy_factor,
            "design_goal_uSv_per_week": profile.default_internal_design_goal_uSv_per_week,
            "classification": "controlled",
        }

    return {
        "occupancy_factor": profile.default_external_occupancy_factor,
        "design_goal_uSv_per_week": profile.default_external_design_goal_uSv_per_week,
        "classification": area_class,
    }


def room_sources_match_profile(room_modality: str, actual_source_types: List[str]) -> bool:
    profile = get_room_constraint_profile(room_modality)
    expected = sorted(profile.expected_source_types)
    actual = sorted([(s or "").strip() for s in actual_source_types])
    return expected == actual


def build_room_constraint_summary(room_modality: str) -> dict:
    profile = get_room_constraint_profile(room_modality)
    return {
        "room_type": profile.room_type,
        "classification": profile.classification,
        "default_energy_label": profile.default_energy_label,
        "default_solver_mode": profile.default_solver_mode,
        "expected_source_types": list(profile.expected_source_types),
        "controlled_area_required": profile.controlled_area_required,
        "patient_radioactivity_present": profile.patient_radioactivity_present,
        "xray_generator_present": profile.xray_generator_present,
        "hybrid_ct_present": profile.hybrid_ct_present,
        "compliance_only": profile.compliance_only,
        "default_internal_design_goal_uSv_per_week": profile.default_internal_design_goal_uSv_per_week,
        "default_external_design_goal_uSv_per_week": profile.default_external_design_goal_uSv_per_week,
        "default_internal_occupancy_factor": profile.default_internal_occupancy_factor,
        "default_external_occupancy_factor": profile.default_external_occupancy_factor,
        "notes": profile.notes,
    }
