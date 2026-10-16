"""Step 36 cleanup guards for historical SPECT wording/schema debt."""
from pathlib import Path

from modalities.spect import SPECT_MODALITY
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION,
    SPECT_WORKING_PROJECT_STATE_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_VERSION,
)
from services.spect_release_gate import SPECT_RELEASE_CLEANUP_DEBT, assess_spect_release_gate

ROOT = Path(__file__).resolve().parents[1]


def test_step36_runtime_spect_wording_matches_current_controlled_host_scope():
    text = (ROOT / "modalities" / "spect.py").read_text(encoding="utf-8")
    assert "SPECT remains registered as coming-soon" not in text
    assert 'report_subtitle="SPECT remains non-production in this build"' not in text
    assert "Controlled SPECT production-host assessment" in text
    assert SPECT_MODALITY.production_enabled is True


def test_step36_working_state_schema_is_v2_with_legacy_v1_identity_retained():
    assert SPECT_WORKING_PROJECT_STATE_SCHEMA == "radshield_spect_working_source_v2"
    assert SPECT_WORKING_PROJECT_STATE_VERSION == 2
    assert SPECT_WORKING_PROJECT_STATE_LEGACY_SCHEMA == "radshield_spect_working_source_v1"
    assert SPECT_WORKING_PROJECT_STATE_LEGACY_VERSION == 1


def test_step36_release_gate_cleanup_debt_is_empty_and_output_stays_closed():
    result = assess_spect_release_gate()
    assert SPECT_RELEASE_CLEANUP_DEBT == ()
    assert result["cleanup_debt"] == []
    assert result["controlled_host_release_ready"] is True
    assert result["issued_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["certification_enabled"] is False


def test_step36_historical_docs_are_marked_and_current_status_is_authoritative():
    historical = (
        "SPECT_Production_Readiness_Boundary_Audit_Step_19.md",
        "SPECT_Physics_Dataset_Approval_Freeze_Step_20.md",
        "SPECT_Canonical_Request_Replay_Step_21.md",
        "SPECT_Working_Project_Persistence_Step_23.md",
        "SPECT_Production_Dispatch_Readiness_Audit_Step_24.md",
    )
    for name in historical:
        text = (ROOT / "docs" / "architecture" / name).read_text(encoding="utf-8")
        assert "Historical snapshot:" in text
        assert "Step 35/36" in text

    current = (ROOT / "docs" / "architecture" / "SPECT_Current_Status_After_Step_36.md").read_text(
        encoding="utf-8"
    )
    assert "authoritative current-status pointer" in current
    assert "Issued/final SPECT PDF routing is disabled." in current
    assert "radshield_spect_working_source_v2" in current
