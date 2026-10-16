from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine.material_attenuation_data import (
    APPROVAL_STATUS_PRODUCTION_APPROVED,
    load_material_attenuation_dataset,
)
from tools.attenuation_dataset_approval import (
    DatasetApprovalError,
    approve_dataset,
    expected_confirmation_token,
    records_sha256,
    render_dataset_review,
)


FIXTURE = Path("tests/fixtures/pet_511kev_attenuation_reviewed_pending_approval.json")


def test_review_prints_pending_metadata_records_provenance_values_and_token():
    review = render_dataset_review(FIXTURE)

    assert "MATERIAL ATTENUATION DATASET REVIEW" in review
    assert "reviewed_pending_user_approval" in review
    assert "tg108-511kev-lead-provisional" in review
    assert "TVL1: 16 mm" in review
    assert "TVLe: 14.8 mm" in review
    assert "AAPM Task Group 108" in review
    assert "Records SHA-256:" in review
    assert (
        "Required confirmation token: "
        "APPROVE:pet-511kev-aapm-tg108-review-fixture:2026-07-19-review-1"
    ) in review


def test_approval_requires_exact_dataset_revision_confirmation(tmp_path):
    output = tmp_path / "approved.json"

    with pytest.raises(DatasetApprovalError, match="Required token"):
        approve_dataset(
            FIXTURE,
            output,
            approved_by="Steve H",
            approved_date="2026-07-19",
            confirmation="APPROVE:wrong:revision",
        )

    assert not output.exists()


def test_approval_writes_separate_production_file_and_preserves_records(tmp_path):
    output = tmp_path / "pet_511kev_attenuation_production_approved.json"
    pending_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pending_digest = records_sha256(pending_payload)
    pending_dataset = load_material_attenuation_dataset(FIXTURE, allow_unapproved=True)

    approved_path = approve_dataset(
        FIXTURE,
        output,
        approved_by="Steve H",
        approved_date="2026-07-19",
        confirmation=expected_confirmation_token(pending_dataset),
    )

    assert approved_path == output.resolve()
    approved_payload = json.loads(output.read_text(encoding="utf-8"))
    assert approved_payload["records"] == pending_payload["records"]
    assert records_sha256(approved_payload) == pending_digest
    assert approved_payload["metadata"]["approval_status"] == "production_approved"
    assert approved_payload["metadata"]["approved_by"] == "Steve H"
    assert approved_payload["metadata"]["approved_date"] == "2026-07-19"
    assert approved_payload["metadata"]["approved_records_sha256"] == pending_digest

    loaded = load_material_attenuation_dataset(output)
    assert loaded.metadata.approval_status == APPROVAL_STATUS_PRODUCTION_APPROVED
    assert loaded.metadata.production_approved is True

    # The pending fixture itself remains unchanged and fail-closed.
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == pending_payload


def test_approval_refuses_source_overwrite_existing_output_blank_approver_and_bad_date(tmp_path):
    dataset = load_material_attenuation_dataset(FIXTURE, allow_unapproved=True)
    token = expected_confirmation_token(dataset)

    with pytest.raises(DatasetApprovalError, match="separate file"):
        approve_dataset(
            FIXTURE,
            FIXTURE,
            approved_by="Steve H",
            approved_date="2026-07-19",
            confirmation=token,
        )

    output = tmp_path / "approved.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(DatasetApprovalError, match="already exists"):
        approve_dataset(
            FIXTURE,
            output,
            approved_by="Steve H",
            approved_date="2026-07-19",
            confirmation=token,
        )

    output.unlink()
    with pytest.raises(DatasetApprovalError, match="approved_by"):
        approve_dataset(
            FIXTURE,
            output,
            approved_by=" ",
            approved_date="2026-07-19",
            confirmation=token,
        )
    with pytest.raises(DatasetApprovalError, match="YYYY-MM-DD"):
        approve_dataset(
            FIXTURE,
            output,
            approved_by="Steve H",
            approved_date="19/07/2026",
            confirmation=token,
        )


def _run_cli_with_file_capture(tmp_path, name, args):
    stdout_path = tmp_path / f"{name}.stdout.txt"
    stderr_path = tmp_path / f"{name}.stderr.txt"

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        completed = subprocess.run(
            [sys.executable, "-m", "tools.attenuation_dataset_approval", *args],
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


def test_cli_review_and_approve_workflow(tmp_path):
    review, review_stdout, review_stderr = _run_cli_with_file_capture(
        tmp_path,
        "review",
        ["review", str(FIXTURE)],
    )
    assert review.returncode == 0, review_stderr
    assert "Required confirmation token:" in review_stdout

    output = tmp_path / "approved.json"
    approve, approve_stdout, approve_stderr = _run_cli_with_file_capture(
        tmp_path,
        "approve",
        [
            "approve",
            str(FIXTURE),
            "--output",
            str(output),
            "--approved-by",
            "Steve H",
            "--approved-date",
            "2026-07-19",
            "--confirm",
            "APPROVE:pet-511kev-aapm-tg108-review-fixture:2026-07-19-review-1",
        ],
    )
    assert approve.returncode == 0, approve_stderr
    assert "Production-approved dataset written to:" in approve_stdout
    assert "Approval status: production_approved" in approve_stdout
    assert output.exists()


def test_approval_tool_remains_disconnected_from_ui_modalities_reports_and_dispatch():
    module_name = "attenuation_dataset_approval"
    production_texts = [
        Path("app.py").read_text(encoding="utf-8"),
        Path("engine/shielding_engine.py").read_text(encoding="utf-8"),
        Path("modalities/pet.py").read_text(encoding="utf-8"),
        Path("modalities/spect.py").read_text(encoding="utf-8"),
        "\n".join(path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")),
    ]
    assert all(module_name not in text for text in production_texts)
