"""Frozen terminology, units, and defaults for the PET preview UI.

This contract is deliberately presentation-only. It gives the non-production
single-source PET preview one canonical set of field keys, labels, units,
default values, ordering, and results-column headings before any future move
into production project, calculation, Results, or report paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PET_PREVIEW_UI_CONTRACT_VERSION = 7
PET_PREVIEW_UI_BASELINE = "pet-single-source-ui-v7-room-mode"

WidgetKind = Literal["entry", "combobox"]


@dataclass(frozen=True)
class PetPreviewUiField:
    key: str
    label: str
    unit: str
    default: str
    widget_kind: WidgetKind = "entry"


PET_ROOM_MODE_OPTIONS = ("Imaging Room", "Uptake Room")

PET_SOURCE_UI_FIELDS = (
    PetPreviewUiField("room_mode", "PET room mode", "", "Imaging Room", "combobox"),
    PetPreviewUiField("radionuclide", "Radionuclide", "", "F18", "combobox"),
    PetPreviewUiField(
        "injected_activity_mbq",
        "Administered activity per patient",
        "MBq/patient",
        "250",
    ),
    PetPreviewUiField("patients_per_week", "Patient workload", "patients/week", "30"),
    PetPreviewUiField(
        "phase_1_start_h",
        "Uptake time",
        "h",
        "0",
    ),
    PetPreviewUiField("phase_1_duration_h", "Imaging time", "h", "1"),
    PetPreviewUiField(
        "phase_1_activity_retention_factor",
        "Voiding factor",
        "dimensionless (0–1)",
        "1.0",
    ),
)

PET_POSITION_UI_FIELDS = (
    PetPreviewUiField("x_from_west_m", "Distance from West wall", "m", "room centre"),
    PetPreviewUiField("y_from_south_m", "Distance from South wall", "m", "room centre"),
    PetPreviewUiField("height_above_ffl_m", "Height above finished floor level", "m AFFL", "1.0"),
)

PET_RESULTS_COLUMNS = (
    ("name", "Barrier", 150),
    ("material", "Material", 165),
    ("distance", "Distance (m)", 85),
    ("occupancy", "Occupancy T", 85),
    ("goal", "Design goal (µSv/week)", 135),
    ("tvls", "Required TVLs", 95),
    ("required", "Required (mm)", 100),
    ("provided", "Provided (mm)", 100),
    ("transmitted", "Transmitted dose (µSv/week)", 160),
    ("status", "Status", 100),
)

PET_SOURCE_UI_DEFAULTS = {field.key: field.default for field in PET_SOURCE_UI_FIELDS}


def display_label(field: PetPreviewUiField) -> str:
    """Return the canonical visible label, including its frozen unit."""
    return field.label if not field.unit else f"{field.label} ({field.unit})"
