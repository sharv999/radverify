from services.report_certification import build_report_certification_state


def _payload(summary=None, source_readiness=None, report_status="Draft"):
    return {
        "meta": {"report_status": report_status},
        "summary": summary or {
            "fail_count": 0,
            "review_count": 0,
            "source_ksec_incomplete_count": 0,
            "source_ksec_manual_override_count": 0,
        },
        "source_readiness": source_readiness or {
            "blocking": False,
            "errors": [],
            "warnings": [],
        },
    }


def test_certification_gate_blocks_incomplete_source_inputs():
    cert = build_report_certification_state(_payload(
        summary={
            "fail_count": 0,
            "review_count": 0,
            "source_ksec_incomplete_count": 1,
            "source_ksec_manual_override_count": 0,
        },
        source_readiness={"blocking": True, "errors": ["Missing CT ksec"], "warnings": []},
    ))

    assert not cert["certification_allowed"]
    assert not cert["signature_allowed"]
    assert cert["assessment_status"] == "INCOMPLETE"
    assert "NOT FOR CERTIFICATION" in cert["label"]


def test_certification_gate_blocks_draft_even_when_pass():
    cert = build_report_certification_state(_payload(report_status="Draft"))

    assert not cert["certification_allowed"]
    assert cert["assessment_status"] == "PASS"
    assert "DRAFT" in cert["label"]


def test_certification_gate_allows_final_clean_pass():
    cert = build_report_certification_state(_payload(report_status="Final"))

    assert cert["certification_allowed"]
    assert cert["signature_allowed"]
    assert cert["label"] == "CERTIFIED PASS"


def test_certification_gate_manual_override_requires_review():
    cert = build_report_certification_state(_payload(
        summary={
            "fail_count": 0,
            "review_count": 0,
            "source_ksec_incomplete_count": 0,
            "source_ksec_manual_override_count": 1,
        },
        report_status="Final",
    ))

    assert not cert["certification_allowed"]
    assert cert["assessment_status"] == "REVIEW"
    assert "REVIEW" in cert["label"]
