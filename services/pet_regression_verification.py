"""Run the curated non-production PET CLI regression manifest.

Usage from the project root::

    python -m tools.pet_cli_regression \
        tests/fixtures/pet_requests/pet_cli_regression_manifest.json

The runner validates every approved request fixture, executes it through the
isolated PET calculation-request CLI boundary, verifies the expected
radionuclide/material sequence, compares the canonical result SHA-256 digest,
and confirms deterministic replay status.

It is intentionally disconnected from the Tk UI, production project
serializer, shielding dispatch, and report pipeline.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.pet_calculation_request_runner import (
    PetCalculationRequestCliError,
    replay_request_file,
    run_request_file,
)

PET_CLI_REGRESSION_MANIFEST_SCHEMA = "radshield_pet_cli_regression_manifest_v1"
PET_CLI_REGRESSION_MANIFEST_VERSION = 1


class PetCliRegressionError(ValueError):
    """Raised when a PET CLI regression manifest or run is invalid."""


@dataclass(frozen=True)
class PetCliRegressionEntry:
    fixture_id: str
    request_path: str
    expected_radionuclide: str
    expected_materials: tuple[str, ...]
    expected_output_sha256: str
    expected_replay_verified: bool


@dataclass(frozen=True)
class PetCliRegressionManifest:
    entries: tuple[PetCliRegressionEntry, ...]


@dataclass(frozen=True)
class PetCliRegressionCaseResult:
    fixture_id: str
    request_path: Path
    output_sha256: str
    replay_verified: bool


@dataclass(frozen=True)
class PetCliRegressionRunResult:
    manifest_path: Path
    cases: tuple[PetCliRegressionCaseResult, ...]

    @property
    def passed(self) -> bool:
        return True


PET_REGRESSION_FLOAT_DECIMAL_PLACES = 9


def _normalise_regression_value(value: Any) -> Any:
    """Return a platform-stable JSON value for PET regression hashing.

    PET calculations use ``exp``/``log10`` and can differ by a few final binary
    floating-point bits between operating systems and C runtime libraries.
    Quantising finite floats to nine decimal places preserves substantially more
    precision than the application displays while preventing false cross-platform
    digest failures. Booleans are handled before integers because ``bool`` is an
    ``int`` subclass.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PetCliRegressionError(
                "PET regression payload contains a non-finite floating-point value."
            )
        rounded = round(value, PET_REGRESSION_FLOAT_DECIMAL_PLACES)
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, Mapping):
        return {str(key): _normalise_regression_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_regression_value(item) for item in value]
    raise PetCliRegressionError(
        f"PET regression payload contains unsupported value type: {type(value).__name__}."
    )


