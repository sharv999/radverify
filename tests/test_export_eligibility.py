from types import SimpleNamespace

from services.source_readiness import (
    PET_WORKING_STATE_BLOCK_REASON,
    validate_project_source_readiness,
)
from services.export_eligibility import (
    NULL_KSEC_BLOCK_REASON,
    apply_export_eligibility_to_payload,
    assess_export_eligibility,
    build_export_prompt_message,
)


def _null_ksec_preflight():
    return {
        "overall_status": "FAIL",
        "blocking": True,
        "errors": ["CT scanner ksec is NULL/missing for selected scanner"],
        "warnings": [],
        "room_results": [
            {
                "room_name": "CT Room 1",
                "source_results": [
                    {
                        "source_name": "Secondary scatter source diagnostic",
                        "source_type": "ct_scatter",
                        "ksec_basis": "manual_override_required",
                        "errors": ["Manual override required for NULL ksec"],
                        "warnings": [],
                    }
                ],
            }
        ],
    }


def test_null_ksec_blocks_csv_and_certification_but_allows_incomplete_draft_pdf():
    eligibility = assess_export_eligibility(
        preflight=_null_ksec_preflight(),
        requested_report_status="Draft",
    )

    assert eligibility.can_export_pdf is True
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.requires_acknowledgement is True
    assert eligibility.report_status_effective == "Draft — Incomplete Source Data"
    assert eligibility.blocking_reasons == [NULL_KSEC_BLOCK_REASON]


def test_null_ksec_blocks_final_pdf():
    eligibility = assess_export_eligibility(
        preflight=_null_ksec_preflight(),
        requested_report_status="Final",
    )

    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.blocking_reasons == [NULL_KSEC_BLOCK_REASON]


def test_apply_export_eligibility_marks_payload_and_certificate_incomplete():
    payload = {
        "meta": {"report_status": "Draft"},
        "certification": {"certification_allowed": True, "signature_allowed": True},
    }

    eligibility = apply_export_eligibility_to_payload(
        payload,
        preflight=_null_ksec_preflight(),
        requested_report_status="Draft",
    )

    assert payload["export_eligibility"] == eligibility.to_dict()
    assert payload["meta"]["report_status_effective"] == "Draft — Incomplete Source Data"
    assert payload["certification"]["assessment_status"] == "INCOMPLETE"
    assert payload["certification"]["label"] == "INCOMPLETE — NOT FOR CERTIFICATION"
    assert payload["certification"]["certification_allowed"] is False
    assert payload["certification"]["signature_allowed"] is False
    assert payload["certification"]["blocking_issues"] == [NULL_KSEC_BLOCK_REASON]


def test_clean_preflight_allows_all_outputs():
    eligibility = assess_export_eligibility(
        preflight={"overall_status": "PASS", "blocking": False, "errors": [], "warnings": []},
        requested_report_status="Final",
    )

    assert eligibility.allowed is True
    assert eligibility.can_export_pdf is True
    assert eligibility.can_export_csv is True
    assert eligibility.can_certify is True
    assert eligibility.report_status_effective == "Final"


def test_prompt_uses_same_blocking_reason():
    eligibility = assess_export_eligibility(
        preflight=_null_ksec_preflight(),
        requested_report_status="Draft",
    )
    message = build_export_prompt_message(eligibility)

    assert NULL_KSEC_BLOCK_REASON in message
    assert "machine-readable exports" in message


def test_persisted_pet_working_state_blocks_machine_export_and_certification():
    room = SimpleNamespace(
        name="CT Room 1",
        modality="CT",
        modality_state={"pet_single_source": {"schema": "radshield_pet_working_source_v2"}},
    )
    source = SimpleNamespace(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_140kvp",
        params={
            "scanner_family": "GE_APEX",
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex",
            "scanner_kvp": 140,
            "ksec_energy_kvp": 140,
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "scanner_source": "JSON worst-case Ksec lookup",
        },
    )
    project = SimpleNamespace(rooms=[room], sources=[])
    preflight = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [source],
    )

    eligibility = assess_export_eligibility(
        preflight=preflight,
        requested_report_status="Final",
    )

    assert preflight["blocking"] is False
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert PET_WORKING_STATE_BLOCK_REASON in eligibility.blocking_reasons[0]
