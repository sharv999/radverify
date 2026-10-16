from services.export_eligibility import assess_export_eligibility


def test_top_level_legacy_preflight_error_text_is_preserved():
    result = assess_export_eligibility(
        preflight={
            "blocking": True,
            "overall_status": "FAIL",
            "errors": ["Missing CT ksec"],
            "warnings": [],
        },
        requested_report_status="Draft",
    )

    assert result.blocking_reasons == ["Missing CT ksec"]
    assert result.can_export_pdf is True
    assert result.can_export_csv is False


def test_structured_null_ksec_source_uses_canonical_block_reason():
    result = assess_export_eligibility(
        preflight={
            "blocking": True,
            "overall_status": "FAIL",
            "errors": [],
            "warnings": [],
            "room_results": [
                {
                    "source_results": [
                        {
                            "ksec_basis": "manual_override_required",
                            "errors": ["CT scanner ksec is missing"],
                        }
                    ]
                }
            ],
        },
        requested_report_status="Draft",
    )

    assert result.blocking_reasons == ["BLOCKED: selected CT scanner has NULL/missing ksec."]
