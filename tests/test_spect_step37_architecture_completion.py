"""Step 37 guards for formal completion of the current SPECT production-host architecture."""
from pathlib import Path

from services.spect_architecture_completion import (
    SPECT_ARCHITECTURE_COMPLETE_CURRENT_SCOPE,
    SPECT_ARCHITECTURE_COMPLETION_BASELINE,
    SPECT_ARCHITECTURE_COMPLETION_SCOPE,
    SPECT_ARCHITECTURE_COMPLETION_STEP,
    assess_spect_architecture_completion,
    require_spect_architecture_complete_current_scope,
)
from services.spect_release_gate import SPECT_RELEASE_CLEANUP_DEBT, assess_spect_release_gate

ROOT = Path(__file__).resolve().parents[1]


def test_step37_current_production_host_architecture_is_formally_complete():
    result = require_spect_architecture_complete_current_scope()
    assert SPECT_ARCHITECTURE_COMPLETE_CURRENT_SCOPE is True
    assert result["architecture_complete_current_scope"] is True
    assert result["baseline"] == SPECT_ARCHITECTURE_COMPLETION_BASELINE
    assert result["completion_step"] == SPECT_ARCHITECTURE_COMPLETION_STEP == 37
    assert result["completion_scope"] == SPECT_ARCHITECTURE_COMPLETION_SCOPE
    assert result["blocking_reasons"] == []


def test_step37_all_completion_invariants_pass():
    result = assess_spect_architecture_completion()
    assert result["checks"]
    assert all(check["passed"] for check in result["checks"])


def test_step37_issued_output_is_explicitly_outside_completed_scope():
    result = assess_spect_architecture_completion()
    release = assess_spect_release_gate()
    assert result["issued_output_in_completion_scope"] is False
    assert release["issued_output_release_ready"] is False
    assert release["issued_pdf_enabled"] is False
    assert release["machine_export_enabled"] is False
    assert release["certification_enabled"] is False


def test_step37_cleanup_debt_remains_empty():
    assert SPECT_RELEASE_CLEANUP_DEBT == ()
    assert assess_spect_release_gate()["cleanup_debt"] == []


def test_step37_completion_document_is_authoritative_and_does_not_open_output():
    text = (
        ROOT / "docs" / "architecture" / "SPECT_Architecture_Completion_Step_37.md"
    ).read_text(encoding="utf-8")
    assert "architecturally complete for the current production-host scope" in text
    assert "issued/final SPECT PDF routing" in text
    assert "requires a separate future release-gate decision" in text
