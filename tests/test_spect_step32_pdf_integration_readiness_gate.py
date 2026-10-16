from __future__ import annotations

from pathlib import Path

import pytest

from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import (
    new_spect_working_project_state,
    set_room_spect_working_state,
)
from services.export_eligibility import assess_export_eligibility
from services.source_readiness import validate_project_source_readiness
from services.spect_pdf_integration_readiness_gate import (
    SPECT_PDF_GATE_BLOCK_REASON,
    SPECT_PDF_INTEGRATION_READINESS_BASELINE,
    SPECT_PDF_INTEGRATION_READINESS_CONTRACT_VERSION,
    SPECT_PDF_INTEGRATION_SWITCH_ENABLED,
    SpectPdfIntegrationNotEnabledError,
    assess_spect_pdf_integration_readiness,
    require_spect_pdf_integration_enabled,
)


def _spect_project() -> Project:
    room = Room(
        name="SPECT Room",
        modality="SPECT",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy="Pb 1.0 mm",
                thickness_mm=1.0,
                distance_m=2.0,
                occupancy_factor=1.0,
                design_goal_uSv_per_week=1.0,
            )
        ],
    )
    set_room_spect_working_state(
        room,
        new_spect_working_project_state(
            SpectSourceDomain("Tc99m", 600.0, 20.0, 0.5)
        ),
    )
    return Project(project_name="SPECT Step 32", rooms=[room])


def test_step32_foundations_pass_but_pdf_gate_remains_closed():
    state = assess_spect_pdf_integration_readiness()
    assert state["contract_version"] == SPECT_PDF_INTEGRATION_READINESS_CONTRACT_VERSION == 1
    assert state["baseline"] == SPECT_PDF_INTEGRATION_READINESS_BASELINE
    assert state["validated_foundations"] is True
    assert state["pdf_integration_switch_enabled"] is False
    assert state["pdf_integration_ready"] is False
    assert state["issued_pdf_enabled"] is False
    assert state["machine_export_enabled"] is False
    assert state["certification_enabled"] is False
    assert len(state["checks"]) == 4
    assert all(check["passed"] for check in state["checks"])
    assert state["blocking_reasons"] == [SPECT_PDF_GATE_BLOCK_REASON]


def test_step32_explicit_gate_fails_closed():
    assert SPECT_PDF_INTEGRATION_SWITCH_ENABLED is False
    with pytest.raises(SpectPdfIntegrationNotEnabledError, match="not enabled"):
        require_spect_pdf_integration_enabled()


def test_step32_normal_output_gate_still_blocks_persisted_spect():
    readiness = validate_project_source_readiness(_spect_project())
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(
        preflight=readiness,
        requested_report_status="Final",
    )
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_step32_gate_is_not_imported_by_issueable_output_modules():
    token = "spect_pdf_integration_readiness_gate"
    paths = list(Path("reports").glob("*.py")) + [
        Path("services/export_eligibility.py"),
        Path("services/report_certification.py"),
        Path("services/report_wording_guard.py"),
    ]
    for path in paths:
        assert token not in path.read_text(encoding="utf-8-sig")


def test_step32_report_modules_remain_disconnected_from_step29_to_step31():
    forbidden_tokens = (
        "spect_source_summary_harness",
        "spect_report_payload_harness",
        "spect_report_section_view_model",
        "spect_report_plain_text_preview",
        "spect_pdf_integration_readiness_gate",
    )
    for path in Path("reports").glob("*.py"):
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden_tokens:
            assert token not in text, f"{path} must remain disconnected from SPECT report-preview chain"


def test_step32_gate_module_has_no_pdf_or_file_output_dependencies():
    text = Path("services/spect_pdf_integration_readiness_gate.py").read_text(encoding="utf-8")
    for forbidden in (
        "reportlab",
        "render_pdf",
        "output_pipeline",
        "results_exporter",
        "report_certification",
        "Path(",
        "open(",
    ):
        assert forbidden not in text


def test_step32_cli_reports_validated_foundations_but_closed_integration(capsys):
    from tools import spect_pdf_integration_readiness

    result = spect_pdf_integration_readiness.main()

    captured = capsys.readouterr()

    assert result in (None, 0)
    assert "SPECT STEP 32 PDF INTEGRATION READINESS" in captured.out
    assert "Validated foundations: YES" in captured.out
    assert "PDF integration switch enabled: NO" in captured.out
    assert "PDF integration ready: NO" in captured.out
    assert "Issued SPECT PDF enabled: NO" in captured.out
    assert "Machine export enabled: NO" in captured.out
    assert "Certification enabled: NO" in captured.out


def test_step32_audit_document_records_no_go_and_next_boundary():
    text = Path("docs/architecture/SPECT_PDF_Integration_Readiness_Gate_Step_32.md").read_text(
        encoding="utf-8-sig"
    )
    assert "Validated report foundations: **YES**" in text
    assert "PDF integration switch enabled: **NO**" in text
    assert "**NO-GO for issued SPECT PDF integration.**" in text
    assert "non-issueable PDF preview adapter" in text
    assert "Step 22 remains authoritative" in text
