from modalities.xray import (
    XRAY_FIG52_REQUALIFICATION_BLOCK_REASON,
    xray_source_readiness_result,
)
from models.shielding_models import Project, Room, Source
from services.export_eligibility import assess_export_eligibility
from services.source_readiness import validate_project_source_readiness


def _source(method="ncrp_simplified", room_type="general_radiography"):
    return Source(
        name="General Radiography",
        source_type="xray_primary",
        radiation_type="xray_120kvp",
        room_name="X-ray Room 1",
        params={"xray_method": method, "exam_room_type": room_type, "exams_per_week": 125},
    )


def _project(source):
    room = Room(name="X-ray Room 1", modality="X-ray", sources=[source])
    return Project(project_name="XR-07 KAT", modality="X-ray", rooms=[room], sources=[source])


def test_xr08e_general_radiography_source_release_gate_passes():
    src = _source()
    result = xray_source_readiness_result(src.source_type, src.params, {"room_name": src.room_name, "source_name": src.name})
    assert result["status"] == "PASS"
    assert result["output_blocking"] is False
    assert result["basis"] == "ncrp147_general_radiography_issueable"


def test_xr08e_general_radiography_source_readiness_no_longer_blocks_outputs():
    src = _source()
    project = _project(src)
    readiness = validate_project_source_readiness(project, get_sources_for_room=lambda name: [src])
    assert readiness["blocking"] is False
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Draft")
    assert eligibility.can_export_pdf is True
    assert eligibility.blocking is False


def test_xr07_manual_xray_remains_fail_closed():
    src = _source(method="manual")
    project = _project(src)
    readiness = validate_project_source_readiness(project, get_sources_for_room=lambda name: [src])
    assert readiness["blocking"] is True
    assert readiness["source_results"][0]["output_blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Draft")
    assert eligibility.can_export_pdf is False


def test_xr07_unsupported_xray_room_preset_remains_fail_closed():
    src = _source(room_type="trauma_emergency")
    result = xray_source_readiness_result(src.source_type, src.params, {"room_name": src.room_name, "source_name": src.name})
    assert result["status"] == "BLOCKED"
    assert result["output_blocking"] is True
