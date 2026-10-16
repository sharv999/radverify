"""Tests for the isolated PET calculation-request CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from modalities.pet import PET_CALCULATION_BLOCK_REASON, PetExposurePhase, PetSourceDomain
from serialization.pet_calculation_request_contract import (
    PetCalculationRequestEnvelope,
    pet_calculation_request_to_dict,
)
from services.pet_calculation_service import PetBarrierCalculationRequest
from tools.pet_calculation_request_cli import (
    PetCalculationRequestCliError,
    render_request_validation,
    replay_request_file,
    run_request_file,
)


def _request_path(tmp_path: Path) -> Path:
    request = PetCalculationRequestEnvelope(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=200.0,
            patients_per_week=20.0,
            residual_activity_factor=0.9,
            exposure_phases=(
                PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
                PetExposurePhase("Imaging", 1.0, 0.5, 0.75),
            ),
        ),
        barrier_requests=(
            PetBarrierCalculationRequest(
                material_key="lead",
                distance_m=2.0,
                occupancy_factor=0.5,
                design_goal_uSv_per_week=10.0,
                provided_thickness_mm=16.0,
                source_name="PET uptake patient",
            ),
        ),
    )
    path = tmp_path / "pet-request.json"
    path.write_text(
        json.dumps(pet_calculation_request_to_dict(request), indent=2),
        encoding="utf-8",
    )
    return path


def test_validate_prints_non_production_request_summary(tmp_path):
    path = _request_path(tmp_path)

    summary = render_request_validation(path)

    assert "PET CALCULATION REQUEST VALIDATION" in summary
    assert "Status: VALID" in summary
    assert "Production eligible: no" in summary
    assert "Radionuclide: F18" in summary
    assert "Barrier requests: 1" in summary
    assert "Material: lead" in summary


def test_run_executes_request_and_optionally_writes_replayable_snapshot(tmp_path):
    path = _request_path(tmp_path)
    output = tmp_path / "pet-result.json"

    result, summary = run_request_file(path, output=output)

    assert result.replay_verified is True
    assert result.payload["production_eligible"] is False
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == result.payload
    assert "Replay verified: yes" in summary
    assert "Result snapshot written to:" in summary


def test_replay_executes_twice_and_proves_determinism(tmp_path):
    path = _request_path(tmp_path)

    result, summary = replay_request_file(path)

    assert result.replay_verified is True
    assert "Deterministic replay: VERIFIED" in summary
    assert "Production eligible: no" in summary


def test_cli_refuses_noncanonical_requests_and_existing_output(tmp_path):
    path = _request_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PetCalculationRequestCliError, match="not canonical"):
        render_request_validation(path)

    valid_path = _request_path(tmp_path)
    output = tmp_path / "existing.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(PetCalculationRequestCliError, match="already exists"):
        run_request_file(valid_path, output=output)


def _run_cli_with_file_capture(tmp_path: Path, name: str, args: list[str]):
    stdout_path = tmp_path / f"{name}.stdout.txt"
    stderr_path = tmp_path / f"{name}.stderr.txt"
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


def test_cli_validate_run_and_replay_commands(tmp_path):
    request = _request_path(tmp_path)

    validate, validate_stdout, validate_stderr = _run_cli_with_file_capture(
        tmp_path, "validate", ["validate", str(request)]
    )
    assert validate.returncode == 0, validate_stderr
    assert "Status: VALID" in validate_stdout

    result_path = tmp_path / "result.json"
    run, run_stdout, run_stderr = _run_cli_with_file_capture(
        tmp_path,
        "run",
        ["run", str(request), "--output", str(result_path)],
    )
    assert run.returncode == 0, run_stderr
    assert "Replay verified: yes" in run_stdout
    assert result_path.exists()

    replay, replay_stdout, replay_stderr = _run_cli_with_file_capture(
        tmp_path, "replay", ["replay", str(request)]
    )
    assert replay.returncode == 0, replay_stderr
    assert "Deterministic replay: VERIFIED" in replay_stdout


def test_cli_remains_disconnected_from_ui_production_serializer_and_reports():
    from modalities.registry import (
        production_modality_names,
        source_calculation_blocked_reason,
        source_type_options,
    )

    assert "PET" in production_modality_names()
    assert "pet_patient" in source_type_options(production_only=True)
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    module_name = "pet_calculation_request_cli"
    paths = [
        Path("app.py"),
        Path("services/project_serializer.py"),
        Path("engine/shielding_engine.py"),
        *Path("reports").glob("*.py"),
    ]
    assert all(module_name not in path.read_text(encoding="utf-8") for path in paths)
