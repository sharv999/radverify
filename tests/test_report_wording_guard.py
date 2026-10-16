from services.report_wording_guard import build_report_wording_state


def _payload(summary=None, source_readiness=None, report_status="Draft", export_eligibility=None, calculation_integrity=None):
    return {
        "meta": {"report_status": report_status},
        "summary": summary or {
            "fail_count": 0,
            "review_count": 0,
            "source_ksec_incomplete_count": 0,
            "source_ksec_manual_override_count": 0,
        },
        "source_readiness": source_readiness or {"blocking": False, "errors": [], "warnings": []},
        "export_eligibility": export_eligibility or {},
        "calculation_integrity": calculation_integrity or {},
    }


def test_wording_blocks_calculation_integrity_from_certification():
    wording = build_report_wording_state(_payload(
        report_status="Final",
        calculation_integrity={
            "calculation_complete": False,
            "blocking": True,
            "blocking_reasons": ["BLOCKED: barrier result count does not match the room barrier schedule."],
        },
    ))

    assert wording["assessment_status"] == "INCOMPLETE"
    assert wording["certification_allowed"] is False
    assert wording["signature_allowed"] is False
    assert "NOT FOR CERTIFICATION" in wording["label"]
    assert "barrier result count" in " ".join(wording["blocking_issues"])


def test_wording_blocks_export_gate_from_final_certificate():
    wording = build_report_wording_state(_payload(
        report_status="Final",
        export_eligibility={
            "can_certify": False,
            "blocking": True,
            "blocking_reasons": ["BLOCKED: selected CT scanner has NULL/missing ksec."],
        },
    ))

    assert wording["assessment_status"] == "INCOMPLETE"
    assert wording["certification_allowed"] is False
    assert "NULL/missing ksec" in " ".join(wording["blocking_issues"])


def test_wording_manual_ksec_override_requires_review_even_if_final_requested():
    wording = build_report_wording_state(_payload(
        report_status="Final",
        summary={
            "fail_count": 0,
            "review_count": 0,
            "source_ksec_incomplete_count": 0,
            "source_ksec_manual_override_count": 1,
        },
    ))

    assert wording["assessment_status"] == "REVIEW"
    assert wording["certification_allowed"] is False
    assert "REVIEW" in wording["label"]
    assert "Manual CT ksec override" in " ".join(wording["mandatory_disclaimers"])


def test_wording_clean_draft_pass_is_not_final_certification():
    wording = build_report_wording_state(_payload(report_status="Draft"))

    assert wording["assessment_status"] == "PASS"
    assert wording["certification_allowed"] is False
    assert "DRAFT" in wording["label"]


def test_wording_clean_final_pass_can_certify():
    wording = build_report_wording_state(_payload(report_status="Final"))

    assert wording["assessment_status"] == "PASS"
    assert wording["certification_allowed"] is True
    assert wording["signature_allowed"] is True
    assert wording["label"] == "CERTIFIED PASS"
