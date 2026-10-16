"""Curated non-production PET request fixtures for CLI validation and replay."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from modalities.pet import PET_CALCULATION_BLOCK_REASON
from serialization.pet_calculation_request_contract import (
    load_and_replay_pet_calculation_request,
    pet_calculation_request_from_dict,
    pet_calculation_request_to_dict,
)
from tools.pet_calculation_request_cli import (
    render_request_validation,
    replay_request_file,
    run_request_file,
)


FIXTURE_DIR = Path("tests/fixtures/pet_requests")
F18_FIXTURE = FIXTURE_DIR / "pet_f18_uptake_imaging_request.json"
GA68_FIXTURE = FIXTURE_DIR / "pet_ga68_delayed_imaging_request.json"
CURATED_FIXTURES = (F18_FIXTURE, GA68_FIXTURE)


@pytest.mark.parametrize(
    ("path", "radionuclide", "phase_count", "barrier_count", "materials"),
    [
        (F18_FIXTURE, "F18", 2, 2, {"lead", "concrete_2350kg_m3"}),
        (GA68_FIXTURE, "Ga68", 2, 2, {"concrete_2350kg_m3", "iron"}),
    ],
)
def test_curated_pet_request_fixtures_are_canonical_and_non_production(
    path, radionuclide, phase_count, barrier_count, materials
):
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = pet_calculation_request_from_dict(payload)

    assert payload["production_eligible"] is False
    assert request.source.radionuclide == radionuclide
    assert len(request.source.exposure_phases) == phase_count
    assert len(request.barrier_requests) == barrier_count
    assert {item.material_key for item in request.barrier_requests} == materials
    assert pet_calculation_request_to_dict(request) == payload


@pytest.mark.parametrize("path", CURATED_FIXTURES)
def test_curated_pet_request_fixtures_validate_run_and_replay(path, tmp_path):
    validation = render_request_validation(path)
    run_result, run_summary = run_request_file(path)
    replay_result, replay_summary = replay_request_file(path)
    loaded_result = load_and_replay_pet_calculation_request(path)

    assert "Status: VALID" in validation
    assert "Production eligible: no" in validation
    assert run_result.replay_verified is True
    assert replay_result.replay_verified is True
    assert loaded_result.replay_verified is True
    assert run_result.payload == replay_result.payload == loaded_result.payload
    assert "Replay verified: yes" in run_summary
    assert "Deterministic replay: VERIFIED" in replay_summary

    output = tmp_path / f"{path.stem}-result.json"
    written_result, _ = run_request_file(path, output=output)
    assert json.loads(output.read_text(encoding="utf-8")) == written_result.payload
    assert written_result.payload["production_eligible"] is False


def _run_cli(tmp_path: Path, label: str, args: list[str]):
    stdout_path = tmp_path / f"{label}.stdout.txt"
    stderr_path = tmp_path / f"{label}.stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        completed = subprocess.run(
            [sys.executable, "-m", "tools.pet_calculation_request_cli", *args],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
        )
    return (
        completed,
        stdout_path.read_text(encoding="utf-8"),
        stderr_path.read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize("path", CURATED_FIXTURES)
def test_real_cli_commands_accept_curated_pet_request_fixtures(path, tmp_path):
    validate, validate_stdout, validate_stderr = _run_cli(
        tmp_path, f"{path.stem}-validate", ["validate", str(path)]
    )
    assert validate.returncode == 0, validate_stderr
    assert "Status: VALID" in validate_stdout

    output = tmp_path / f"{path.stem}-cli-result.json"
    run, run_stdout, run_stderr = _run_cli(
        tmp_path,
        f"{path.stem}-run",
        ["run", str(path), "--output", str(output)],
    )
    assert run.returncode == 0, run_stderr
    assert "Replay verified: yes" in run_stdout
    assert output.exists()

    replay, replay_stdout, replay_stderr = _run_cli(
        tmp_path, f"{path.stem}-replay", ["replay", str(path)]
    )
    assert replay.returncode == 0, replay_stderr
    assert "Deterministic replay: VERIFIED" in replay_stdout


def test_curated_fixture_set_remains_disconnected_from_ui_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    fixture_names = {path.name for path in CURATED_FIXTURES}
    production_paths = [
        Path("app.py"),
        Path("services/project_serializer.py"),
        Path("engine/shielding_engine.py"),
        *Path("reports").glob("*.py"),
    ]
    for production_path in production_paths:
        text = production_path.read_text(encoding="utf-8")
        assert all(name not in text for name in fixture_names)
