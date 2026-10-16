from geometry.geometry_model import BuckyShield, RoomGeometry, WallBucky
from tabs.barriers_openings import _opening_display_status_from_live


def test_xr19a_bucky_shield_defaults_are_fixed_1p2m_2p2mm_pb():
    shield = BuckyShield()
    assert shield.width_m == 1.2
    assert shield.material == "Pb"
    assert shield.thickness_mm == 2.2


def test_xr19a_bucky_shield_round_trips_with_room_geometry():
    geom = RoomGeometry(room_name="GXR", wall_bucky=WallBucky(wall="E", offset_m=2.3),
                        bucky_shield=BuckyShield(wall="E", offset_m=2.3))
    reopened = RoomGeometry.from_dict(geom.to_dict())
    assert reopened.bucky_shield is not None
    assert reopened.bucky_shield.wall == "E"
    assert reopened.bucky_shield.offset_m == 2.3
    assert reopened.bucky_shield.width_m == 1.2
    assert reopened.bucky_shield.thickness_mm == 2.2


def test_xr19a1_legacy_chest_bucky_without_shield_reopens_unchanged():
    geom = RoomGeometry(room_name="GXR", wall_bucky=WallBucky(wall="W", offset_m=1.7))
    data = geom.to_dict()
    assert data["bucky_shield"] is None
    reopened = RoomGeometry.from_dict(data)
    assert reopened.bucky_shield is None
    assert reopened.to_dict() == data


def test_xr19a_gxr_opening_pass_is_not_promoted_to_review_only_for_small_margin():
    live = {"compliance_status": "PASS", "margin_mm": 0.12}
    assert _opening_display_status_from_live(live, conservative_margin=False) == "PASS"
    # Preserve the established conservative display policy for other modalities.
    assert _opening_display_status_from_live(live, conservative_margin=True) == "REVIEW"


def test_xr19a_chest_bucky_update_owns_and_removes_bucky_shield():
    text = open("tabs/geometry_tab.py", encoding="utf-8").read()
    assert "g.bucky_shield = BuckyShield(wall=wall, offset_m=offset)" in text
    assert "g.bucky_shield = None" in text
