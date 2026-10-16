"""Modality-neutral source-marker layout resolution.

The modality plugin owns the rendering descriptor.  Tk, preview overlays, and
PDF renderers consume the same resolved marker points rather than independently
choosing which physical point anchors the patient marker or 1 m reference
circle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class SourceMarkerPoints:
    """Resolved display-space anchor points for one source marker group."""

    source: tuple[float, float]
    radiation: tuple[float, float]
    patient: tuple[float, float]
    reference_circle: tuple[float, float]


def _offset_point(
    x: float,
    y: float,
    px_per_m: float,
    rotation_deg: float,
    offset_m: float,
) -> tuple[float, float]:
    offset_px = float(offset_m) * float(px_per_m)
    theta = math.radians(float(rotation_deg))
    return (
        float(x) + offset_px * math.cos(theta),
        float(y) + offset_px * math.sin(theta),
    )


def resolve_source_marker_points(
    source_x: float,
    source_y: float,
    px_per_m: float,
    rotation_deg: float,
    rendering: Mapping[str, Any] | None,
) -> SourceMarkerPoints:
    """Resolve all source-marker anchors from one neutral render descriptor."""

    spec = dict(rendering or {})
    source = (float(source_x), float(source_y))
    radiation = _offset_point(
        *source,
        px_per_m,
        rotation_deg,
        float(spec.get("radiation_symbol_offset_m", 0.0) or 0.0),
    )
    patient = _offset_point(
        *source,
        px_per_m,
        rotation_deg,
        float(spec.get("patient_symbol_offset_m", 0.5) or 0.0),
    )

    anchor = str(spec.get("reference_circle_anchor", "source") or "source").strip().lower()
    if anchor == "patient":
        reference_circle = patient
    elif anchor == "radiation":
        reference_circle = radiation
    else:
        reference_circle = source

    return SourceMarkerPoints(
        source=source,
        radiation=radiation,
        patient=patient,
        reference_circle=reference_circle,
    )
