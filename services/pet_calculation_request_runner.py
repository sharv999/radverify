"""Validate, run, and replay non-production PET calculation request files.

Usage from the project root::

    python -m tools.pet_calculation_request_cli validate request.json
    python -m tools.pet_calculation_request_cli run request.json --output result.json
    python -m tools.pet_calculation_request_cli replay request.json

This CLI is intentionally isolated from the Tk UI, production working-project
serializer, shielding dispatch, and report pipeline.  It only consumes the
versioned non-production PET calculation-request contract and invokes the
isolated PET calculation service.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from serialization.pet_calculation_request_contract import (
    PET_CALCULATION_REQUEST_SCHEMA,
    PET_CALCULATION_REQUEST_VERSION,
    PetCalculationRequestEnvelope,
    PetCalculationRequestSerializationError,
    load_and_replay_pet_calculation_request,
    pet_calculation_request_from_dict,
    pet_calculation_request_to_dict,
    replay_pet_calculation_request,
)
from services.pet_calculation_service import PetCalculationServiceResult


class PetCalculationRequestCliError(ValueError):
    """Raised when a PET request CLI operation cannot be completed."""


def _read_json_object(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PetCalculationRequestCliError(
            f"Unable to read PET calculation request {source_path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PetCalculationRequestCliError(
            f"PET calculation request {source_path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PetCalculationRequestCliError(
            "PET calculation request JSON root must be an object."
        )
    return payload


def _validated_request(path: str | Path) -> tuple[Path, PetCalculationRequestEnvelope, dict[str, Any]]:
    source_path = Path(path)
    payload = _read_json_object(source_path)
    try:
        request = pet_calculation_request_from_dict(payload)
        canonical = pet_calculation_request_to_dict(request)
    except PetCalculationRequestSerializationError as exc:
        raise PetCalculationRequestCliError(str(exc)) from exc
    if payload != canonical:
        raise PetCalculationRequestCliError(
            "PET calculation request is valid but not canonical; unexpected or altered fields are present."
        )
    return source_path, request, canonical


def render_request_validation(path: str | Path) -> str:
    """Validate a request file and render a concise audit summary."""

    source_path, request, _ = _validated_request(path)
    source = request.source
    lines = [
        "PET CALCULATION REQUEST VALIDATION",
        "=" * 34,
        f"Source path: {source_path}",
        f"Schema: {PET_CALCULATION_REQUEST_SCHEMA}",
        f"Schema version: {PET_CALCULATION_REQUEST_VERSION}",
        "Production eligible: no",
        f"Radionuclide: {source.radionuclide_spec.code}",
        f"Injected activity: {source.injected_activity_mbq:g} MBq",
        f"Patients per week: {source.patients_per_week:g}",
        f"Residual activity factor: {source.residual_activity_factor:g}",
        f"Exposure phases: {len(source.exposure_phases)}",
        f"Barrier requests: {len(request.barrier_requests)}",
        "Status: VALID",
    ]
    for index, barrier in enumerate(request.barrier_requests, start=1):
        lines.extend(
            [
                "",
                f"Barrier [{index}]",
                f"  Material: {barrier.material_key}",
                f"  Distance: {barrier.distance_m:g} m",
                f"  Occupancy: {barrier.occupancy_factor:g}",
                f"  Design goal: {barrier.design_goal_uSv_per_week:g} uSv/week",
                "  Provided thickness: "
                + (
                    "[not supplied]"
                    if barrier.provided_thickness_mm is None
                    else f"{barrier.provided_thickness_mm:g} mm"
                ),
            ]
        )
    return "\n".join(lines)


def _write_json_atomic(path: str | Path, payload: Mapping[str, Any], *, overwrite: bool) -> Path:
    output_path = Path(path).resolve()
    if output_path.exists() and not overwrite:
        raise PetCalculationRequestCliError(
            f"Output already exists: {output_path}. Use --overwrite explicitly to replace it."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def _render_run_summary(
    source_path: Path,
    result: PetCalculationServiceResult,
    *,
    heading: str,
    output_path: Path | None = None,
) -> str:
    lines = [
        heading,
        "=" * len(heading),
        f"Source path: {source_path}",
        f"Service contract: {result.contract_version}",
        f"Source type: {result.source_type}",
        f"Radionuclide: {result.snapshot.source.radionuclide_spec.code}",
        f"Weekly dose at 1 m: {result.snapshot.physics_result.weekly_dose_uSv_at_1m:.12g} uSv/week",
        f"Barrier results: {len(result.snapshot.barrier_results)}",
        f"Replay verified: {'yes' if result.replay_verified else 'no'}",
        "Production eligible: no",
    ]
    if output_path is not None:
        lines.append(f"Result snapshot written to: {output_path}")
    return "\n".join(lines)


def run_request_file(
    path: str | Path,
    *,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> tuple[PetCalculationServiceResult, str]:
    """Validate and execute one saved PET request file."""

    source_path, _, payload = _validated_request(path)
    try:
        result = replay_pet_calculation_request(payload)
    except PetCalculationRequestSerializationError as exc:
        raise PetCalculationRequestCliError(str(exc)) from exc
    output_path = None
    if output is not None:
        output_path = _write_json_atomic(output, result.payload, overwrite=overwrite)
    return result, _render_run_summary(
        source_path, result, heading="PET CALCULATION REQUEST RUN", output_path=output_path
    )


def replay_request_file(
    path: str | Path,
    *,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> tuple[PetCalculationServiceResult, str]:
    """Execute the saved request twice and prove deterministic replay."""

    source_path, _, _ = _validated_request(path)
    try:
        first = load_and_replay_pet_calculation_request(source_path)
        second = load_and_replay_pet_calculation_request(source_path)
    except PetCalculationRequestSerializationError as exc:
        raise PetCalculationRequestCliError(str(exc)) from exc
    if first.snapshot != second.snapshot or first.payload != second.payload:
        raise PetCalculationRequestCliError(
            "PET calculation request replay was not deterministic."
        )
    output_path = None
    if output is not None:
        output_path = _write_json_atomic(output, first.payload, overwrite=overwrite)
    summary = _render_run_summary(
        source_path,
        first,
        heading="PET CALCULATION REQUEST REPLAY",
        output_path=output_path,
    )
    summary += "\nDeterministic replay: VERIFIED"
    return first, summary
