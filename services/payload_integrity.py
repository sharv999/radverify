from __future__ import annotations

"""
Canonical report-payload calculation integrity guard.

MVP risk protected:
    Prevent a PDF/CSV payload from looking complete when the room calculation
    failed, returned fewer wall results than expected, or omitted Geometry
    openings/sub-barriers from the exported payload.

This module is intentionally payload-shaped and UI-free. It inspects the
canonical report payload after results_payload_builder has assembled the room
and barrier rows.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List


ROOM_CALCULATION_FAILED_REASON = "BLOCKED: one or more room barrier calculations failed."
BARRIER_RESULT_COUNT_MISMATCH_REASON = "BLOCKED: barrier result count does not match the room barrier schedule."
OPENING_EXPORT_OMISSION_REASON = "BLOCKED: one or more Geometry openings are missing from the report payload."
XRAY_FIG52_RELEASE_REASON = "BLOCKED: General X-ray issued output requires the fully requalified NCRP 147 Section 5.3 / Figure 5.2 project-specific model."


@dataclass(frozen=True)
class PayloadCalculationIntegrity:
    calculation_complete: bool
    room_count: int = 0
    barrier_count_exported: int = 0
    wall_count_expected: int = 0
    wall_result_count: int = 0
    opening_count_expected: int = 0
    opening_count_exported: int = 0
    blocking_reasons: List[str] = field(default_factory=list)
    room_issues: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return bool(self.blocking_reasons)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["blocking"] = self.blocking
        return data


def build_payload_calculation_integrity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a serialisable integrity summary for the canonical report payload.

    Expected optional per-room metadata, populated by results_payload_builder:
      * wall_count_expected
      * wall_result_count
      * opening_count_expected
      * opening_count_exported
      * error
    """
    rooms = list(payload.get("rooms", []) or [])
    room_issues: List[Dict[str, Any]] = []
    reasons: List[str] = []

    total_barriers = 0
    wall_expected_total = 0
    wall_result_total = 0
    opening_expected_total = 0
    opening_exported_total = 0
    hard_output_block = False

    for room in rooms:
        if not isinstance(room, dict):
            continue

        room_name = str(room.get("name", "") or "")
        barriers = list(room.get("barriers", []) or [])
        total_barriers += len(barriers)

        wall_expected = _int_or_zero(room.get("wall_count_expected"))
        wall_results = _int_or_zero(room.get("wall_result_count"))
        opening_expected = _int_or_zero(room.get("opening_count_expected"))
        opening_exported = _int_or_zero(room.get("opening_count_exported"))

        # Backwards-compatible fallback when metadata is absent.
        if "wall_count_expected" not in room:
            wall_expected = _count_barriers_by_element(barriers, "wall")
        if "wall_result_count" not in room:
            wall_results = wall_expected
        if "opening_count_exported" not in room:
            opening_exported = _count_opening_rows(barriers)

        wall_expected_total += wall_expected
        wall_result_total += wall_results
        opening_expected_total += opening_expected
        opening_exported_total += opening_exported

        room_error = str(room.get("error", "") or "").strip()
        if room_error:
            reasons.append(ROOM_CALCULATION_FAILED_REASON)
            room_issues.append({
                "room_name": room_name,
                "issue": "room_calculation_failed",
                "detail": room_error,
            })

        if wall_results != wall_expected:
            reasons.append(BARRIER_RESULT_COUNT_MISMATCH_REASON)
            room_issues.append({
                "room_name": room_name,
                "issue": "wall_result_count_mismatch",
                "expected": wall_expected,
                "actual": wall_results,
            })

        if opening_exported < opening_expected:
            reasons.append(OPENING_EXPORT_OMISSION_REASON)
            room_issues.append({
                "room_name": room_name,
                "issue": "opening_export_omission",
                "expected": opening_expected,
                "actual": opening_exported,
            })

        if str(room.get("modality", "") or "").strip().upper() == "X-RAY":
            qualification = room.get("xray_report_qualification") or {}
            if not (
                qualification.get("project_specific_geometry") is True
                and qualification.get("issued_output_enabled") is True
                and qualification.get("fig52_requalification_version") in {
                    "xr08e-issueable-project-fig52-v1",
                    "xr15d-issueable-control-wall-v1",
                    "xr17d-issueable-intervening-control-wall-v1",
                }
            ):
                hard_output_block = True
                reasons.append(XRAY_FIG52_RELEASE_REASON)
                room_issues.append({
                    "room_name": room_name,
                    "issue": "xray_fig52_release_gate",
                    "detail": XRAY_FIG52_RELEASE_REASON,
                })

    integrity = PayloadCalculationIntegrity(
        calculation_complete=not bool(room_issues),
        room_count=len(rooms),
        barrier_count_exported=total_barriers,
        wall_count_expected=wall_expected_total,
        wall_result_count=wall_result_total,
        opening_count_expected=opening_expected_total,
        opening_count_exported=opening_exported_total,
        blocking_reasons=_unique_texts(reasons),
        room_issues=room_issues,
    )
    data = integrity.to_dict()
    data["output_blocking"] = hard_output_block
    return data


def _count_opening_rows(barriers: Iterable[Dict[str, Any]]) -> int:
    return sum(
        1
        for barrier in barriers
        if str(barrier.get("barrier_element_type", "") or "").strip().lower()
        in {"door", "viewing_panel"}
    )


def _count_barriers_by_element(barriers: Iterable[Dict[str, Any]], element_type: str) -> int:
    target = str(element_type or "").strip().lower()
    return sum(
        1
        for barrier in barriers
        if str(barrier.get("barrier_element_type", "") or "").strip().lower() == target
    )


def _int_or_zero(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except Exception:
        return 0


def _unique_texts(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
