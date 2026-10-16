"""Canonical execution/replay helpers for saved SPECT calculation requests."""
from __future__ import annotations

import json
from pathlib import Path

from engine.spect_calculation_request_contract import (
    SpectCalculationRequestError,
    load_and_replay_spect_calculation_request,
    spect_calculation_request_from_dict,
    spect_calculation_request_to_dict,
)


class SpectCalculationRequestCliError(ValueError):
    """Raised when a saved SPECT request cannot be validated or replayed."""


def _load(path):
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SpectCalculationRequestCliError(f"Unable to read SPECT request {p}: {exc}") from exc
    try:
        request = spect_calculation_request_from_dict(raw)
        canonical = spect_calculation_request_to_dict(request)
    except SpectCalculationRequestError as exc:
        raise SpectCalculationRequestCliError(str(exc)) from exc
    if raw != canonical:
        raise SpectCalculationRequestCliError("SPECT calculation request is not canonical.")
    return p, request


def render_request_validation(path) -> str:
    p, request = _load(path)
    return (
        "SPECT CALCULATION REQUEST VALIDATION\n"
        "====================================\n"
        f"Source path: {p}\n"
        f"Barriers: {len(request.barrier_requests)}\n"
        "Status: VALID\n"
        "Production eligible: no"
    )


def run_request_file(path):
    p, _ = _load(path)
    try:
        result = load_and_replay_spect_calculation_request(p)
    except SpectCalculationRequestError as exc:
        raise SpectCalculationRequestCliError(str(exc)) from exc
    return result, (
        "SPECT CALCULATION REQUEST RUN\n"
        "=============================\n"
        f"Source path: {p}\n"
        "Replay verified: yes\n"
        "Production eligible: no"
    )


def replay_request_file(path):
    first, _ = run_request_file(path)
    second, _ = run_request_file(path)
    if first.payload != second.payload:
        raise SpectCalculationRequestCliError("SPECT replay was not deterministic.")
    return first, (
        "SPECT CALCULATION REQUEST REPLAY\n"
        "================================\n"
        "Deterministic replay: VERIFIED\n"
        "Production eligible: no"
    )
