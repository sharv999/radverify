from pathlib import Path

from geometry.geometry_model import RadiationSourceGeometry, RoomGeometry, WallBucky
from models.shielding_models import Barrier, Project, Room, Source, project_to_dict
from reports.report_generator import render_pdf_from_payload
from reports.results_payload_builder import build_results_payload
from services.project_io import load_project_from_file, write_project_payload
from services.xray_results_model import build_xray_results_model, XRAY_RESULTS_MODEL_VERSION

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


class _Var:
    def __init__(self, value=""): self.value=value
    def get(self): return self.value
class _App:
    def __init__(self, project):
        self.project=project; self.project_vars={}; self.global_energy_var=_Var("xray_120kvp"); self.solver_mode_var=_Var("auto")
    def get_sources_for_room(self, room_name): return [s for s in self.project.sources if s.room_name == room_name]
    def _row_confidence_from_live(self, *_args): return 1.0


def _project():
    g=RoomGeometry(room_name="GXR Fig52", length_m=6.0, width_m=5.0, height_m=3.0,
        source=RadiationSourceGeometry(label="General Radiography", x_m=2.0, y_m=2.5),
        wall_bucky=WallBucky(wall="N", offset_m=2.0))
    barriers=[
        Barrier(name="N chest bucky", material="Pb", thickness_mm=0.88, barrier_role="fig52_chest_bucky_wall", distance_m=2.5, occupancy_factor=0.2, design_goal_uSv_per_week=20.0),
        Barrier(name="S cross-table", material="Pb", thickness_mm=0.88, barrier_role="fig52_cross_table_wall", distance_m=2.8, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        Barrier(name="E control", material="Pb", thickness_mm=0.88, barrier_role="fig52_control_wall", distance_m=1.8, occupancy_factor=1.0, design_goal_uSv_per_week=100.0),
        Barrier(name="Floor", material="Concrete", thickness_mm=150.0, barrier_role="fig52_floor_under_table", distance_m=4.1, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
        Barrier(name="Ceiling", material="Concrete", thickness_mm=150.0, barrier_role="fig52_ceiling", distance_m=2.7, occupancy_factor=1.0, design_goal_uSv_per_week=20.0),
    ]
    room=Room(name="GXR Fig52", modality="X-ray", geometry=g, barriers=barriers)
    src=Source(name="General Radiography", source_type="xray_primary", radiation_type="xray_120kvp", room_name=room.name,
        params={"xray_method":"ncrp_simplified","exam_room_type":"general_radiography","exams_per_week":125,"tube_potential_kvp":120})
    return Project(project_name="XR08D Fig52", modality="X-ray", rooms=[room], sources=[src])


def test_xr08d_save_reopen_deterministic_fig52_replay(tmp_path):
    p=_project(); before=build_xray_results_model(p,p.rooms[0])
    path=write_project_payload(tmp_path/"xr08d.json", project_to_dict(p)); loaded=load_project_from_file(path)
    after=build_xray_results_model(loaded,loaded.rooms[0])
    assert project_to_dict(loaded)==project_to_dict(p)
    assert after==before
    assert all(r["results_model_version"]==XRAY_RESULTS_MODEL_VERSION and r["replay_verified"] for r in after)


def test_xr08d_results_expose_fig52_scenario_combination_and_preshielding():
    p=_project(); rows=build_xray_results_model(p,p.rooms[0])
    by_name={r["barrier"]:r for r in rows}
    cross=by_name["S cross-table"]
    assert cross["fig52_section"]=="5.3.5" and cross["fig52_combination"]=="joint"
    assert any(c["preshield"]=="grid_cassette" and c["preshield_mm"]==0.30 for c in cross["fig52_components"])
    floor=by_name["Floor"]
    assert floor["fig52_section"]=="5.3.1"
    assert any(c["preshield"]=="grid_cassette_support" and c["preshield_mm"]==72.0 for c in floor["fig52_components"])


def test_xr08e_report_payload_is_exactly_canonical_and_issueable():
    p=_project(); canonical=build_xray_results_model(p,p.rooms[0]); payload=build_results_payload(_App(p), report_status="QUALIFICATION - NON-ISSUEABLE")
    room=payload["rooms"][0]; q=room["xray_report_qualification"]
    assert q["fig52_requalification_version"]=="xr08e-issueable-project-fig52-v1"
    assert q["project_specific_geometry"] is True and q["issued_output_enabled"] is True
    for report_row,result_row in zip(room["barriers"],canonical):
        for key in ("unshielded_weekly_dose_uSv","transmitted_dose_uSv_per_week","required_thickness_mm","solver_used"):
            assert report_row[key]==result_row[key]
    assert payload["export_eligibility"]["can_export_pdf"] is True
    assert payload["export_eligibility"]["can_export_csv"] is True
    assert payload["export_eligibility"]["can_certify"] is True


def test_xr08d_rendered_pdf_discloses_s53_fig52_basis_and_nonissueable_state(tmp_path):
    p=_project(); payload=build_results_payload(_App(p), report_status="QUALIFICATION - NON-ISSUEABLE")
    path=tmp_path/"xr08d.pdf"; render_pdf_from_payload(payload,path)
    assert path.read_bytes().startswith(b"%PDF-") and path.stat().st_size>5000
    if PdfReader is not None:
        text="\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        assert "Section 5.3 / Figure 5.2" in text
        assert "project-specific barrier distances" in text
        assert "cross-table lateral shielding combines transmitted primary and secondary" in text.lower()
        assert "QUALIFICATION - NON-ISSUEABLE" in text
