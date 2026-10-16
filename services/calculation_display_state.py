"""Live calculation display gating derived from canonical source readiness.

This module keeps UI surfaces from presenting stale barrier calculations after a
source becomes calculation-blocked.  It does not cache results; every query is
resolved from the current room/source model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.source_readiness import validate_room_source_readiness


@dataclass(frozen=True)
class CalculationDisplayState:
    blocking: bool
    message: str = ""
    readiness: dict[str, Any] | None = None


def _blocking_message(readiness: dict[str, Any]) -> str:
    issues = [str(value).strip() for value in readiness.get("errors", []) or [] if str(value).strip()]
    combined = " ".join(issues).lower()

    if "ksec" in combined and ("manual override" in combined or "null" in combined or "missing" in combined):
        return (
            "Calculation blocked — CT scanner ksec is unavailable. "
            "Enter and document a manual ksec override in the Sources tab."
        )

    if issues:
        return f"Calculation blocked — {issues[0]}"

    return "Calculation blocked — source inputs are incomplete."


def room_calculation_display_state(app: Any, room: Any) -> CalculationDisplayState:
    if room is None:
        return CalculationDisplayState(blocking=True, message="Calculation blocked — no room selected.")

    source_getter = getattr(app, "get_sources_for_room", None)
    if not callable(source_getter) and not hasattr(room, "sources"):
        # Lightweight presentation helpers/tests may not expose project source
        # inventory. In that case there is no canonical readiness state to gate.
        return CalculationDisplayState(blocking=False)

    try:
        readiness = validate_room_source_readiness(
            room,
            get_sources_for_room=source_getter if callable(source_getter) else None,
        )
    except Exception as exc:
        return CalculationDisplayState(
            blocking=True,
            message=f"Calculation blocked — source readiness could not be evaluated: {exc}",
        )

    blocking = bool(readiness.get("blocking", False))
    if not blocking and str(getattr(room, "modality", "") or "").strip().upper() == "X-RAY":
        getter = getattr(app, "get_room_results_model", None)
        if callable(getter):
            try:
                from services.xray_results_model import xray_results_issueable
                rows = list(getter(room) or [])
                if not xray_results_issueable(rows):
                    blocking = True
                    readiness = dict(readiness)
                    readiness["errors"] = [
                        "General X-ray project barriers are not fully qualified through the XR-08E project-specific NCRP 147 Section 5.3 / Figure 5.2 model."
                    ]
            except Exception as exc:
                blocking = True
                readiness = dict(readiness)
                readiness["errors"] = [f"General X-ray canonical Results unavailable: {exc}"]
    return CalculationDisplayState(
        blocking=blocking,
        message=_blocking_message(readiness) if blocking else "",
        readiness=readiness,
    )
