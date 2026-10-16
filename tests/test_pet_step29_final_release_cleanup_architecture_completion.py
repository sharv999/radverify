from __future__ import annotations

from pathlib import Path

from modalities.pet import PET_MODALITY
from serialization.pet_working_project_state import (
    PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA,
    PET_WORKING_PROJECT_STATE_LEGACY_VERSION,
    PET_WORKING_PROJECT_STATE_SCHEMA,
    PET_WORKING_PROJECT_STATE_VERSION,
)
from services.pet_architecture_completion import (
    PET_ARCHITECTURE_COMPLETE_CURRENT_SCOPE,
    PET_ARCHITECTURE_COMPLETION_BASELINE,
    PET_ARCHITECTURE_COMPLETION_SCOPE,
    PET_ARCHITECTURE_COMPLETION_STEP,
    assess_pet_architecture_completion,
    require_pet_architecture_complete_current_scope,
)
from services.pet_pdf_integration_readiness_gate import assess_pet_pdf_integration_readiness
from services.pet_release_gate import (
    PET_RELEASE_CLEANUP_DEBT,
    assess_pet_release_gate,
    require_pet_controlled_host_release_ready,
)
from services.pet_report_pdf_preview import (
    PET_PDF_PREVIEW_INTEGRATION_OPEN,
    PET_PDF_PREVIEW_ISSUEABLE,
    PET_PDF_PREVIEW_OUTPUT_ELIGIBLE,
)

ROOT = Path(__file__).resolve().parents[1]


def test_step29_final_release_gate_is_go_for_controlled_host_but_no_go_for_issued_output():
    result = require_pet_controlled_host_release_ready()
    assert result["controlled_host_release_ready"] is True
    assert result["issued_output_release_ready"] is False
    assert result["working_project_enabled"] is True
    assert result["production_calculation_enabled"] is True
    assert result["in_app_results_enabled"] is True
    assert result["issued_pdf_enabled"] is False
    assert result["machine_export_enabled"] is False
    assert result["certification_enabled"] is False
    assert result["signatures_enabled"] is False
    assert result["blocking_reasons"] == []


def test_step29_all_release_invariants_pass_and_cleanup_debt_is_empty():
    result = assess_pet_release_gate()
    assert result["checks"]
    assert all(check["passed"] for check in result["checks"])
    assert PET_RELEASE_CLEANUP_DEBT == ()
    assert result["cleanup_debt"] == []


def test_step29_runtime_pet_wording_matches_current_controlled_host_scope():
    text = (ROOT / "modalities" / "pet.py").read_text(encoding="utf-8")
    assert "Controlled PET production-host assessment" in text
    assert "PET shielding calculations are not implemented in this build" not in text
    assert "production calculations are currently blocked" not in text
    assert PET_MODALITY.production_enabled is True


def test_step29_working_state_schema_v3_and_legacy_v2_identity_remain_frozen():
    assert PET_WORKING_PROJECT_STATE_SCHEMA == "radshield_pet_working_source_v3"
    assert PET_WORKING_PROJECT_STATE_VERSION == 3
    assert PET_WORKING_PROJECT_STATE_LEGACY_SCHEMA == "radshield_pet_working_source_v2"
    assert PET_WORKING_PROJECT_STATE_LEGACY_VERSION == 2


def test_step29_step15_readiness_document_is_explicitly_historical():
    text = (
        ROOT / "docs" / "architecture" / "PET_Production_Readiness_Boundary_Audit_Step_15.md"
    ).read_text(encoding="utf-8")
    assert text.startswith("> **Historical snapshot:**")
    assert "Steps 27-29" in text
    assert "must not be interpreted as current registry or calculation state" in text


def test_step29_pdf_gate_and_preview_remain_closed_and_nonissueable():
    pdf = assess_pet_pdf_integration_readiness()
    assert pdf["validated_foundations"] is True
    assert pdf["pdf_integration_switch_enabled"] is False
    assert pdf["issued_pdf_enabled"] is False
    assert pdf["machine_export_enabled"] is False
    assert pdf["certification_enabled"] is False
    assert PET_PDF_PREVIEW_INTEGRATION_OPEN is False
    assert PET_PDF_PREVIEW_ISSUEABLE is False
    assert PET_PDF_PREVIEW_OUTPUT_ELIGIBLE is False


def test_step29_architecture_is_formally_complete_for_current_scope():
    result = require_pet_architecture_complete_current_scope()
    assert PET_ARCHITECTURE_COMPLETE_CURRENT_SCOPE is True
    assert result["architecture_complete_current_scope"] is True
    assert result["baseline"] == PET_ARCHITECTURE_COMPLETION_BASELINE
    assert result["completion_step"] == PET_ARCHITECTURE_COMPLETION_STEP == 29
    assert result["completion_scope"] == PET_ARCHITECTURE_COMPLETION_SCOPE
    assert result["issued_output_in_completion_scope"] is False
    assert result["blocking_reasons"] == []


def test_step29_all_architecture_completion_invariants_pass():
    result = assess_pet_architecture_completion()
    assert result["checks"]
    assert all(check["passed"] for check in result["checks"])


def test_step29_release_and_completion_gates_are_not_imported_by_issueable_output_modules():
    forbidden = (
        "pet_release_gate",
        "pet_architecture_completion",
        "require_pet_controlled_host_release_ready",
        "require_pet_architecture_complete_current_scope",
    )
    paths = [
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "reports" / "report_generator.py",
        ROOT / "services" / "report_certification.py",
        ROOT / "services" / "export_eligibility.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined


def test_step29_authoritative_docs_record_parity_and_closed_output():
    current = (
        ROOT / "docs" / "architecture" / "PET_Current_Status_After_Step_29.md"
    ).read_text(encoding="utf-8")
    completion = (
        ROOT / "docs" / "architecture" / "PET_Final_Release_and_Architecture_Completion_Step_29.md"
    ).read_text(encoding="utf-8")
    assert "authoritative current-status pointer" in current
    assert "radshield_pet_working_source_v3" in current
    assert "Issued/final PET PDF routing is disabled." in current
    assert "GO — controlled production-host scope" in completion
    assert "NO-GO — issued-output scope" in completion
    assert "PET and SPECT are on the same formal architectural footing" in completion


def test_step29_clis_report_go_complete_and_closed_issued_output(capsys):
    from tools import pet_architecture_completion, pet_release_gate

    assert pet_release_gate.main() == 0
    release_out = capsys.readouterr().out
    assert "Controlled production-host release: GO" in release_out
    assert "Issued PDF/export/certification release: NO-GO" in release_out

    assert pet_architecture_completion.main() == 0
    completion_out = capsys.readouterr().out
    assert "Current production-host architecture: COMPLETE" in completion_out
    assert "Issued PDF/export/certification in completion scope: NO" in completion_out
