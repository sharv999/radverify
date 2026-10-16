"""Compatibility imports for legacy report opening helpers.

Opening physics interpretation now lives in :mod:`services.opening_physics`.
New code should import there directly.  These aliases remain temporarily for
external/internal callers that still import ``reports.opening_helpers``.
"""

from services.opening_physics import (
    make_opening_physics_barrier,
    opening_barrier_id,
    opening_display_material,
    opening_live_result,
    opening_parent_barrier,
    opening_pb_equiv_mm,
    opening_physics_material,
    opening_type_normalized,
)
from services.barrier_risk import barrier_heatmap_color, classify_barrier_visual_state

__all__ = [
    "barrier_heatmap_color",
    "classify_barrier_visual_state",
    "make_opening_physics_barrier",
    "opening_barrier_id",
    "opening_display_material",
    "opening_live_result",
    "opening_parent_barrier",
    "opening_pb_equiv_mm",
    "opening_physics_material",
    "opening_type_normalized",
]
