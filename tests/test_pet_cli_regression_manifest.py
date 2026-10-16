"""Regression manifest for the curated non-production PET CLI fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.pet_cli_regression import (
    PetCliRegressionError,
    canonical_payload_sha256,
    load_pet_cli_regression_manifest,
    render_pet_cli_regression_summary,
    run_pet_cli_regression_manifest,
)
from tools.pet_calculation_request_cli import run_request_file

MANIFEST = Path("tests/fixtures/pet_requests/pet_cli_regression_manifest.json")


def test_manifest_lists_both_approved_curated_fixtures():
    manifest = load_pet_cli_regression_manifest(MANIFEST)

    assert [entry.fixture_id for entry in manifest.entries] == [
        "pet-f18-uptake-imaging-v1",
        "pet-ga68-delayed-imaging-v1",
    ]
    assert [entry.expected_radionuclide for entry in manifest.entries] == [
        "F18",
        "Ga68",
    ]
    assert [entry.expected_materials for entry in manifest.entries] == [
        ("lead", "concrete_2350kg_m3"),
        ("concrete_2350kg_m3", "iron"),
    ]
    assert all(entry.expected_replay_verified for entry in manifest.entries)


def test_manifest_expected_digests_match_current_canonical_outputs():
    manifest = load_pet_cli_regression_manifest(MANIFEST)

    for entry in manifest.entries:
        result, _ = run_request_file(entry.request_path)
        assert canonical_payload_sha256(result.payload) == entry.expected_output_sha256



def test_canonical_digest_ignores_only_subnanounit_float_noise():
    baseline = {"value": 1.234567890123, "nested": [2.0, 3.0]}
    tiny_noise = {"value": 1.234567890223, "nested": [2.0, 3.0]}
    meaningful_change = {"value": 1.2345689, "nested": [2.0, 3.0]}

    assert canonical_payload_sha256(baseline) == canonical_payload_sha256(tiny_noise)
    assert canonical_payload_sha256(baseline) != canonical_payload_sha256(meaningful_change)

def test_one_command_regression_runner_passes_all_fixtures():
    result = run_pet_cli_regression_manifest(MANIFEST)
    summary = render_pet_cli_regression_summary(result)

    assert result.passed is True
    assert len(result.cases) == 2
    assert all(case.replay_verified for case in result.cases)
    assert "pet-f18-uptake-imaging-v1] PASS" in summary
    assert "pet-ga68-delayed-imaging-v1] PASS" in summary
    assert "Overall status: PASS" in summary


def test_runner_rejects_changed_digest_and_replay_expectation(tmp_path):
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["fixtures"][0]["expected_output_sha256"] = "0" * 64
    changed = tmp_path / "changed-digest.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PetCliRegressionError, match="output digest mismatch"):
        run_pet_cli_regression_manifest(changed)

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["fixtures"][0]["expected_replay_verified"] = False
    changed = tmp_path / "changed-replay.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PetCliRegressionError, match="replay status mismatch"):
        run_pet_cli_regression_manifest(changed)


def test_manifest_validation_rejects_nonproduction_and_duplicate_entries(tmp_path):
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["production_eligible"] = True
    invalid = tmp_path / "production.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PetCliRegressionError, match="must remain non-production"):
        load_pet_cli_regression_manifest(invalid)

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["fixtures"].append(dict(payload["fixtures"][0]))
    invalid = tmp_path / "duplicate.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PetCliRegressionError, match="Duplicate fixture_id"):
        load_pet_cli_regression_manifest(invalid)


def test_real_cli_runs_manifest_with_windows_safe_capture(tmp_path):
    stdout_path = tmp_path / "regression.stdout.txt"
    stderr_path = tmp_path / "regression.stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        completed = subprocess.run(
            [sys.executable, "-m", "tools.pet_cli_regression", str(MANIFEST)],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
        )
    stdout = stdout_path.read_text(encoding="utf-8")
    stderr = stderr_path.read_text(encoding="utf-8")

    assert completed.returncode == 0, stderr
    assert "Fixtures: 2" in stdout
    assert "Overall status: PASS" in stdout


def test_regression_runner_remains_disconnected_from_ui_and_reports():
    module_name = "pet_cli_regression"
    paths = [
        Path("app.py"),
        Path("services/project_serializer.py"),
        Path("engine/shielding_engine.py"),
        *Path("reports").glob("*.py"),
    ]
    assert all(module_name not in path.read_text(encoding="utf-8") for path in paths)
