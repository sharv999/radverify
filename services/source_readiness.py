from __future__ import annotations

"""
Canonical source-readiness / preflight validation.

This service is UI-independent. It answers one question consistently:

    Is the project source state ready for calculation/report generation?

It does not repair source inventory. Callers should run their source-inventory
repair/sync path before calling this validator.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from modalities.registry import (
    expected_source_types_for_modality,
    source_readiness_label,
    source_readiness_result_for_source,
)




PET_WORKING_STATE_OUTPUT_BLOCK_REASON = (
    "PET working state is enabled for gated calculation and in-app Results, but issued PDF, "
    "machine export, certification, and signatures remain disabled."
)
# Backward-compatible import name retained for older callers/tests. Its meaning is
# now output-only rather than a calculation/readiness blocker.
PET_WORKING_STATE_BLOCK_REASON = PET_WORKING_STATE_OUTPUT_BLOCK_REASON


def room_has_persisted_pet_working_state(room: Any) -> bool:
    """Return True when the room carries any persisted PET working-state envelope.

    Presence alone is sufficient to block normal production output. The payload is
    intentionally not parsed here: malformed PET working state must fail closed just
    as valid preview state does.
    """
    modality_state = getattr(room, "modality_state", {}) or {}
    if not isinstance(modality_state, dict):
        return False
    return "pet_single_source" in modality_state


def pet_working_state_blocking_reason(room: Any) -> str:
    """Legacy compatibility helper: persisted PET state no longer blocks calculation."""
    return ""


def pet_working_state_output_blocking_reason(room: Any) -> str:
    return PET_WORKING_STATE_OUTPUT_BLOCK_REASON if room_has_persisted_pet_working_state(room) else ""


@dataclass
class SourceReadinessResult:
    overall_status: str = "PASS"
    blocking: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    room_results: List[Dict[str, Any]] = field(default_factory=list)
    source_results: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "blocking": self.blocking,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "room_results": list(self.room_results),
            "source_results": list(self.source_results),
        }


def validate_project_source_readiness(
    project: Any,
    *,
    get_sources_for_room=None,
) -> Dict[str, Any]:
    result = SourceReadinessResult()

    rooms = list(getattr(project, "rooms", []) or [])
    if not rooms:
        result.overall_status = "FAIL"
        result.blocking = True
        result.errors.append("Project has no rooms.")
        return result.as_dict()

    for room in rooms:
        room_result = validate_room_source_readiness(
            room,
            get_sources_for_room=get_sources_for_room,
        )
        result.room_results.append(room_result)
        result.errors.extend(room_result.get("errors", []) or [])
        result.warnings.extend(room_result.get("warnings", []) or [])
        result.source_results.extend(room_result.get("source_results", []) or [])

    result.overall_status = _overall_status(result.errors, result.warnings)
    result.blocking = bool(result.errors)
    return result.as_dict()


def validate_room_source_readiness(
    room: Any,
    *,
    get_sources_for_room=None,
) -> Dict[str, Any]:
    room_name = str(getattr(room, "name", "") or "").strip()
    modality = str(getattr(room, "modality", "") or "").strip() or "CT"

    try:
        sources = (
            list(get_sources_for_room(room_name))
            if get_sources_for_room is not None
            else list(getattr(room, "sources", []) or [])
        )
    except Exception:
        sources = list(getattr(room, "sources", []) or [])

    errors: List[str] = []
    warnings: List[str] = []
    source_results: List[Dict[str, Any]] = []
    checks: List[Dict[str, str]] = []

    pet_output_reason = pet_working_state_output_blocking_reason(room)
    if pet_output_reason:
        qualified = f"{room_name}: {pet_output_reason}" if room_name else pet_output_reason
        warnings.append(qualified)
        _add_check(
            checks,
            "PET working-state production host",
            "REVIEW",
            pet_output_reason,
        )

    expected = set(expected_source_types_for_modality(modality))
    actual_types = {
        str(getattr(src, "source_type", "") or "").strip()
        for src in sources
    }

    if sources:
        _add_check(checks, "Room source inventory", "PASS", f"{len(sources)} source(s) configured.")
    else:
        msg = "Room has no sources."
        errors.append(f"{room_name}: {msg}")
        _add_check(checks, "Room source inventory", "FAIL", msg)

    if expected:
        missing = sorted(expected - actual_types)
        unexpected = sorted(actual_types - expected)

        if missing:
            msg = f"Missing required source type(s): {', '.join(missing)}."
            errors.append(f"{room_name}: {msg}")
            _add_check(checks, "Required source types", "FAIL", msg)
        else:
            _add_check(
                checks,
                "Required source types",
                "PASS",
                ", ".join(sorted(expected)) if expected else "No locked source type.",
            )

        if unexpected:
            msg = f"Unexpected source type(s): {', '.join(unexpected)}."
            warnings.append(f"{room_name}: {msg}")
            _add_check(checks, "Unexpected source types", "REVIEW", msg)

    for src in sources:
        source_result = validate_source_readiness(src, room=room)
        source_results.append(source_result)

        source_errors = list(source_result.get("errors", []) or [])
        source_warnings = list(source_result.get("warnings", []) or [])
        errors.extend(source_errors)
        warnings.extend(source_warnings)

        # Fail closed when a modality-owned validator declares a blocking
        # source but omits an explicit errors list.  Step 22 closes the SPECT
        # audit gap and also prevents the same aggregation mistake recurring
        # for a future modality.
        source_status = str(
            source_result.get("overall_status", source_result.get("status", "")) or ""
        ).strip().upper()
        source_blocking = bool(source_result.get("blocking", False)) or source_status in {
            "BLOCKED",
            "FAIL",
            "ERROR",
        }
        if source_blocking and not source_errors:
            reason = str(
                source_result.get("message", "")
                or "Source is blocked by its modality readiness contract."
            ).strip()
            qualified = f"{room_name}: {reason}" if room_name and not reason.startswith(f"{room_name}:") else reason
            errors.append(qualified)

    if pet_output_reason and not any(bool(item.get("output_blocking", False)) for item in source_results):
        source_results.append({
            "source_type": "persisted_pet_working_state",
            "source_name": "Persisted PET working state",
            "room_name": room_name,
            "overall_status": "REVIEW",
            "status": "REVIEW",
            "blocking": False,
            "output_blocking": True,
            "basis": "production_host_results_only",
            "message": pet_output_reason,
            "checks": [],
            "errors": [],
            "warnings": [qualified if room_name else pet_output_reason],
        })

    status = _overall_status(errors, warnings)
    return {
        "overall_status": status,
        "status": status,
        "blocking": bool(errors),
        "room_name": room_name,
        "room_modality": modality,
        "source_count": len(sources),
        "expected_source_types": sorted(expected),
        "actual_source_types": sorted(actual_types),
        "message": f"{len(sources)} source(s) configured." if sources else "Room has no sources.",
        "checks": checks,
        "source_results": source_results,
        "errors": errors,
        "warnings": warnings,
    }


def validate_source_readiness(src: Any, *, room: Any | None = None) -> Dict[str, Any]:
    source_type = str(getattr(src, "source_type", "") or "").strip()
    source_name = str(getattr(src, "name", "") or "").strip()
    room_name = str(getattr(room, "name", "") or getattr(src, "room_name", "") or "").strip()
    modality = str(getattr(room, "modality", "") or "").strip()
    params = dict(getattr(src, "params", {}) or {})

    context = {
        "room_name": room_name,
        "room_modality": modality,
        "source_name": source_name,
        "radiation_type": str(getattr(src, "radiation_type", "") or params.get("tvl_key", "") or "").strip(),
    }
    modality_result = source_readiness_result_for_source(source_type, params, context)
    if modality_result is not None:
        return modality_result

    checks: List[Dict[str, str]] = []
    _add_check(checks, source_readiness_label(source_type, "source_type", "Source type"), "PASS", source_type or "non-CT source")
    status = "PASS"
    return {
        "overall_status": status,
        "status": status,
        "blocking": False,
        "room_name": room_name,
        "room_modality": modality,
        "source_name": source_name,
        "source_type": source_type,
        "message": "Source ready.",
        "checks": checks,
        "errors": [],
        "warnings": [],
        "basis": "not_applicable",
    }

def source_readiness_summary_lines(readiness: Dict[str, Any]) -> List[str]:
    if not readiness:
        return ["Source readiness unavailable."]

    lines: List[str] = [f"Overall: {readiness.get('overall_status', 'UNKNOWN')}"]

    for room in readiness.get("room_results", []) or []:
        room_name = room.get("room_name", "") or "Unknown room"
        status = room.get("overall_status", room.get("status", "UNKNOWN"))
        lines.append(f"{_status_icon(status)} {room_name}: {status} — {room.get('message', '')}")

        for check in room.get("checks", []) or []:
            lines.append(_format_check_line(check))

        for source in room.get("source_results", []) or []:
            source_name = source.get("source_name", "") or source.get("source_type", "Source")
            source_status = source.get("overall_status", source.get("status", "UNKNOWN"))
            lines.append(f"{_status_icon(source_status)} {source_name}: {source_status}")

            for check in source.get("checks", []) or []:
                lines.append(_format_check_line(check, indent="    "))

    return lines


def _format_check_line(check: Dict[str, Any], *, indent: str = "  ") -> str:
    status = str(check.get("status", "") or "")
    detail = str(check.get("detail", "") or "").strip()
    suffix = f": {detail}" if detail else ""
    return f"{indent}{_status_icon(status)} {check.get('name', 'Check')}{suffix}"


def _add_check(checks: List[Dict[str, str]], name: str, status: str, detail: str = "") -> None:
    checks.append({
        "name": str(name),
        "status": str(status),
        "detail": str(detail or ""),
    })


def _overall_status(errors: List[str], warnings: List[str]) -> str:
    if errors:
        return "FAIL"
    if warnings:
        return "REVIEW"
    return "PASS"


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower().endswith("kvp"):
            text = text[:-3].strip()
        return float(text)
    except Exception:
        return None


def _status_icon(status: str) -> str:
    status = str(status or "").upper()
    if status in {"FAIL", "ERROR"}:
        return "❌"
    if status in {"REVIEW", "WARN", "WARNING"}:
        return "⚠️"
    if status == "INFO":
        return "ℹ️"
    return "✅"
