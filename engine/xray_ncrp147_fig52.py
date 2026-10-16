"""NCRP 147 Section 5.3 / Figure 5.2 representative radiographic-room physics.

XR-08B qualification layer.  It deliberately stays independent of the issued
report gate: XR-08A keeps output fail-closed until geometry/UI integration and
report replay are requalified against these scenarios.

The module uses the NCRP workload-distribution transmission fits and the
worked-example source terms from Section 5.3.  Air-kerma values are represented
numerically as mGy/week; the existing application uses the equivalent numeric
uSv/week convention for diagnostic x-ray shielding bookkeeping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

from engine.shielding_engine import _archer_required_thickness_mm, _archer_transmission_from_thickness


FIG52_VERSION = "xr08b-ncrp147-s5.3-fig5.2-v1"

# NCRP 147 Tables B.1 and C.1.  XR-08B qualifies lead and standard-weight
# concrete for the three radiographic-room workload distributions required by
# the representative-room scenarios.
PRIMARY_PARAMS = {
    "all_barriers": {
        "Pb": {"alpha": 2.346, "beta": 15.90, "gamma": 0.4982},
        "Concrete": {"alpha": 3.626e-2, "beta": 1.429e-1, "gamma": 0.4932},
    },
    "chest_bucky": {
        "Pb": {"alpha": 2.264, "beta": 13.08, "gamma": 0.5600},
        "Concrete": {"alpha": 3.552e-2, "beta": 1.177e-1, "gamma": 0.6007},
    },
    "floor_or_other": {
        "Pb": {"alpha": 2.651, "beta": 16.56, "gamma": 0.4585},
        "Concrete": {"alpha": 3.994e-2, "beta": 1.448e-1, "gamma": 0.4231},
    },
}
SECONDARY_PARAMS = {
    "all_barriers": {
        "Pb": {"alpha": 2.298, "beta": 17.38, "gamma": 0.6193},
        "Concrete": {"alpha": 3.610e-2, "beta": 1.433e-1, "gamma": 0.5600},
    },
    "chest_bucky": {
        "Pb": {"alpha": 2.256, "beta": 13.80, "gamma": 0.8837},
        "Concrete": {"alpha": 3.560e-2, "beta": 1.079e-1, "gamma": 0.7705},
    },
    "floor_or_other": {
        "Pb": {"alpha": 2.513, "beta": 17.34, "gamma": 0.4994},
        "Concrete": {"alpha": 3.920e-2, "beta": 1.464e-1, "gamma": 0.4486},
    },
}

PRESHIELD_MM = {
    "none": {"Pb": 0.0, "Concrete": 0.0},
    "grid_cassette": {"Pb": 0.30, "Concrete": 30.0},
    "grid_cassette_support": {"Pb": 0.85, "Concrete": 72.0},
}


@dataclass(frozen=True)
class Fig52Component:
    name: str
    kind: str  # primary | secondary
    unshielded_mGy_week: float
    distribution: str
    preshield: str = "none"


@dataclass(frozen=True)
class Fig52Scenario:
    scenario_id: str
    label: str
    components: tuple[Fig52Component, ...]
    combination: str  # joint | governing_max
    section: str


def _family(material: str) -> str:
    text = str(material or "").strip()
    if text.startswith("Concrete"):
        return "Concrete"
    if text == "Pb" or text.startswith("Pb "):
        return "Pb"
    raise ValueError(f"Fig. 5.2 material {material!r} is not qualified; use Pb or standard-weight Concrete.")


def _params(kind: str, distribution: str, material: str) -> Mapping[str, float]:
    table = PRIMARY_PARAMS if kind == "primary" else SECONDARY_PARAMS
    try:
        return table[distribution][_family(material)]
    except KeyError as exc:
        raise ValueError(f"Unqualified NCRP 147 {kind} distribution {distribution!r}.") from exc


def structural_transmission_factor(kind: str, distribution: str, structural_mm: float, material: str) -> float:
    """Transmission of a structural layer alone, with no receptor preshield credit."""
    family = _family(material)
    x = max(0.0, float(structural_mm))
    return float(_archer_transmission_from_thickness(x, _params(kind, distribution, family)))


def component_transmitted_mGy_week(component: Fig52Component, structural_mm: float, material: str) -> float:
    family = _family(material)
    x = max(0.0, float(structural_mm))
    if component.kind == "primary":
        x += float(PRESHIELD_MM[component.preshield][family])
    B = _archer_transmission_from_thickness(x, _params(component.kind, component.distribution, family))
    return float(component.unshielded_mGy_week) * B


def component_required_structural_mm(component: Fig52Component, target_mGy_week: float, material: str) -> float:
    target = float(target_mGy_week)
    if target <= 0.0:
        raise ValueError("Target air kerma must be positive.")
    if component.unshielded_mGy_week <= target:
        return 0.0
    family = _family(material)
    B = target / float(component.unshielded_mGy_week)
    total = _archer_required_thickness_mm(B, _params(component.kind, component.distribution, family))
    pre = float(PRESHIELD_MM[component.preshield][family]) if component.kind == "primary" else 0.0
    return max(0.0, total - pre)


def required_joint_structural_mm(components: Iterable[Fig52Component], target_mGy_week: float, material: str) -> float:
    """Iteratively solve NCRP Appendix C general-case sum of transmitted kerma."""
    comps = tuple(components)
    target = float(target_mGy_week)
    if target <= 0.0:
        raise ValueError("Target air kerma must be positive.")
    if sum(c.unshielded_mGy_week for c in comps) <= target:
        return 0.0

    def total(x: float) -> float:
        return sum(component_transmitted_mGy_week(c, x, material) for c in comps)

    lo, hi = 0.0, 1.0
    while total(hi) > target and hi < 2000.0:
        hi *= 2.0
    if total(hi) > target:
        raise ValueError("Unable to bound NCRP 147 Fig. 5.2 barrier solution.")
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if total(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def solve_fig52_scenario(scenario: Fig52Scenario, target_mGy_week: float, material: str) -> Dict[str, object]:
    individual = {
        c.name: component_required_structural_mm(c, target_mGy_week, material)
        for c in scenario.components
    }
    if scenario.combination == "joint":
        required = required_joint_structural_mm(scenario.components, target_mGy_week, material)
    elif scenario.combination == "governing_max":
        required = max(individual.values(), default=0.0)
    else:
        raise ValueError(f"Unknown Fig. 5.2 combination rule {scenario.combination!r}.")
    transmitted = sum(component_transmitted_mGy_week(c, required, material) for c in scenario.components)
    return {
        "fig52_version": FIG52_VERSION,
        "scenario_id": scenario.scenario_id,
        "label": scenario.label,
        "section": scenario.section,
        "combination": scenario.combination,
        "target_mGy_week": float(target_mGy_week),
        "material": _family(material),
        "required_structural_mm": required,
        "individual_required_mm": individual,
        "transmitted_sum_at_required_mm": transmitted,
        "components": [
            {
                "name": c.name,
                "kind": c.kind,
                "unshielded_mGy_week": c.unshielded_mGy_week,
                "distribution": c.distribution,
                "preshield": c.preshield,
                "preshield_mm": PRESHIELD_MM[c.preshield][_family(material)] if c.kind == "primary" else 0.0,
            }
            for c in scenario.components
        ],
    }


def representative_fig52_scenarios(n_patients_week: float = 125.0) -> Dict[str, Fig52Scenario]:
    """Return Section 5.3 representative-room scenarios scaled to patient count.

    Distances follow the worked example and are encoded transparently in the
    source terms below.  Geometry integration will replace these representative
    distances with project-specific values in the next qualification step.
    """
    n = float(n_patients_week)
    scale = n / 125.0
    return {
        "floor_under_table": Fig52Scenario(
            "floor_under_table", "Floor beneath radiographic table", (
                Fig52Component("primary_floor", "primary", 39.0 * scale, "floor_or_other", "grid_cassette_support"),
                Fig52Component("secondary_floor", "secondary", 0.47 * scale, "all_barriers"),
            ), "governing_max", "5.3.1",
        ),
        "ceiling": Fig52Scenario(
            "ceiling", "Ceiling", (
                Fig52Component("secondary_ceiling", "secondary", 0.84 * scale, "all_barriers"),
            ), "governing_max", "5.3.2",
        ),
        "chest_bucky_wall": Fig52Scenario(
            "chest_bucky_wall", "Wall containing chest image receptor", (
                Fig52Component("primary_chest_bucky", "primary", 46.0 * scale, "chest_bucky", "grid_cassette_support"),
                Fig52Component("secondary_chest_bucky", "secondary", 1.11 * scale, "chest_bucky"),
            ), "governing_max", "5.3.3",
        ),
        "darkroom_wall": Fig52Scenario(
            "darkroom_wall", "Darkroom wall (legacy film workflow)", (
                Fig52Component("secondary_darkroom", "secondary", 1.1 * scale, "all_barriers"),
            ), "governing_max", "5.3.4",
        ),
        "cross_table_wall": Fig52Scenario(
            "cross_table_wall", "Cross-table lateral wall", (
                Fig52Component("primary_cross_table", "primary", 7.5 * scale, "floor_or_other", "grid_cassette"),
                Fig52Component("secondary_cross_table", "secondary", 0.72 * scale, "floor_or_other"),
            ), "joint", "5.3.5",
        ),
        "control_wall": Fig52Scenario(
            "control_wall", "Control wall", (
                Fig52Component("secondary_control", "secondary", 1.3 * scale, "all_barriers"),
            ), "governing_max", "5.3.6",
        ),
    }
