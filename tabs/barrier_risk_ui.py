from __future__ import annotations

from typing import Any, Dict, Optional
from models.shielding_models import Barrier, Room
from geometry.barrier_sync import safe_refresh_barrier_schedule
from tabs.barrier_live_results import get_barrier_live_result


def barrier_heatmap_color(app, live: Dict[str, Any], confidence: float) -> str:
    risk, _ = classify_barrier_visual_state(
        app,
        live=live,
        confidence=confidence,
        severities=set(),
        mismatch_flag=False,
    )

    try:
        margin = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin = 0.0

    # Softer, desaturated base colours (consultancy-style)
    if risk == "FAIL":
        base = (220, 140, 140)   # muted red
    elif risk == "REVIEW":
        base = (235, 210, 140)   # muted amber
    else:
        base = (170, 210, 170)   # muted green

    # Gentle intensity scaling (less aggressive than before)
    if margin < 0:
        intensity = 1.0
    else:
        intensity = max(0.6, 1.0 - (margin / 10.0))  # softer gradient

    r = int(base[0] * intensity)
    g = int(base[1] * intensity)
    b = int(base[2] * intensity)

    return f"#{r:02x}{g:02x}{b:02x}"


def get_barrier_from_table_item(app, item_id: str) -> tuple[Optional[Room], Optional[Barrier], Optional[int]]:
    room = app.get_room_by_name(app.barriers_room_var.get())
    if not room or not hasattr(app, "barrier_table"):
        return None, None, None

    vals = app.barrier_table.item(item_id, "values")
    if not vals:
        return room, None, None

    try:
        name_idx = app.BARRIER_COLUMNS.index("name")
        barrier_name = str(vals[name_idx]).strip()
    except Exception:
        return room, None, None

    matches = []
    for idx, barrier in enumerate(room.barriers):
        if str(barrier.name).strip() == barrier_name:
            matches.append((idx, barrier))

    if len(matches) == 1:
        idx, barrier = matches[0]
        return room, barrier, idx

    # Fallback: disambiguate duplicate names by visible table row order
    try:
        row_index = app.barrier_table.index(item_id)
        if 0 <= row_index < len(matches):
            idx, barrier = matches[row_index]
            return room, barrier, idx
    except Exception:
        pass

    return room, None, None


def barrier_visual_score(app, barrier_name: str, live: Dict[str, Any]) -> tuple[int, float, float]:
    """
    Lower score = higher risk.

    Returns:
        (risk_bucket, confidence, margin_mm)

    risk_bucket:
        0 = FAIL
        1 = REVIEW
        2 = PASS
    """
    confidence = app._row_confidence_from_live(barrier_name, live)

    try:
        margin_mm = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin_mm = 0.0

    risk, _ = classify_barrier_visual_state(
        app,
        live=live,
        confidence=confidence,
        severities=set(),
        mismatch_flag=False,
    )

    if risk == "FAIL":
        bucket = 0
    elif risk == "REVIEW":
        bucket = 1
    else:
        bucket = 2

    return bucket, confidence, margin_mm



def on_barrier_risk_row_select(app, event=None):
    if not hasattr(app, "barrier_risk_table") or not hasattr(app, "barrier_table"):
        return

    selection = app.barrier_risk_table.selection()
    if not selection:
        return

    item_id = selection[0]
    values = app.barrier_risk_table.item(item_id, "values")
    if not values:
        return

    barrier_name = str(values[0]).strip()

    target_item = None
    for item in app.barrier_table.get_children():
        vals = app.barrier_table.item(item, "values")
        if not vals:
            continue
        try:
            name_idx = app.BARRIER_COLUMNS.index("name")
            if str(vals[name_idx]).strip() == barrier_name:
                target_item = item
                break
        except Exception:
            pass

    if target_item:
        try:
            app.barrier_table.focus(target_item)
            app.barrier_table.see(target_item)
            flash_barrier_row(app, target_item)
        except Exception:
            pass


def sort_barriers_by_risk(app):
    room = app.get_room_by_name(app.barriers_room_var.get())
    if not room:
        return

    try:
        app._apply_geometry_to_selected_room_barriers(room)

        room_results = app.get_room_barrier_results(room)

        if not room_results and room.barriers:
            room_results = [get_barrier_live_result(app, room, b) for b in room.barriers]

    except Exception as e:
        app.set_status(f"Barrier schedule unavailable: {e}")
        return

    paired = list(zip(room.barriers, room_results))

    def sort_key(item):
        barrier, live = item
        bucket, confidence, margin_mm = barrier_visual_score(app, barrier.name, live)
        return (
            bucket,
            confidence,
            margin_mm,
            str(barrier.name).lower(),
        )

    paired.sort(key=sort_key)
    room.barriers = [barrier for barrier, _ in paired]

    safe_refresh_barrier_schedule(app)
    app.set_status(f"Sorted barriers in {room.name} by visual risk.")



