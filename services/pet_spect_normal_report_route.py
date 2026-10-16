"""Step 40 closed PET/SPECT route into the normal report payload builder.

This service is the only bridge between the normal report payload builder and
validated PET/SPECT production Results.  It does not calculate shielding and it
does not open issued output.  The Step 39 adapter remains non-issueable.
"""
from __future__ import annotations

from typing import Any, Mapping

from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.spect_source_summary_harness import build_non_issueable_spect_source_summary
from services.pet_spect_report_payload_adapter import (
    PetSpectReportPayloadAdapterError,
    build_non_issueable_pet_spect_report_payload,
)

PET_SPECT_NORMAL_REPORT_ROUTE_CONTRACT_VERSION = 1
PET_SPECT_NORMAL_REPORT_ROUTE_BASELINE = "pet-spect-normal-report-route-v1-non-issueable"
PET_SPECT_NORMAL_REPORT_ROUTE_ISSUEABLE = False
PET_SPECT_NORMAL_REPORT_ROUTE_EXPORT_ENABLED = False
PET_SPECT_NORMAL_REPORT_ROUTE_CERTIFICATION_ENABLED = False
PET_SPECT_NORMAL_REPORT_OUTPUT_BLOCK_REASON = (
    "PET/SPECT Step 40 normal report payload is validated but remains non-issueable; "
    "normal PDF, machine export, certification and signatures are disabled."
)

_SUPPORTED_MODALITIES = frozenset({"PET", "SPECT"})
_SOURCE_BUILDERS = {
    "PET": build_non_issueable_pet_source_summary,
    "SPECT": build_non_issueable_spect_source_summary,
}


class PetSpectNormalReportRouteError(ValueError):
    """Raised when the normal report builder cannot safely consume PET/SPECT Results."""


def is_pet_spect_report_modality(modality: object) -> bool:
    return str(modality or "").strip().upper() in _SUPPORTED_MODALITIES


def build_non_issueable_pet_spect_room_report_payload(app: Any, room: Any) -> dict[str, Any] | None:
    """Return the Step 39 payload for a PET/SPECT room, otherwise ``None``.

    The caller must not fall back to generic calculation when this function is
    applicable.  Openings are deliberately rejected until they have their own
    validated PET/SPECT Results contract.
    """
    modality = str(getattr(room, "modality", "") or "").strip().upper()
    if modality not in _SUPPORTED_MODALITIES:
        return None

    geometry = getattr(room, "geometry", None)
    openings = list(getattr(geometry, "openings", ()) or ()) if geometry is not None else []
    if openings:
        raise PetSpectNormalReportRouteError(
            f"{modality} normal report payload cannot include openings until a validated modality Results contract exists for openings."
        )

    try:
        result_rows = list(app.get_room_results_model(room) or [])
    except Exception as exc:
        raise PetSpectNormalReportRouteError(
            f"{modality} canonical Results are unavailable: {exc}"
        ) from exc

    barriers = list(getattr(room, "barriers", ()) or ())
    if not result_rows:
        raise PetSpectNormalReportRouteError(
            f"{modality} normal report payload requires canonical production Results."
        )
    if len(result_rows) != len(barriers):
        raise PetSpectNormalReportRouteError(
            f"{modality} Results/barrier count mismatch: {len(result_rows)} result row(s) for {len(barriers)} barrier(s)."
        )

    source_builder = _SOURCE_BUILDERS[modality]
    try:
        source_payload = source_builder(room)
        adapted = build_non_issueable_pet_spect_report_payload(
            modality=modality,
            source_payload=source_payload,
            result_rows=result_rows,
        )
    except Exception as exc:
        if isinstance(exc, PetSpectNormalReportRouteError):
            raise
        raise PetSpectNormalReportRouteError(
            f"{modality} Step 39 report-payload adaptation failed: {exc}"
        ) from exc

    if adapted.get("non_issueable") is not True or adapted.get("issueable") is not False:
        raise PetSpectNormalReportRouteError(
            f"{modality} report-payload adapter crossed the non-issueable boundary."
        )
    if any(
        adapted.get(field) is not False
        for field in ("report_integration_open", "machine_export_enabled", "certification_enabled", "signature_enabled")
    ):
        raise PetSpectNormalReportRouteError(
            f"{modality} report-payload adapter exposes a closed output surface."
        )

    adapted_names = [str(item.get("barrier_name", "") or "") for item in adapted.get("barriers", [])]
    room_names = [str(getattr(barrier, "name", "") or "") for barrier in barriers]
    if adapted_names != room_names:
        raise PetSpectNormalReportRouteError(
            f"{modality} adapted Results ordering does not match the room barrier schedule."
        )

    return {
        "route_contract_version": PET_SPECT_NORMAL_REPORT_ROUTE_CONTRACT_VERSION,
        "route_baseline": PET_SPECT_NORMAL_REPORT_ROUTE_BASELINE,
        "modality": modality,
        "room_name": str(getattr(room, "name", "") or ""),
        "non_issueable": True,
        "issueable": PET_SPECT_NORMAL_REPORT_ROUTE_ISSUEABLE,
        "machine_export_enabled": PET_SPECT_NORMAL_REPORT_ROUTE_EXPORT_ENABLED,
        "certification_enabled": PET_SPECT_NORMAL_REPORT_ROUTE_CERTIFICATION_ENABLED,
        "payload": adapted,
    }


def canonical_result_rows_from_room_report_payload(route_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract already-audited canonical result rows; never calculate or fallback."""
    if not isinstance(route_payload, Mapping) or route_payload.get("non_issueable") is not True:
        raise PetSpectNormalReportRouteError("Closed PET/SPECT room report route payload is required.")
    payload = route_payload.get("payload")
    if not isinstance(payload, Mapping) or payload.get("non_issueable") is not True:
        raise PetSpectNormalReportRouteError("Closed Step 39 report payload is required.")
    barriers = payload.get("barriers")
    if not isinstance(barriers, list) or not barriers:
        raise PetSpectNormalReportRouteError("Step 39 report payload contains no barrier rows.")
    rows: list[dict[str, Any]] = []
    for index, barrier in enumerate(barriers):
        if not isinstance(barrier, Mapping):
            raise PetSpectNormalReportRouteError(f"Adapted barrier {index} is not a mapping.")
        result_payload = barrier.get("result_payload")
        if not isinstance(result_payload, Mapping):
            raise PetSpectNormalReportRouteError(f"Adapted barrier {index} has no canonical result_payload.")
        rows.append(dict(result_payload))
    return rows


def apply_pet_spect_normal_report_output_block(
    preflight: Mapping[str, Any],
    route_payloads: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Attach a hard normal-output blocker whenever Step 40 room payloads exist."""
    merged = dict(preflight or {})
    if not route_payloads:
        return merged
    source_results = list(merged.get("source_results", []) or [])
    existing = {
        (str(item.get("room_name", "") or ""), str(item.get("message", "") or ""))
        for item in source_results
        if isinstance(item, Mapping)
    }
    for route in route_payloads:
        room_name = str(route.get("room_name", "") or "")
        key = (room_name, PET_SPECT_NORMAL_REPORT_OUTPUT_BLOCK_REASON)
        if key in existing:
            continue
        source_results.append({
            "room_name": room_name,
            "source_type": f"{str(route.get('modality', '') or '').lower()}_step40_report_route",
            "status": "REVIEW",
            "blocking": False,
            "output_blocking": True,
            "message": PET_SPECT_NORMAL_REPORT_OUTPUT_BLOCK_REASON,
        })
    merged["source_results"] = source_results
    return merged
