from reports.results_payload_builder import build_results_payload
from tests.test_xray_xr08d_results_report_requalification import _App, _project
from tests.test_xray_xr05_persistence_results import _project as _legacy_project


def test_xr08e_project_specific_fig52_payload_is_issueable():
    p = _project()
    payload = build_results_payload(_App(p), report_status="Draft")
    q = payload["rooms"][0]["xray_report_qualification"]
    assert q["fig52_requalification_version"] == "xr08e-issueable-project-fig52-v1"
    assert q["project_specific_geometry"] is True
    assert q["issued_output_enabled"] is True
    assert payload["export_eligibility"]["can_export_pdf"] is True
    assert payload["export_eligibility"]["can_export_csv"] is True
    assert payload["export_eligibility"]["can_certify"] is True


def test_xr08e_legacy_xray_roles_remain_fail_closed():
    p = _legacy_project()
    payload = build_results_payload(_App(p), report_status="Draft")
    q = payload["rooms"][0]["xray_report_qualification"]
    assert q["issued_output_enabled"] is False
    assert payload["calculation_integrity"]["blocking"] is True
    assert any(i["issue"] == "xray_fig52_release_gate" for i in payload["calculation_integrity"]["room_issues"])
    assert payload["export_eligibility"]["can_export_pdf"] is False
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["export_eligibility"]["can_certify"] is False
