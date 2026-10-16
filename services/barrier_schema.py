from __future__ import annotations

from models.shielding_models import Barrier
from engine.shielding_engine import parse_material_option


MATERIAL_FAMILIES = {"Pb", "Concrete", "Pb glass"}


def coerce_barrier_schema(barrier: Barrier) -> None:
    """Normalise legacy barrier material/thickness fields in-place."""
    raw_material = str(getattr(barrier, "material", "") or "").strip()
    legacy = str(
        getattr(barrier, "material_legacy", "") or raw_material or "Pb 0.88 mm (10 kg/m2)"
    )

    material_for_parse = legacy if raw_material not in MATERIAL_FAMILIES else raw_material
    family, inferred = parse_material_option(material_for_parse)

    if raw_material not in MATERIAL_FAMILIES:
        barrier.material = family

    if not hasattr(barrier, "material_legacy") or not getattr(barrier, "material_legacy", ""):
        setattr(barrier, "material_legacy", legacy)

    try:
        thickness = float(getattr(barrier, "thickness_mm", 0.0) or 0.0)
    except Exception:
        thickness = 0.0

    if thickness <= 0:
        setattr(barrier, "thickness_mm", float(inferred))
