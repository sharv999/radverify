import pytest
from engine.shielding_engine import default_barriers
from engine.xray_ncrp147_fig52 import structural_transmission_factor
from engine.xray_ncrp147_project_geometry import scenario_for_project_barrier, _scenario_with_bucky_shield
from geometry.geometry_model import RoomGeometry, RadiationSourceGeometry, WallBucky, BuckyShield
from models.shielding_models import Project, Room, Source

def _project():
    room=Room(name="X-ray Room 1",modality="X-RAY",barriers=default_barriers())
    room.geometry=RoomGeometry(room_name=room.name,length_m=6.0,width_m=4.0,source=RadiationSourceGeometry(label="General Radiography",x_m=2.0,y_m=3.0),wall_bucky=WallBucky(wall="N",offset_m=2.0),bucky_shield=BuckyShield(wall="N",offset_m=2.0))
    b=room.barriers[0]; b.name="N wall"; b.barrier_role="fig52_chest_bucky_wall"; b.distance_m=3.0
    src=Source(name="General Radiography",room_name=room.name,source_type="xray_primary",params={"xray_method":"ncrp_simplified","exam_room_type":"general_radiography","exams_per_week":125})
    return Project(project_name="XR19B",modality="X-ray",rooms=[room],sources=[src]),room,b

def test_bucky_shield_credits_primary_only():
    p,r,b=_project(); s=scenario_for_project_barrier(p,r,b); out,applied,factor=_scenario_with_bucky_shield(r,b,s)
    assert applied
    assert factor==pytest.approx(structural_transmission_factor("primary","chest_bucky",2.2,"Pb"))
    before={c.name:c.unshielded_mGy_week for c in s.components}; after={c.name:c.unshielded_mGy_week for c in out.components}
    assert after["primary_chest_bucky"]==pytest.approx(before["primary_chest_bucky"]*factor)
    secondary_factor = structural_transmission_factor("secondary", "chest_bucky", 2.2, "Pb")
    assert after["secondary_chest_bucky"]==pytest.approx(before["secondary_chest_bucky"]*secondary_factor)

def test_missing_or_misaligned_shield_gets_no_credit():
    p,r,b=_project(); s=scenario_for_project_barrier(p,r,b); r.geometry.bucky_shield=None
    assert _scenario_with_bucky_shield(r,b,s)[1:]==(False,1.0)
    r.geometry.bucky_shield=BuckyShield(wall="E",offset_m=2.0)
    assert _scenario_with_bucky_shield(r,b,s)[1:]==(False,1.0)

def test_new_gxr_seed_contract_is_pb_0p88():
    text=open("geometry/barrier_sync.py",encoding="utf-8").read()
    assert 'if seed_xray_fig52_roles:' in text and 'b.material = "Pb"' in text and 'b.thickness_mm = 0.88' in text
