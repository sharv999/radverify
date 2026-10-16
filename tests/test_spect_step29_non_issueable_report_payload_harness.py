from copy import deepcopy
import pytest
from models.shielding_models import Barrier, Project, Room
from modalities.spect import SpectSourceDomain
from serialization.spect_working_project_state import new_spect_working_project_state, set_room_spect_working_state
from services.spect_results_model import build_room_results_model
from services.spect_source_summary_harness import build_non_issueable_spect_source_summary
from services.spect_report_payload_harness import build_non_issueable_spect_report_payload, SpectReportPayloadHarnessError


def _data(lead=1.0):
    room=Room(name="SPECT Room", modality="SPECT", barriers=[Barrier(name="North wall",material="Pb",material_legacy=f"Pb {lead} mm",thickness_mm=lead,distance_m=2.0,occupancy_factor=1.0,design_goal_uSv_per_week=1.0), Barrier(name="South wall",material="Concrete",material_legacy="Concrete 150 mm",thickness_mm=150.0,distance_m=3.0,occupancy_factor=0.25,design_goal_uSv_per_week=10.0)])
    set_room_spect_working_state(room,new_spect_working_project_state(SpectSourceDomain("Tc99m",600.0,20.0,0.5)))
    project=Project(project_name="SPECT",rooms=[room])
    return room, build_room_results_model(project,room,fallback_results=[])


def test_step29_builds_closed_source_and_barrier_harnesses():
    room,rows=_data()
    source=build_non_issueable_spect_source_summary(room); barrier=build_non_issueable_spect_report_payload(rows)
    assert source["non_issueable"] is True and source["report_integration_open"] is False
    assert barrier["non_issueable"] is True and barrier["report_integration_open"] is False
    assert source["source_summary"]["physics_freeze"] == barrier["shared_provenance"]["physics_freeze"]
    assert barrier["barrier_count"] == 2 and barrier["permitted_field_count"] == 30


def test_step29_rejects_mixed_provenance_and_nonreportable_dose_leak():
    _room,rows=_data()
    mixed=deepcopy(rows); mixed[1]["request_sha256"]="0"*64
    with pytest.raises(SpectReportPayloadHarnessError, match="provenance"):
        build_non_issueable_spect_report_payload(mixed)
    _room,rows=_data(3.0); assert rows[0]["transmitted_dose_reportable"] is False
    leaked=deepcopy(rows); leaked[0]["transmitted_dose_uSv_per_week"]=0.001
    with pytest.raises(SpectReportPayloadHarnessError, match="non-reportable"):
        build_non_issueable_spect_report_payload(leaked)