def flash_barrier_row(app, item_id: str, flashes: int = 3):
    if not hasattr(app, "barrier_table"):
        return

    table = app.barrier_table

    try:
        original_selection = tuple(table.selection())
        original_focus = table.focus()
    except Exception:
        return

    timings = [120, 120, 160, 200, 260, 320]

    def step(idx: int, on: bool):
        if not hasattr(app, "barrier_table"):
            return

        try:
            exists = item_id in table.get_children()
        except Exception:
            exists = False
        if not exists:
            return

        try:
            if on:
                table.selection_set(item_id)
                table.focus(item_id)
                app.center_row(table, item_id)
            else:
                table.selection_remove(item_id)
        except Exception:
            return

        if idx >= len(timings):
            try:
                table.selection_remove(item_id)
                if original_selection:
                    table.selection_set(original_selection)
                if original_focus:
                    table.focus(original_focus)
            except Exception:
                pass
            return

        app.after(timings[idx], lambda: step(idx + 1, not on))

    try:
        current = table.selection()
        if current:
            table.selection_remove(current)
    except Exception:
        pass

    step(0, True)



def derive_primary_barrier_issue(
    app,
    barrier: Barrier,
    live: Dict[str, Any],
    barrier_issues: list[Dict[str, Any]],
) -> str:
    titles = [str(i.get("title", "")).strip() for i in barrier_issues if str(i.get("title", "")).strip()]
    severities = [str(i.get("severity", "")).strip().lower() for i in barrier_issues]

    margin_mm = app._safe_float(live.get("margin_mm"), 0.0)
    required_mm = app._safe_float(live.get("required_thickness_mm"), 0.0)
    actual_mm = app._safe_float(getattr(barrier, "thickness_mm", 0.0), 0.0)
    status = str(live.get("compliance_status", "")).strip().upper()

    # issue takes precedence if it is explicit and meaningful
    for title in titles:
        lower = title.lower()
        if "mismatch" in lower:
            return title
        if "source" in lower or "occupancy" in lower or "dose" in lower:
            return title

    # Physics-driven interpretation
    if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin_mm < 0:
        if required_mm > 0:
            deficit = abs(margin_mm)
            return f"Actual thickness below required thickness by {deficit:.3f} mm"
        return "Barrier fails current requirement"

    if status in {"REVIEW", "WARN", "WARNING"}:
        if required_mm > 0 and actual_mm > 0:
            return "Borderline barrier - review thickness and assumptions"
        return "Review recommended"

    if required_mm > 0 and actual_mm >= required_mm:
        surplus = actual_mm - required_mm
        return f"Meets required thickness (+{surplus:.3f} mm margin)"

    if titles:
        return titles[0]

    return "No major issue detected"


def on_barrier_table_motion(app, event):
    if not hasattr(app, "barrier_table"):
        return

    region = app.barrier_table.identify("region", event.x, event.y)
    if region != "cell":
        return

    row_id = app.barrier_table.identify_row(event.y)
    col_id = app.barrier_table.identify_column(event.x)

    if not row_id or not col_id:
        return

    col_index = int(col_id.replace("#", "")) - 1
    if col_index < 0 or col_index >= len(app.BARRIER_COLUMNS):
        return

    column_name = app.BARRIER_COLUMNS[col_index]
    if column_name != "compliance_status":
        return

    values = app.barrier_table.item(row_id, "values")
    if not values:
        return

    status_idx = app.BARRIER_COLUMNS.index("compliance_status")
    status = str(values[status_idx]).strip().upper()

    if status in {"FAIL", "ERROR", "NON-COMPLIANT"}:
        app.set_status("FAIL = barrier does not currently meet the required thickness / compliance outcome.")
    elif status in {"REVIEW", "WARN", "WARNING"}:
        app.set_status("REVIEW = barrier is borderline or QA found a review-worthy issue.")
    elif status == "PASS":
        app.set_status("PASS = barrier currently meets the required thickness / compliance outcome.")


def on_barrier_table_leave(app, event):
    """Clear barrier-table hover status when the mouse leaves the table."""
    try:
        app.set_status("")
    except Exception:
        pass


def classify_barrier_visual_state(
    app,
    live: Dict[str, Any],
    confidence: float,
    severities: Optional[set[str]] = None,
    mismatch_flag: bool = False,
) -> tuple[str, str]:
    severities = severities or set()

    live_status = str(live.get("compliance_status", "")).strip().upper()
    try:
        margin_mm = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin_mm = 0.0

    # Unified visual logic for BOTH tables
    if (
        live_status in {"FAIL", "ERROR", "NON-COMPLIANT"}
        or margin_mm < 0
        or "critical" in severities
        or confidence < 0.75
    ):
        return "FAIL", "qa_fail"

    if (
        live_status in {"REVIEW", "WARN", "WARNING"}
        or "warning" in severities
        or mismatch_flag
        or margin_mm < 0.5
        or confidence < 0.90
    ):
        return "REVIEW", "qa_review"

    return "PASS", "qa_pass"
