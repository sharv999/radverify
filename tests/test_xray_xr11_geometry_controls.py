from geometry.default_room_geometry import create_default_room_geometry
from geometry.geometry_model import ControlWall, RoomGeometry
from models.shielding_models import Project, Room, Source


def _room():
    g = create_default_room_geometry('X-ray Room 1', 'X-ray')
    r = Room(name='X-ray Room 1', modality='X-ray', geometry=g, barriers=[])
    p = Project(project_name='XR11', modality='X-ray', rooms=[r], sources=[Source(name='General Radiography', source_type='xray_primary', radiation_type='xray_120kvp', room_name=r.name, params={'xray_method':'ncrp_simplified','exam_room_type':'general_radiography','exams_per_week':125,'tube_potential_kvp':120})])
    return p, r


def test_xr11_control_wall_round_trips_with_geometry():
    g = create_default_room_geometry('X-ray Room 1', 'X-ray')
    g.control_wall = ControlWall(center_x_m=1.2, center_y_m=2.4, length_m=1.8, orientation_deg=90)
    restored = RoomGeometry.from_dict(g.to_dict())
    assert restored.control_wall == g.control_wall
    assert restored.wall_bucky == g.wall_bucky


def test_xr11_control_wall_is_a_fig52_control_barrier_at_placed_distance():
    from geometry.barrier_sync import apply_geometry_to_selected_room_barriers
    p, room = _room()
    room.geometry.source.x_m = 2.0
    room.geometry.source.y_m = 2.0
    room.geometry.control_wall = ControlWall(center_x_m=3.0, center_y_m=2.0, length_m=1.5)

    class App:
        project = p
        def create_default_room_geometry(self, name, modality): return create_default_room_geometry(name, modality)
        def _coerce_barrier_schema(self, b): return b
        def enforce_room_source_types(self, r): return None

    apply_geometry_to_selected_room_barriers(App(), room)
    control = next(b for b in room.barriers if b.barrier_role == 'fig52_control_wall')
    assert control.name == 'Control wall'
    # XR-15B: shortest distance to the finite wall segment (centre distance was 1.0 m).
    assert control.distance_m == 0.25
    assert control.occupancy_factor == 1.0
    assert control.design_goal_uSv_per_week == 100.0


def test_xr11_xray_role_labels_are_explicit_in_geometry_canvas_source():
    import inspect
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab.draw_room_with_risk)
    assert 'PRIMARY — chest bucky' in text
    assert 'PRIMARY + SECONDARY — cross-table' in text
    assert 'SECONDARY — control wall' in text
    assert 'PRIMARY + SECONDARY — floor' in text


def test_xr11a_gxr_geometry_controls_are_gated_by_modality_and_room_type_not_canvas_label():
    import inspect
    from tabs.geometry_tab import GeometryTab
    text = inspect.getsource(GeometryTab._update_source_control_visibility)
    assert 'modality_id.upper() == "X-RAY"' in text
    assert 'room_type == "General Radiography"' in text
    assert 'getattr(geometry_ui, "source_label"' not in text


def test_xr11b_gxr_geometry_controls_use_chest_bucky_and_jog_fields():
    import inspect
    from tabs.geometry_tab import GeometryTab
    init_text = inspect.getsource(GeometryTab._build_ui)
    assert 'text="Chest Bucky"' in init_text
    assert 'text="Control Wall"' in init_text
    assert 'Distance along wall (m)' in init_text
    assert 'From West wall (m)' in init_text
    assert 'From North wall (m)' in init_text
    assert 'Remove chest bucky' in init_text
    assert hasattr(GeometryTab, 'remove_xray_chest_bucky')
    assert hasattr(GeometryTab, 'nudge_xray_chest_bucky')
    assert hasattr(GeometryTab, 'nudge_xray_control_wall')
