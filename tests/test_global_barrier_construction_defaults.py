from engine.shielding_engine import default_barriers
from geometry.geometry_model import Opening
from geometry.room_defaults import get_barrier_default


def test_all_supported_modalities_share_standard_construction_defaults():
    for modality in ("CT", "SPECT/CT", "X-ray"):
        wall = get_barrier_default(modality, "wall")
        door = get_barrier_default(modality, "door")
        panel = get_barrier_default(modality, "viewing_panel")
        floor = get_barrier_default(modality, "floor")
        ceiling = get_barrier_default(modality, "ceiling")
        assert (wall["material"], wall["pb_mm"]) == ("Pb", 0.88)
        assert (door["material"], door["pb_mm"]) == ("Pb", 0.88)
        assert panel["pb_mm"] == 2.20
        assert floor["material"] == "150 mm solid concrete"
        assert ceiling["material"] == "150 mm solid concrete"


def test_default_room_barriers_are_pb_walls_and_150_mm_concrete_slabs():
    barriers = {b.name: b for b in default_barriers()}
    for name in ("N wall", "E wall", "S wall", "W wall"):
        assert barriers[name].material == "Pb"
        assert barriers[name].thickness_mm == 0.88
    for name in ("Floor", "Ceiling"):
        assert barriers[name].material == "Concrete"
        assert barriers[name].thickness_mm == 150.0


def test_opening_model_defaults_match_standard_door_construction():
    opening = Opening()
    assert opening.opening_type == "door"
    assert opening.material == "Pb"
    assert opening.pb_equiv_mm == 0.88
