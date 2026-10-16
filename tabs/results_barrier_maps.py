"""Barrier risk and dose label maps for Results/Geometry overlays.

These functions are kept outside app.py so barrier overlay presentation logic
does not live in the Tk application shell.
"""

from __future__ import annotations

from services.opening_physics import opening_live_result
from tabs.barrier_live_results import get_barrier_live_result
from services.calculation_display_state import room_calculation_display_state


_MODAL_RESULTS_SOURCES = {
    "persisted_pet_single_source",
    "spect_step26_production_dispatch",
    "xray_xr08e_project_fig52",
}


def _canonical_modal_results_by_barrier(app, room) -> dict[str, dict]:
    """Return canonical PET/SPECT Results rows keyed by barrier name.

    PET and SPECT use modality-specific production Results adapters rather than
    the legacy ``calc_barrier_result`` path.  Geometry colour overlays must read
    the same canonical rows as the Results tab; otherwise a valid PET/SPECT PASS
    can be misclassified as FAIL when the legacy calculator returns ERROR.

    CT and other legacy calculation paths intentionally fall through to the
    existing live barrier helper below.
    """
    getter = getattr(app, "get_room_results_model", None)
    if not callable(getter):
        return {}

    try:
        rows = list(getter(room) or [])
    except Exception:
        return {}

    by_name: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("results_source", "") or "").strip() not in _MODAL_RESULTS_SOURCES:
            continue
        name = str(row.get("barrier_name", row.get("barrier", "")) or "").strip()
        if name:
            by_name[name] = row
    return by_name


def _wall_live_results(app, room) -> list[tuple[object, dict]]:
    """Return wall barriers paired with the same live result path used by the Barriers tab.

    The Geometry overlay must not read a stale cached result set.  The Barriers
    table computes each row via get_barrier_live_result(), so the overlay uses
    that helper as the primary source and only falls back to app.get_room_barrier_results()
    if the live helper is unavailable for a row.
    """
    barriers = list(getattr(room, "barriers", []) or [])
    pairs: list[tuple[object, dict]] = []
    canonical_modal = _canonical_modal_results_by_barrier(app, room)

    fallback_results = []
    try:
        fallback_results = list(app.get_room_barrier_results(room) or [])
    except Exception:
        fallback_results = []

    for index, barrier in enumerate(barriers):
        name = str(getattr(barrier, "name", "") or "").strip()
        live = canonical_modal.get(name)

        if not isinstance(live, dict):
            try:
                live = get_barrier_live_result(app, room, barrier)
            except Exception:
                live = None

        if not isinstance(live, dict):
            try:
                candidate = fallback_results[index]
            except Exception:
                candidate = {}
            live = candidate if isinstance(candidate, dict) else {}

        pairs.append((barrier, live))

    return pairs