def canonical_payload_sha256(payload: Mapping[str, Any]) -> str:
    """Return the cross-platform SHA-256 digest of a result payload.

    The digest is calculated from the complete payload after recursively
    quantising finite floats to ``PET_REGRESSION_FLOAT_DECIMAL_PLACES``.
    """

    normalised = _normalise_regression_value(payload)
    encoded = json.dumps(
        normalised,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PetCliRegressionError(f"Unable to read regression manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PetCliRegressionError(f"Regression manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PetCliRegressionError("PET CLI regression manifest root must be an object.")
    return payload


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PetCliRegressionError(f"{field} must be a non-blank string.")
    return value.strip()


def load_pet_cli_regression_manifest(path: str | Path) -> PetCliRegressionManifest:
    """Load and validate one canonical PET CLI regression manifest."""

    manifest_path = Path(path)
    payload = _read_json_object(manifest_path)
    expected_root_keys = {
        "schema",
        "schema_version",
        "production_eligible",
        "fixtures",
    }
    if set(payload) != expected_root_keys:
        raise PetCliRegressionError(
            "PET CLI regression manifest must contain exactly schema, schema_version, "
            "production_eligible, and fixtures."
        )
    if payload["schema"] != PET_CLI_REGRESSION_MANIFEST_SCHEMA:
        raise PetCliRegressionError("Unsupported PET CLI regression manifest schema.")
    if payload["schema_version"] != PET_CLI_REGRESSION_MANIFEST_VERSION:
        raise PetCliRegressionError("Unsupported PET CLI regression manifest version.")
    if payload["production_eligible"] is not False:
        raise PetCliRegressionError("PET CLI regression manifest must remain non-production.")

    raw_entries = payload["fixtures"]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise PetCliRegressionError("fixtures must be a non-empty list.")

    entries: list[PetCliRegressionEntry] = []
    fixture_ids: set[str] = set()
    request_paths: set[str] = set()
    for index, raw in enumerate(raw_entries):
        field = f"fixtures[{index}]"
        if not isinstance(raw, dict):
            raise PetCliRegressionError(f"{field} must be an object.")
        expected_keys = {
            "fixture_id",
            "request_path",
            "expected_radionuclide",
            "expected_materials",
            "expected_output_sha256",
            "expected_replay_verified",
        }
        if set(raw) != expected_keys:
            raise PetCliRegressionError(f"{field} contains missing or unexpected fields.")
        fixture_id = _text(raw["fixture_id"], f"{field}.fixture_id")
        request_path = _text(raw["request_path"], f"{field}.request_path")
        radionuclide = _text(raw["expected_radionuclide"], f"{field}.expected_radionuclide")
        materials_raw = raw["expected_materials"]
        if not isinstance(materials_raw, list) or not materials_raw:
            raise PetCliRegressionError(f"{field}.expected_materials must be a non-empty list.")
        materials = tuple(
            _text(value, f"{field}.expected_materials[{material_index}]")
            for material_index, value in enumerate(materials_raw)
        )
        digest = _text(raw["expected_output_sha256"], f"{field}.expected_output_sha256").lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise PetCliRegressionError(f"{field}.expected_output_sha256 must be a SHA-256 hex digest.")
        replay = raw["expected_replay_verified"]
        if not isinstance(replay, bool):
            raise PetCliRegressionError(f"{field}.expected_replay_verified must be boolean.")
        if fixture_id in fixture_ids:
            raise PetCliRegressionError(f"Duplicate fixture_id: {fixture_id}")
        if request_path in request_paths:
            raise PetCliRegressionError(f"Duplicate request_path: {request_path}")
        fixture_ids.add(fixture_id)
        request_paths.add(request_path)
        entries.append(
            PetCliRegressionEntry(
                fixture_id=fixture_id,
                request_path=request_path,
                expected_radionuclide=radionuclide,
                expected_materials=materials,
                expected_output_sha256=digest,
                expected_replay_verified=replay,
            )
        )
    return PetCliRegressionManifest(entries=tuple(entries))


def _resolve_request_path(manifest_path: Path, request_path: str) -> Path:
    candidate = Path(request_path)
    if candidate.is_absolute():
        return candidate
    project_relative = Path.cwd() / candidate
    if project_relative.exists():
        return project_relative
    return manifest_path.parent / candidate


def run_pet_cli_regression_manifest(path: str | Path) -> PetCliRegressionRunResult:
    """Execute every approved fixture and fail on the first regression."""

    manifest_path = Path(path).resolve()
    manifest = load_pet_cli_regression_manifest(manifest_path)
    results: list[PetCliRegressionCaseResult] = []

    for entry in manifest.entries:
        request_path = _resolve_request_path(manifest_path, entry.request_path).resolve()
        if not request_path.is_file():
            raise PetCliRegressionError(
                f"Fixture {entry.fixture_id} request file does not exist: {request_path}"
            )
        try:
            run_result, _ = run_request_file(request_path)
            replay_result, _ = replay_request_file(request_path)
        except PetCalculationRequestCliError as exc:
            raise PetCliRegressionError(f"Fixture {entry.fixture_id} failed: {exc}") from exc

        radionuclide = run_result.snapshot.source.radionuclide_spec.code
        if radionuclide != entry.expected_radionuclide:
            raise PetCliRegressionError(
                f"Fixture {entry.fixture_id} radionuclide mismatch: "
                f"expected {entry.expected_radionuclide}, got {radionuclide}."
            )
        materials = tuple(
            barrier.solver_result.material_key
            for barrier in run_result.snapshot.barrier_results
        )
        if materials != entry.expected_materials:
            raise PetCliRegressionError(
                f"Fixture {entry.fixture_id} material sequence mismatch: "
                f"expected {entry.expected_materials}, got {materials}."
            )
        digest = canonical_payload_sha256(run_result.payload)
        if digest != entry.expected_output_sha256:
            raise PetCliRegressionError(
                f"Fixture {entry.fixture_id} output digest mismatch: "
                f"expected {entry.expected_output_sha256}, got {digest}."
            )
        replay_verified = bool(
            run_result.replay_verified and replay_result.replay_verified
        )
        if replay_verified is not entry.expected_replay_verified:
            raise PetCliRegressionError(
                f"Fixture {entry.fixture_id} replay status mismatch: "
                f"expected {entry.expected_replay_verified}, got {replay_verified}."
            )
        results.append(
            PetCliRegressionCaseResult(
                fixture_id=entry.fixture_id,
                request_path=request_path,
                output_sha256=digest,
                replay_verified=replay_verified,
            )
        )

    return PetCliRegressionRunResult(
        manifest_path=manifest_path,
        cases=tuple(results),
    )


def render_pet_cli_regression_summary(result: PetCliRegressionRunResult) -> str:
    lines = [
        "PET CLI REGRESSION MANIFEST",
        "=" * 27,
        f"Manifest: {result.manifest_path}",
        f"Fixtures: {len(result.cases)}",
    ]
    for case in result.cases:
        lines.extend(
            [
                "",
                f"[{case.fixture_id}] PASS",
                f"  Request: {case.request_path}",
                f"  Output SHA-256: {case.output_sha256}",
                f"  Replay verified: {'yes' if case.replay_verified else 'no'}",
            ]
        )
    lines.extend(["", "Overall status: PASS"])
    return "\n".join(lines)
