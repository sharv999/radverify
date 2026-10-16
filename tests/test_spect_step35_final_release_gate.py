"""Step 35 final SPECT release-gate / cleanup audit regression guards."""
from pathlib import Path
from types import SimpleNamespace

from engine.spect_low_transmission_policy import (
    SPECT_LOW_TRANSMISSION_POLICY_APPROVED,
    SPECT_LOW_TRANSMISSION_THRESHOLD,
)
from engine.spect_production_dispatch_gate import assess_spect_production_dispatch_readiness
from modalities.registry import (
    coming_soon_modality_names,
    locked_source_mapping,
    production_modality_names,
    source_calculation_blocked_reason,
)
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, spect_source_readiness_result
from serialization.spect_working_project_state import (
    SPECT_WORKING_PROJECT_STATE_SCHEMA,
    SPECT_WORKING_PROJECT_STATE_VERSION,
)
from services.export_eligibility import assess_export_eligibility
from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness
from services.spect_release_gate import (
    SPECT_RELEASE_CLEANUP_DEBT,
    SPECT_RELEASE_GATE_BASELINE,
    assess_spect_release_gate,
    require_spect_controlled_host_release_ready,
)
from services.spect_report_pdf_preview import (
    SPECT_PDF_PREVIEW_INTEGRATION_OPEN,
    SPECT_PDF_PREVIEW_ISSUEABLE,
    SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE,
)

ROOT = Path(__file__).resolve().parents[1]


def _spect_preflight():
    result = spect_source_readiness_result(
        "spect_patient",
        {},
        {"room_name": "SPECT Room 1", "source_name": "SPECT Patient Source"},
    )
    return {
        "overall_status": result["overall_status"],
        "blocking": result["blocking"],
        "errors": list(result["errors"]),
        "warnings": list(result["warnings"]),
        "room_results": [{"room_name": result["room_name"], "source_results": [result]}],
    }


def test_step35_controlled_host_release_is_go_but_issued_output_is_no_go():
    result = require_spect_controlled_host_release_ready()
    assert result["baseline"] == SPECT_RELEASE_GATE_BASELINE
    assert result["controlled_host_release_ready"] is True
    assert result["working_project_enabled"] is True
    assert result["production_calculation_enabled"] is True
    assert result["in_app_results_enabled"] is True
    assert result["issued_output_release_ready"] is False
    assert result["issued_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["certification_enabled"] is False
    assert result["blocking_reasons"] == []


def test_step35_registry_and_app_host_path_are_stably_registry_driven():
    assert "SPECT" in production_modality_names()
    assert "SPECT" not in coming_soon_modality_names()
    assert locked_source_mapping(production_only=True)["SPECT"] == [
        ("spect_patient", "SPECT Patient Source")
    ]
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ROOM_TYPES = production_modality_names()" in app_text
    assert "LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)" in app_text
    assert 'if modality == "SPECT"' not in app_text
    assert 'if room.modality == "SPECT"' not in app_text


def test_step35_working_project_contract_and_dispatch_are_frozen_and_ready():
    assert SPECT_WORKING_PROJECT_STATE_SCHEMA == "radshield_spect_working_source_v2"
    assert SPECT_WORKING_PROJECT_STATE_VERSION == 2
    dispatch = assess_spect_production_dispatch_readiness()
    assert dispatch.validated_foundations is True
    assert dispatch.production_ready is True
    assert dispatch.dispatch_enabled is True


def test_step35_low_transmission_policy_remains_approved_at_one_percent_boundary():
    assert SPECT_LOW_TRANSMISSION_POLICY_APPROVED is True
    assert SPECT_LOW_TRANSMISSION_THRESHOLD == 0.01


def test_step35_legacy_generic_source_calculator_remains_closed():
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON


def test_step35_normal_pdf_machine_export_and_certification_remain_hard_blocked():
    eligibility = assess_export_eligibility(
        preflight=_spect_preflight(),
        requested_report_status="Final",
    )
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.allowed is False


def test_step35_pdf_gate_and_preview_remain_closed_and_nonissueable():
    pdf = assess_spect_pdf_integration_readiness()
    assert pdf["validated_foundations"] is True
    assert pdf["pdf_integration_switch_enabled"] is False
    assert pdf["issued_pdf_enabled"] is False
    assert SPECT_PDF_PREVIEW_INTEGRATION_OPEN is False
    assert SPECT_PDF_PREVIEW_ISSUEABLE is False
    assert SPECT_PDF_PREVIEW_OUTPUT_ELIGIBLE is False


def test_step35_cleanup_debt_is_cleared_without_opening_issued_output():
    result = assess_spect_release_gate()
    assert result["controlled_host_release_ready"] is True
    assert tuple(result["cleanup_debt"]) == SPECT_RELEASE_CLEANUP_DEBT == ()
    assert result["issued_output_release_ready"] is False


def test_step35_release_gate_is_not_imported_by_issued_output_modules():
    forbidden = ("spect_release_gate", "require_spect_controlled_host_release_ready")
    paths = [
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "reports" / "report_generator.py",
        ROOT / "services" / "report_certification.py",
        ROOT / "services" / "export_eligibility.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined


def test_step35_audit_document_records_split_release_decision():
    text = (ROOT / "docs" / "architecture" / "SPECT_Final_Release_Gate_Step_35.md").read_text(
        encoding="utf-8"
    )
    assert "GO — controlled production-host scope" in text
    assert "NO-GO — issued-output scope" in text
    assert "working-project persistence + gated production calculation + in-app Results" in text
    assert "issued/final SPECT PDF routing" in text
