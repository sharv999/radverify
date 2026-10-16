"""Step 34 controlled SPECT production-host integration regression guards."""
from pathlib import Path
from types import SimpleNamespace

from engine.spect_production_dispatch_gate import assess_spect_production_dispatch_readiness
from modalities.registry import (
    coming_soon_modality_names,
    locked_source_mapping,
    production_modality_names,
    source_calculation_blocked_reason,
)
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, spect_source_readiness_result
from services.export_eligibility import assess_export_eligibility
from services.source_readiness import validate_project_source_readiness
from services.spect_host_integration_gate import (
    SPECT_HOST_INTEGRATION_BASELINE,
    assess_spect_host_integration_readiness,
    require_spect_host_integration_ready,
)
from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness

ROOT = Path(__file__).resolve().parents[1]


def _spect_room_and_source():
    room = SimpleNamespace(name="SPECT Room 1", modality="SPECT", modality_state={}, sources=[])
    source = SimpleNamespace(
        name="SPECT Patient Source",
        source_type="spect_patient",
        radiation_type="tc99m_140kev",
        params={},
    )
    return room, source


def test_step34_spect_is_registry_driven_production_host_modality():
    assert "SPECT" in production_modality_names()
    assert "SPECT" not in coming_soon_modality_names()
    assert locked_source_mapping(production_only=True)["SPECT"] == [("spect_patient", "SPECT Patient Source")]


def test_step34_app_host_remains_modality_neutral_and_registry_driven():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ROOM_TYPES = production_modality_names()" in app_text
    assert "LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)" in app_text
    assert 'if modality == "SPECT"' not in app_text
    assert "if room.modality == \"SPECT\"" not in app_text


def test_step34_source_readiness_allows_host_but_blocks_issued_output():
    result = spect_source_readiness_result(
        "spect_patient", {}, {"room_name": "SPECT Room 1", "source_name": "SPECT Patient Source"}
    )
    assert result["overall_status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["output_blocking"] is True
    assert result["basis"] == "production_host_results_only"
    assert result["errors"] == []
    assert result["warnings"]


def test_step34_project_readiness_is_nonblocking_but_normal_output_stays_hard_blocked():
    room, source = _spect_room_and_source()
    project = SimpleNamespace(rooms=[room], sources=[source])
    preflight = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [source],
    )
    assert preflight["overall_status"] == "REVIEW"
    assert preflight["blocking"] is False
    assert preflight["errors"] == []
    assert preflight["warnings"]

    eligibility = assess_export_eligibility(preflight=preflight, requested_report_status="Draft")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.allowed is False


def test_step34_generic_source_calculator_remains_closed():
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON


def test_step34_dispatch_ready_but_issued_pdf_gate_remains_closed():
    dispatch = assess_spect_production_dispatch_readiness()
    assert dispatch.production_ready is True
    assert dispatch.dispatch_enabled is True
    pdf = assess_spect_pdf_integration_readiness()
    assert pdf["validated_foundations"] is True
    assert pdf["pdf_integration_switch_enabled"] is False
    assert pdf["issued_pdf_enabled"] is False


def test_step34_host_integration_gate_is_green_with_output_surfaces_closed():
    assessment = require_spect_host_integration_ready()
    assert assessment["baseline"] == SPECT_HOST_INTEGRATION_BASELINE
    assert assessment["host_integration_ready"] is True
    assert assessment["working_project_enabled"] is True
    assert assessment["production_calculation_enabled"] is True
    assert assessment["in_app_results_enabled"] is True
    assert assessment["issued_pdf_enabled"] is False
    assert assessment["machine_export_enabled"] is False
    assert assessment["certification_enabled"] is False


def test_step34_host_gate_not_imported_by_issued_output_modules():
    forbidden = ("spect_host_integration_gate", "require_spect_host_integration_ready")
    paths = [
        ROOT / "reports" / "output_pipeline.py",
        ROOT / "reports" / "report_generator.py",
        ROOT / "services" / "report_certification.py",
        ROOT / "services" / "export_eligibility.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in forbidden:
        assert token not in combined
