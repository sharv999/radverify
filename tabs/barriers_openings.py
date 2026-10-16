"""Barrier-opening helpers for the Barriers tab.

This module owns the helper logic that treats room openings, such as doors and
viewing panels, as physics rows in the barrier table.  The functions operate on
plain room/opening objects where possible, and accept the desktop app instance
only where table/UI state or live calculation context is required.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.shielding_models import Barrier, Room
from tabs.barrier_risk_ui import (
    barrier_heatmap_color,
    classify_barrier_visual_state,
)

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

from tabs.barrier_live_results import (
    display_recommended_thickness_mm,
    display_required_thickness_mm,
)

def _opening_display_status_from_live(live: dict, *, conservative_margin: bool = True) -> str:
    """
    Display status for all opening rows: doors and viewing panels.

    Rules:
      FAIL / negative margin        -> FAIL
      PASS with margin < 0.5 mm     -> REVIEW
      PASS with margin >= 0.5 mm    -> PASS
    """
    if not isinstance(live, dict):
        live = {}

    status = str(
        live.get("compliance_status")
        or live.get("status")
        or ""
    ).strip().upper()

    try:
        margin_mm = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin_mm = 0.0

    if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin_mm < 0:
        return "FAIL"

    if status in {"REVIEW", "WARN", "WARNING"} or (conservative_margin and margin_mm < 0.5):
        return "REVIEW"

    return "PASS"


def _opening_row_tag_from_live(live: dict, *, conservative_margin: bool = True) -> str:
    status = _opening_display_status_from_live(live, conservative_margin=conservative_margin)

    if status == "FAIL":
        return "qa_fail"

    if status == "REVIEW":
        return "qa_review"

    return "qa_pass"



def barrier_table_values_for_barrier_live(
    app: Any,
    barrier: Barrier,
    live: Dict[str, Any],
    *,
    display_material: Optional[str] = None,
    conservative_margin: bool = True,
) -> list[Any]:

    live = dict(live or {})

    effective_material = (
        display_material
        or getattr(barrier, "material", "")
        or live.get("material", "")
    )

    live["material"] = effective_material
    live["display_required_thickness_mm"] = display_required_thickness_mm(live)
    live["display_recommended_thickness_mm"] = display_recommended_thickness_mm(live)

    values = []
    for col in app.BARRIER_EDIT_COLUMNS:
        if col == "unshielded_weekly_dose_uSv":
            values.append(live.get("unshielded_weekly_dose_uSv", ""))
        elif col == "transmitted_dose_uSv_per_week":
            values.append(live.get("transmitted_dose_uSv_per_week", ""))
        elif col == "thickness_mm":
            try:
                values.append(f"{float(getattr(barrier, 'thickness_mm', 0.0) or 0.0):.2f}")
            except Exception:
                values.append("")
        elif col == "material" and display_material is not None:
            values.append(display_material)
        else:
            values.append(getattr(barrier, col, ""))

    row_confidence = app._row_confidence_from_live(barrier.name, live)
    display_status = _opening_display_status_from_live(live, conservative_margin=conservative_margin)

    for col in app.BARRIER_RESULT_COLUMNS:
        if col == "confidence":
            values.append(row_confidence)
        elif col == "mm_shortfall":
            try:
                margin = float(live.get("margin_mm", 0.0) or 0.0)
                shortfall = abs(margin) if margin < 0 else 0.0
                values.append(round(shortfall, 3))
            except Exception:
                values.append("")
        elif col == "compliance_status":
            values.append(display_status)
        else:
            values.append(live.get(col, ""))

    return values


def insert_opening_physics_rows(app: Any, room: Room) -> None:
    geom = getattr(room, "geometry", None)
    if geom is None or not hasattr(app, "barrier_table"):
        return

    openings = list(getattr(geom, "openings", []) or [])
    for idx, opening in enumerate(openings, start=1):
        opening_barrier, live = opening_live_result(app, room, opening, idx)
        if opening_barrier is None:
            continue

        display_material = opening_display_material(opening)
        values = barrier_table_values_for_barrier_live(
            app,
            opening_barrier,
            live,
            display_material=display_material,
            conservative_margin=str(getattr(room, "modality", "") or "").upper() != "X-RAY",
        )

        row_confidence = app._row_confidence_from_live(opening_barrier.name, live)

        if app.heatmap_mode_var.get():
            color = barrier_heatmap_color(app, live, row_confidence)
            tag = f"heat_{color}"
            try:
                app.barrier_table.tag_configure(tag, background=color)
            except Exception:
                pass
        else:
            tag = _opening_row_tag_from_live(
                live, conservative_margin=str(getattr(room, "modality", "") or "").upper() != "X-RAY"
            )

        app.barrier_table.insert("", "end", values=values, tags=(tag,))
