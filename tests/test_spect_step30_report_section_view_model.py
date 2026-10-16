from copy import deepcopy
from pathlib import Path
import pytest
from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state,set_room_spect_working_state
from services.spect_results_model import build_room_results_model
from services.spect_source_summary_harness import build_non_issueable_spect_source_summary
from services.spect_report_payload_harness import build_non_issueable_spect_report_payload
from services.spect_report_section_view_model import (
    SPECT_BARRIER_TABLE_FIELDS,SPECT_PROVENANCE_DISPLAY_FIELDS,SPECT_REPORT_SECTION_HEADINGS,
    SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE,SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION,
    SPECT_REPORT_SECTION_WARNINGS,SPECT_SOURCE_DISPLAY_FIELDS,SpectReportSectionViewModelError,
    build_non_issueable_spect_report_section_view_model,
)


def _payloads(lead=1.0):
    room=Room(name="SPECT Room",modality="SPECT",barriers=[Barrier(name="North wall",material="Pb",material_legacy=f"Pb {lead} mm",thickness_mm=lead,distance_m=2.0,occupancy_factor=1.0,design_goal_uSv_per_week=1.0),Barrier(name="South wall",material="Concrete",material_legacy="Concrete 150 mm",thickness_mm=150.0,distance_m=3.0,occupancy_factor=0.25,design_goal_uSv_per_week=10.0)])
    set_room_spect_working_state(room,new_spect_working_project_state(SpectSourceDomain("Tc99m",600.0,20.0,0.5)))
    rows=build_room_results_model(Project(project_name="SPECT",rooms=[room]),room,fallback_results=[])
    return build_non_issueable_spect_source_summary(room),build_non_issueable_spect_report_payload(rows)


def test_step30_freezes_headings_warnings_fields_and_wording():
    source,barrier=_payloads(); view=build_non_issueable_spect_report_section_view_model(source_payload=source,barrier_payload=barrier)
    assert view["view_model_contract_version"] == SPECT_REPORT_SECTION_VIEW_MODEL_CONTRACT_VERSION
    assert view["view_model_baseline"] == SPECT_REPORT_SECTION_VIEW_MODEL_BASELINE
    assert view["headings"] == dict(SPECT_REPORT_SECTION_HEADINGS)
    assert view["warnings"] == list(SPECT_REPORT_SECTION_WARNINGS)
    assert view["source_summary"]["field_order"] == list(SPECT_SOURCE_DISPLAY_FIELDS)
    assert view["barrier_table"]["field_order"] == list(SPECT_BARRIER_TABLE_FIELDS)
    assert view["provenance"]["field_order"] == list(SPECT_PROVENANCE_DISPLAY_FIELDS)
    assert view["barrier_table"]["columns"][-2]["label"] == "Assessment status"
    assert all("certified" not in warning.lower() for warning in view["warnings"])


def test_step30_formats_deterministically_and_suppresses_nonreportable_dose():
    source,barrier=_payloads(3.0); view=build_non_issueable_spect_report_section_view_model(source_payload=source,barrier_payload=barrier)
    assert view == build_non_issueable_spect_report_section_view_model(source_payload=source,barrier_payload=barrier)
    assert view["source_summary"]["rows"][1]["value"] == "600.000"
    assert len(view["barrier_table"]["rows"][0]["barrier_transmission_factor_B"].split(".")[1]) == 6
    assert view["barrier_table"]["rows"][0]["transmitted_dose_uSv_per_week"] == "Not reported"


def test_step30_fails_closed_for_open_drifted_or_mismatched_payloads():
    source,barrier=_payloads()
    opened=deepcopy(source); opened["report_integration_open"]=True
    with pytest.raises(SpectReportSectionViewModelError,match="not closed"):
        build_non_issueable_spect_report_section_view_model(source_payload=opened,barrier_payload=barrier)
    drifted=deepcopy(barrier); drifted["barriers"][0]["unexpected"]="x"
    with pytest.raises(SpectReportSectionViewModelError,match="30-field"):
        build_non_issueable_spect_report_section_view_model(source_payload=source,barrier_payload=drifted)
    mismatch=deepcopy(source); mismatch["source_summary"]["physics_freeze"]["freeze_id"]="wrong"
    with pytest.raises(SpectReportSectionViewModelError,match="physics freeze"):
        build_non_issueable_spect_report_section_view_model(source_payload=mismatch,barrier_payload=barrier)


def test_step30_remains_disconnected_from_issueable_outputs():
    token="spect_report_section_view_model"
    for path in list(Path("reports").glob("*.py"))+[Path("services/export_eligibility.py"),Path("services/report_certification.py"),Path("reports/output_pipeline.py"),Path("reports/results_exporter.py")]:
        assert token not in path.read_text(encoding="utf-8-sig")
    text=Path("services/spect_report_section_view_model.py").read_text(encoding="utf-8")
    for forbidden in ("reportlab","openpyxl","json.dump","Path(","open(","reports."):
        assert forbidden not in text