def get_barrier_dose_label_map(app, room_name: str) -> dict:
    room = app.get_room_by_name(room_name)
    if not room:
        return {}

    if room_calculation_display_state(app, room).blocking:
        return {}

    dose_map = {}

    def fmt_dose(live: dict) -> str:
        if not isinstance(live, dict):
            return ""

        def _first_value(*keys):
            for key in keys:
                value = live.get(key)
                if value not in (None, ""):
                    return value
            return None

        tx = _first_value(
            "transmitted_dose_uSv_per_week",
            "Tx_uSv_per_week",
            "transmitted_weekly_dose_uSv",
        )

        unshielded = _first_value(
            "unshielded_weekly_dose_uSv",
            "unshielded_dose_uSv_per_week",
            "unshielded_uSv_per_week",
            "unshielded_weekly_dose_uSv_per_week",
        )

        transmission_b = _first_value(
            "barrier_transmission_factor_B",
            "required_transmission",
            "transmission_factor_B",
        )

        lines = []

        try:
            if tx not in (None, ""):
                lines.append(f"Tx {float(tx):.2f} µSv/wk")
        except Exception:
            pass

        try:
            if unshielded not in (None, ""):
                lines.append(f"Unsh {float(unshielded):.1f} µSv/wk")
        except Exception:
            pass

        try:
            if transmission_b not in (None, ""):
                lines.append(f"B={float(transmission_b):.6f}")
        except Exception:
            pass

        # XR-19C: expose the extra primary layer on the chest-bucky wall.
        if bool(live.get("bucky_shield_attenuation_applied", False)):
            try:
                bbs = float(live.get("bucky_shield_primary_transmission"))
                lines.append(f"Bucky shield Pb 2.20 mm B={bbs:.6f}")
            except Exception:
                lines.append("Bucky shield Pb 2.20 mm credited")

        # XR-17C: make intervening Control Wall credit visible on the geometry
        # canvas without changing status colours or calculation values.
        if bool(live.get("control_wall_attenuation_applied", False)):
            try:
                bcw = float(live.get("control_wall_secondary_transmission"))
                lines.append(f"CW credit B={bcw:.6f}")
            except Exception:
                lines.append("CW attenuation credited")

        return "\n".join(lines)

    # Wall barriers: use the same current live-result path as the Barriers tab.
    for barrier, live in _wall_live_results(app, room):
        name = str(getattr(barrier, "name", "") or "").strip()
        label = fmt_dose(live if isinstance(live, dict) else {})
        if name and label:
            dose_map[name] = label

    # XR-20A finite Chest Bucky sub-barrier is a separate canonical result.
    canonical_modal = _canonical_modal_results_by_barrier(app, room)
    bucky_live = canonical_modal.get("Bucky shield")
    if isinstance(bucky_live, dict):
        # XR-20B: the shielded sub-barrier inherits occupancy/design goal
        # from its parent chest-bucky wall.  Make that assumption explicit
        # on the canvas rather than leaving it implicit in the calculation.
        inherited = []
        try:
            inherited.append(f"T={float(bucky_live.get('occupancy_factor')):g}")
        except (TypeError, ValueError):
            pass
        try:
            inherited.append(f"P={float(bucky_live.get('design_goal_uSv_per_week')):g} µSv/wk")
        except (TypeError, ValueError):
            pass
        label = fmt_dose(bucky_live)
        parts = inherited + ([label] if label else [])
        if parts:
            dose_map["Bucky shield"] = "\n".join(parts)

    # Opening barriers
    geom = getattr(room, "geometry", None)
    openings = list(getattr(geom, "openings", []) or []) if geom else []

    for opening_index, opening in enumerate(openings, start=1):
        result = opening_live_result(app, room, opening, opening_index)
        if not result:
            continue

        opening_barrier, live = result
        if opening_barrier is None or not isinstance(live, dict):
            continue

        name = str(getattr(opening_barrier, "name", "") or "").strip()
        label = fmt_dose(live)
        if name and label:
            # GXR openings are evaluated as secondary sub-barriers by
            # services.opening_physics; do not infer a primary component
            # from the parent wall or the opening's compliance colour.
            if str(getattr(room, "modality", "") or "").upper() == "X-RAY":
                label = "SECONDARY\n" + label
            else:
                # Only display a role for other modalities when the live
                # calculation explicitly supplies one.
                role = str(live.get("radiation_classification", "") or "").strip().upper()
                if role in {"PRIMARY", "SECONDARY", "PRIMARY + SECONDARY"}:
                    label = role + "\n" + label
            dose_map[name] = label

    return dose_map


def get_barrier_risk_map(app, room_name: str) -> dict:
    room = app.get_room_by_name(room_name)
    if not room:
        return {}

    if room_calculation_display_state(app, room).blocking:
        return {}

    def classify(live: dict) -> str:
        if not isinstance(live, dict):
            live = {}

        status = str(live.get("compliance_status", "")).strip().upper()

        try:
            margin = float(live.get("margin_mm", 0.0) or 0.0)
        except Exception:
            margin = 0.0

        if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin < 0:
            return "fail"
        if status in {"REVIEW", "WARN", "WARNING"} or margin < 0.5:
            return "review"
        return "pass"

    risk = {}

    # Wall barriers: use the same current live-result path as the Barriers tab.
    for barrier, live in _wall_live_results(app, room):
        name = str(getattr(barrier, "name", "") or "").strip()
        if name:
            risk[name] = classify(live)

    # XR-20A finite Chest Bucky sub-barrier has its own risk state.
    canonical_modal = _canonical_modal_results_by_barrier(app, room)
    bucky_live = canonical_modal.get("Bucky shield")
    if isinstance(bucky_live, dict):
        risk["Bucky shield"] = classify(bucky_live)

    # Opening sub-barriers: same physics path as Barrier table
    geom = getattr(room, "geometry", None)
    openings = list(getattr(geom, "openings", []) or []) if geom else []

    for opening_index, opening in enumerate(openings, start=1):
        result = opening_live_result(app, room, opening, opening_index)

        if not result:
            continue

        opening_barrier, live = result

        if opening_barrier is None:
            continue

        name = str(getattr(opening_barrier, "name", "") or "").strip()
        if name:
            if str(getattr(room, "modality", "") or "").upper() == "X-RAY":
                status = str(live.get("compliance_status", "") or "").strip().upper()
                try:
                    margin = float(live.get("margin_mm", 0.0) or 0.0)
                except Exception:
                    margin = 0.0
                risk[name] = "fail" if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin < 0 else (
                    "review" if status in {"REVIEW", "WARN", "WARNING"} else "pass"
                )
            else:
                risk[name] = classify(live)

    return risk
