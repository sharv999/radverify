"""SPECT Step 22: explicit source-readiness and normal-output blockers."""
from types import SimpleNamespace

import pytest

from modalities.spect import SPECT_CALCULATION_BLOCK_REASON, SPECT_ISSUED_OUTPUT_BLOCK_REASON, spect_source_readiness_result
from services.export_eligibility import (
    apply_export_eligibility_to_payload,
    assess_export_eligibility,
    build_export_prompt_message,
)
from services.source_readiness import (
    validate_project_source_readiness,
    validate_room_source_readiness,
)


def _spect_room_and_source():
    room = SimpleNamespace(
        name="SPECT Room 1",
        modality="SPECT",
        modality_state={},
        sources=[],
    )
    source = SimpleNamespace(
        name="SPECT Patient Source",
        source_type="spect_patient",
        radiation_type="tc99m_140kev",
        params={},
    )
    return room, source


def _project_preflight():
    room, source = _spect_room_and_source()
    project = SimpleNamespace(rooms=[room], sources=[])
    return validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [source],
    )


def test_step22_spect_owned_readiness_contract_evolves_to_host_ready_output_blocking():
    result = spect_source_readiness_result(
        "spect_patient",
        {},
        {"room_name": "SPECT Room 1", "source_name": "SPECT Patient Source"},
    )

    assert result["overall_status"] == "REVIEW"
    assert result["status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["output_blocking"] is True
    assert result["basis"] == "production_host_results_only"
    assert result["errors"] == []
    assert result["warnings"] == [f"SPECT Room 1: {SPECT_ISSUED_OUTPUT_BLOCK_REASON}"]
    assert result["checks"][0]["status"] == "PASS"


def test_step22_room_readiness_is_host_nonblocking_but_output_blocking():
    room, source = _spect_room_and_source()
    result = validate_room_source_readiness(
        room,
        get_sources_for_room=lambda room_name: [source],
    )

    assert result["overall_status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["source_results"][0]["blocking"] is False
    assert result["source_results"][0]["output_blocking"] is True
    assert result["errors"] == []


def test_step22_project_readiness_is_host_nonblocking_but_output_blocking():
    result = _project_preflight()

    assert result["overall_status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["errors"] == []
    assert result["room_results"][0]["overall_status"] == "REVIEW"


@pytest.mark.parametrize("status", ["Draft", "Final"])
def test_step22_spect_blocks_pdf_csv_and_certification_for_all_normal_output(status):
    eligibility = assess_export_eligibility(
        preflight=_project_preflight(),
        requested_report_status=status,
    )

    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.allowed is False
    assert eligibility.blocking is True
    assert eligibility.requires_acknowledgement is True


def test_step22_room_level_preflight_also_hard_blocks_draft_pdf():
    room, source = _spect_room_and_source()
    room_preflight = validate_room_source_readiness(
        room,
        get_sources_for_room=lambda room_name: [source],
    )

    eligibility = assess_export_eligibility(
        preflight=room_preflight,
        requested_report_status="Draft",
    )
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False


def test_step22_payload_gate_marks_spect_incomplete_and_noncertifiable():
    payload = {
        "meta": {"report_status": "Draft"},
        "certification": {"certification_allowed": True, "signature_allowed": True},
    }
    eligibility = apply_export_eligibility_to_payload(
        payload,
        preflight=_project_preflight(),
        requested_report_status="Draft",
    )

    assert eligibility.can_export_pdf is False
    assert payload["export_eligibility"]["can_export_pdf"] is False
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["certification"]["certification_allowed"] is False
    assert payload["certification"]["signature_allowed"] is False


def test_step22_export_prompt_does_not_offer_a_draft_pdf_escape_hatch():
    eligibility = assess_export_eligibility(
        preflight=_project_preflight(),
        requested_report_status="Draft",
    )
    message = build_export_prompt_message(eligibility)

    assert "Normal PDF/CSV export and certification are blocked" in message
    assert "A Draft PDF can still be generated" not in message


def test_step22_generic_room_aggregator_synthesises_error_for_blocked_validator(monkeypatch):
    """Regression guard for the class of bug identified in Step 19."""

    room, source = _spect_room_and_source()

    monkeypatch.setattr(
        "services.source_readiness.source_readiness_result_for_source",
        lambda source_type, params, context: {
            "source_type": source_type,
            "source_name": context["source_name"],
            "overall_status": "BLOCKED",
            "status": "BLOCKED",
            "blocking": True,
            "message": "Synthetic modality block.",
            "errors": [],
            "warnings": [],
        },
    )

    result = validate_room_source_readiness(
        room,
        get_sources_for_room=lambda room_name: [source],
    )
    assert result["blocking"] is True
    assert result["overall_status"] == "FAIL"
    assert result["errors"] == ["SPECT Room 1: Synthetic modality block."]


def test_step22_does_not_change_ordinary_incomplete_draft_pdf_policy():
    """CT-style incomplete source data still follows the existing draft policy."""

    preflight = {
        "overall_status": "FAIL",
        "blocking": True,
        "errors": ["Missing ordinary source input"],
        "warnings": [],
        "room_results": [],
    }
    eligibility = assess_export_eligibility(
        preflight=preflight,
        requested_report_status="Draft",
    )

    assert eligibility.can_export_pdf is True
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
