from services.export_eligibility import apply_export_eligibility_to_payload
from services.payload_integrity import (
    BARRIER_RESULT_COUNT_MISMATCH_REASON,
    OPENING_EXPORT_OMISSION_REASON,
    ROOM_CALCULATION_FAILED_REASON,
    build_payload_calculation_integrity,
)


def _payload_with_room(**room_overrides):
    room = {
        "name": "CT Room 1",
        "error": "",
        "wall_count_expected": 4,
        "wall_result_count": 4,
        "opening_count_expected": 0,
        "opening_count_exported": 0,
        "barriers": [
            {"name": "N wall", "barrier_element_type": "Wall"},
            {"name": "E wall", "barrier_element_type": "Wall"},
            {"name": "S wall", "barrier_element_type": "Wall"},
            {"name": "W wall", "barrier_element_type": "Wall"},
        ],
    }
    room.update(room_overrides)
    return {"rooms": [room]}


def test_payload_integrity_passes_complete_room_payload():
    integrity = build_payload_calculation_integrity(_payload_with_room())

    assert integrity["calculation_complete"] is True
    assert integrity["blocking"] is False
    assert integrity["blocking_reasons"] == []
    assert integrity["wall_count_expected"] == 4
    assert integrity["wall_result_count"] == 4


def test_payload_integrity_blocks_room_calculation_error():
    integrity = build_payload_calculation_integrity(
        _payload_with_room(error="CT scanner ksec is NULL/missing")
    )

    assert integrity["calculation_complete"] is False
    assert integrity["blocking"] is True
    assert integrity["blocking_reasons"] == [ROOM_CALCULATION_FAILED_REASON]
    assert integrity["room_issues"][0]["issue"] == "room_calculation_failed"


def test_payload_integrity_blocks_wall_result_count_mismatch():
    integrity = build_payload_calculation_integrity(
        _payload_with_room(wall_count_expected=6, wall_result_count=4)
    )

    assert integrity["calculation_complete"] is False
    assert integrity["blocking_reasons"] == [BARRIER_RESULT_COUNT_MISMATCH_REASON]
    assert integrity["room_issues"][0]["issue"] == "wall_result_count_mismatch"


def test_payload_integrity_blocks_missing_opening_rows():
    integrity = build_payload_calculation_integrity(
        _payload_with_room(opening_count_expected=2, opening_count_exported=1)
    )

    assert integrity["calculation_complete"] is False
    assert integrity["blocking_reasons"] == [OPENING_EXPORT_OMISSION_REASON]
    assert integrity["room_issues"][0]["issue"] == "opening_export_omission"


def test_export_eligibility_uses_payload_integrity_to_block_csv_and_certification():
    payload = {
        "meta": {"report_status": "Draft"},
        "source_readiness": {"blocking": False, "overall_status": "PASS", "errors": [], "warnings": []},
        "calculation_integrity": build_payload_calculation_integrity(
            _payload_with_room(wall_count_expected=6, wall_result_count=4)
        ),
        "certification": {"certification_allowed": True, "signature_allowed": True},
    }

    eligibility = apply_export_eligibility_to_payload(payload, requested_report_status="Draft")

    assert eligibility.can_export_pdf is True
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
    assert eligibility.blocking_reasons == [BARRIER_RESULT_COUNT_MISMATCH_REASON]
    assert payload["certification"]["assessment_status"] == "INCOMPLETE"


def test_export_eligibility_blocks_final_pdf_when_payload_integrity_fails():
    payload = {
        "meta": {"report_status": "Final"},
        "source_readiness": {"blocking": False, "overall_status": "PASS", "errors": [], "warnings": []},
        "calculation_integrity": build_payload_calculation_integrity(
            _payload_with_room(error="calculation failed")
        ),
    }

    eligibility = apply_export_eligibility_to_payload(payload, requested_report_status="Final")

    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.blocking_reasons == [ROOM_CALCULATION_FAILED_REASON]
