"""Canonical deterministic-regression verification for frozen SPECT fixtures."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from engine.spect_calculation_request_contract import current_spect_calculation_physics_freeze
from services.spect_calculation_request_runner import (
    SpectCalculationRequestCliError,
    replay_request_file,
    run_request_file,
)

SCHEMA = "radshield_spect_cli_regression_manifest_v1"
VERSION = 1


class SpectCliRegressionError(ValueError):
    pass


def _norm(v: Any):
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            raise SpectCliRegressionError("Non-finite value in SPECT regression payload.")
        r = round(v, 9)
        return 0.0 if r == 0.0 else r
    if isinstance(v, Mapping):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    raise SpectCliRegressionError("Unsupported SPECT regression payload value.")


def canonical_payload_sha256(payload):
    return hashlib.sha256(
        json.dumps(_norm(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def load_manifest(path):
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if set(raw) != {"schema", "schema_version", "production_eligible", "physics_freeze_id", "fixtures"}:
        raise SpectCliRegressionError("Invalid SPECT CLI regression manifest fields.")
    if raw["schema"] != SCHEMA or raw["schema_version"] != VERSION or raw["production_eligible"] is not False:
        raise SpectCliRegressionError("Invalid SPECT CLI regression manifest header.")
    if raw["physics_freeze_id"] != current_spect_calculation_physics_freeze()["freeze_id"]:
        raise SpectCliRegressionError("SPECT CLI regression manifest physics freeze does not match the installed Step 20 freeze.")
    if not isinstance(raw["fixtures"], list) or not raw["fixtures"]:
        raise SpectCliRegressionError("fixtures must be non-empty.")
    return raw


def run_manifest(path):
    p = Path(path).resolve()
    raw = load_manifest(p)
    out = []
    seen = set()
    for i, e in enumerate(raw["fixtures"]):
        required = {"fixture_id", "request_path", "expected_materials", "expected_output_sha256", "expected_replay_verified"}
        if not isinstance(e, dict) or set(e) != required:
            raise SpectCliRegressionError(f"fixtures[{i}] invalid fields.")
        if e["fixture_id"] in seen:
            raise SpectCliRegressionError("Duplicate fixture_id.")
        seen.add(e["fixture_id"])
        rp = Path(e["request_path"])
        rp = rp if rp.is_absolute() else Path.cwd() / rp
        try:
            result, _ = run_request_file(rp)
            replay, _ = replay_request_file(rp)
        except SpectCalculationRequestCliError as exc:
            raise SpectCliRegressionError(str(exc)) from exc
        mats = [r.material_key for r in result.schedule.rows]
        if mats != e["expected_materials"]:
            raise SpectCliRegressionError(f"Fixture {e['fixture_id']} material sequence mismatch.")
        digest = canonical_payload_sha256(result.payload)
        if digest != e["expected_output_sha256"]:
            raise SpectCliRegressionError(
                f"Fixture {e['fixture_id']} output digest mismatch: expected {e['expected_output_sha256']}, got {digest}."
            )
        if bool(result.replay_verified and replay.replay_verified) != e["expected_replay_verified"]:
            raise SpectCliRegressionError("Replay status mismatch.")
        out.append((e["fixture_id"], rp, digest))
    return p, out
