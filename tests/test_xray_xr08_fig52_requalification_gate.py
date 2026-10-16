from modalities.xray import XRAY_PLUGIN, xray_source_readiness_result


def test_xr08_production_ui_exposes_general_radiography_only():
    assert XRAY_PLUGIN.EXAM_ROOM_TYPE_VALUES == ("general_radiography",)


def test_xr08e_fig52_requalification_releases_qualified_source_route():
    result = xray_source_readiness_result(
        "xray_primary",
        {"xray_method": "ncrp_simplified", "exam_room_type": "general_radiography", "exams_per_week": 125},
        {"room_name": "X-ray Room 1", "source_name": "General Radiography"},
    )
    assert result["status"] == "PASS"
    assert result["output_blocking"] is False
    assert result["basis"] == "ncrp147_general_radiography_issueable"
