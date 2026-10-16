from __future__ import annotations

from typing import Any, Dict, List, Optional
from engine.shielding_engine import compute_room_barrier_table

MATERIAL_FAMILIES = ["Pb", "Concrete", "Pb glass"]
LEAD_MM = [0.44, 0.88, 1.32, 1.76, 2.20, 2.64, 3.08, 3.52, 5.28, 7.04]
CONCRETE_MM = [80.0, 100.0, 120.0, 150.0, 180.0, 200.0, 250.0, 300.0, 350.0, 400.0]
PB_GLASS_MM = [2.2, 4.4, 6.6, 8.8, 11.0]


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ''):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _round_up(value: float, options: List[float]) -> float:
    for option in sorted(options):
        if option >= value:
            return option
    return sorted(options)[-1]


def _candidate(material: str, live: Dict[str, Any]) -> Dict[str, Any]:
    required = _safe_float(live.get('required_thickness_mm'), 0.0) or 0.0
    if material == 'Pb':
        thickness = _round_up(max(required, 0.44), LEAD_MM)
        source = 'commercial lead'
    elif material == 'Concrete':
        thickness = _round_up(max(required, 80.0), CONCRETE_MM)
        source = 'commercial concrete'
    else:
        thickness = _round_up(max(required, 2.2), PB_GLASS_MM)
        source = 'lead glass'
    margin = thickness - required
    if margin >= 0:
        status = 'PASS'
        confidence = min(0.97, 0.82 + min(0.12, margin / 25.0))
    elif thickness >= 0.9 * max(required, 1.0):
        status = 'REVIEW'
        confidence = 0.68
    else:
        status = 'FAIL'
        confidence = 0.35
    rationale = [
        'Predicted to meet required thickness.' if status == 'PASS' else ('Close to required thickness but review-worthy.' if status == 'REVIEW' else 'Still predicted to be under-required.'),
        f'Based on {source} sizing.',
        f'Required thickness is {required:.2f} mm.',
        f'Predicted margin is {margin:.2f} mm.'
    ]
    score = (1.0 if status == 'PASS' else 0.55 if status == 'REVIEW' else 0.0) + confidence - min(thickness / 500.0, 0.5)
    return {
        'material': material,
        'thickness_mm': round(thickness, 2),
        'expected_status': status,
        'predicted_confidence': round(confidence, 3),
        'score': round(score, 3),
        'rationale': rationale,
        'required_thickness_mm': round(required, 3),
    }


def optimise_flagged_barriers(project, energy_label: str, solver_mode: str, room_name: Optional[str] = None):
    recommendations: List[Dict[str, Any]] = []
    rooms = [r for r in project.rooms if room_name is None or r.name == room_name]

    for room in rooms:
        results = compute_room_barrier_table(
            project,
            room.name,
            energy_label,
            solver_mode=solver_mode,
        )

        for barrier, live in zip(room.barriers, results):
            current_status = str(live.get("compliance_status", "")).upper()

            if current_status == "PASS":
                continue

            candidates = [_candidate(material, live) for material in MATERIAL_FAMILIES]
            candidates.sort(key=lambda c: c["score"], reverse=True)

            best = candidates[0] if candidates else {}

            recommendations.append({
                "room_name": room.name,
                "barrier_name": barrier.name,
                "baseline": {
                    "compliance_status": current_status,
                    "actual_thickness_mm": live.get("actual_thickness_mm", getattr(barrier, "thickness_mm", None)),
                    "required_thickness_mm": live.get("required_thickness_mm"),
                    "material": getattr(barrier, "material", ""),
                },
                "best_candidate": best,
                "alternatives": candidates[:5],
                "explanation": [
                    f"Recommend {best.get('material', '')} @ {best.get('thickness_mm', '')} mm."
                ],
            })

    return recommendations
