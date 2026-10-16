from pathlib import Path

from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from geometry.pet_preview_overlay import (
    PET_GEOMETRY_OVERLAY_BASELINE,
    PET_GEOMETRY_OVERLAY_CONTRACT_VERSION,
    build_pet_geometry_overlay,
    draw_pet_geometry_preview_overlay,
    wall_key_for_preview_name,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.calls.append(("oval", args, kwargs))
        return len(self.calls)

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", args, kwargs))
        return len(self.calls)

    def create_line(self, *args, **kwargs):
        self.calls.append(("line", args, kwargs))
        return len(self.calls)

    def tag_raise(self, *args, **kwargs):
        self.calls.append(("raise", args, kwargs))


def _preview():
    return {
        "radionuclide": "F-18",
        "weekly_dose_uSv_at_1m": 1234.5,
    }


def _schedule():
    return {
        "replay_verified": True,
        "rows": (
            {
                "source_name": "North wall",
                "material_key": "lead",
                "required_thickness_mm": 12.3,
                "provided_thickness_mm": 15.0,
                "compliance_status": "PASS",
            },
            {
                "source_name": "East wall",
                "material_key": "concrete_2350kg_m3",
                "required_thickness_mm": 210.0,
                "provided_thickness_mm": 150.0,
                "compliance_status": "FAIL",
            },
            {
                "source_name": "Control barrier",
                "material_key": "iron",
                "required_thickness_mm": 45.0,
                "provided_thickness_mm": None,
                "compliance_status": "NOT_ASSESSED",
            },
        ),
    }


def test_pet_geometry_overlay_payload_is_nonproduction_and_wall_aware():
    overlay = build_pet_geometry_overlay(_preview(), _schedule(), PetPreviewPosition(1.5, 2.5, 1.0))
    assert overlay["contract_version"] == PET_GEOMETRY_OVERLAY_CONTRACT_VERSION == 3
    assert overlay["baseline"] == PET_GEOMETRY_OVERLAY_BASELINE == "pet-ui-preview-v8"
    assert overlay["production_eligible"] is False
    assert overlay["replay_verified"] is True
    assert overlay["source_x_m"] == 1.5
    assert overlay["source_y_m"] == 2.5
    assert overlay["source_height_m"] == 1.0
    assert [row["wall_key"] for row in overlay["rows"]] == ["N", "E", None]


def test_pet_geometry_overlay_wall_name_mapping_is_deliberately_narrow():
    assert wall_key_for_preview_name("North wall") == "N"
    assert wall_key_for_preview_name("east") == "E"
    assert wall_key_for_preview_name("S wall") == "S"
    assert wall_key_for_preview_name("W") == "W"
    assert wall_key_for_preview_name("Control barrier") is None


def test_pet_geometry_overlay_draws_source_only_without_duplicate_barrier_status_text():
    geom = RoomGeometry(room_name="Room", length_m=6.0, width_m=5.0, height_m=3.0)
    geom.source.x_m = 2.0
    geom.source.y_m = 3.0
    before = (geom.source.x_m, geom.source.y_m, geom.length_m, geom.width_m)

    canvas = FakeCanvas()
    overlay = build_pet_geometry_overlay(_preview(), _schedule(), PetPreviewPosition(1.0, 1.5, 1.0))
    draw_pet_geometry_preview_overlay(canvas, geom, (100, 100, 600, 700), overlay)

    assert before == (geom.source.x_m, geom.source.y_m, geom.length_m, geom.width_m)
    assert not any("pet_preview_source" in call[2].get("tags", ()) for call in canvas.calls)
    assert not any("pet_preview_one_m_circle" in call[2].get("tags", ()) for call in canvas.calls)
    barrier_lines = [
        call for call in canvas.calls
        if call[0] == "line" and "pet_preview_barrier" in call[2].get("tags", ())
    ]
    assert barrier_lines == []
    texts = [call[2].get("text", "") for call in canvas.calls if call[0] == "text"]
    assert not any("PET preview" in text for text in texts)
    assert "1234.50 µSv/wk @ 1 m" in texts
    assert not any("PET N:" in text for text in texts)
    assert not any("PET E:" in text for text in texts)
    assert not any("Control barrier" in text for text in texts)
    assert not any("concrete_2350kg_m3" in text for text in texts)
    assert not any("PET preview barriers" in text for text in texts)


def test_geometry_tab_consumes_overlay_but_production_paths_do_not():
    geometry_tab = (ROOT / "tabs" / "geometry_tab.py").read_text(encoding="utf-8")
    preview_panel = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert "draw_pet_geometry_preview_overlay" in geometry_tab
    assert "build_pet_input_geometry_overlay" in preview_panel

    forbidden = (
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    )
    forbidden += tuple((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "pet_preview_overlay" not in text
        assert "pet_preview_geometry_overlay" not in text


def test_pet_geometry_overlay_places_one_m_label_from_canonical_geometry_source_when_preview_position_is_stale():
    geom = RoomGeometry(room_name="Room", length_m=6.0, width_m=5.0, height_m=3.0)
    geom.source.x_m = 2.0
    geom.source.y_m = 3.0
    canvas = FakeCanvas()
    overlay = build_pet_geometry_overlay(_preview(), _schedule(), PetPreviewPosition(4.0, 5.0, 1.0))
    bbox = (100, 100, 600, 700)

    draw_pet_geometry_preview_overlay(canvas, geom, bbox, overlay)

    label = next(call for call in canvas.calls if call[0] == "text" and call[2].get("text") == "1234.50 µSv/wk @ 1 m")
    label_x, label_y = label[1]
    px_per_m = min((bbox[2] - bbox[0]) / geom.width_m, (bbox[3] - bbox[1]) / geom.length_m)
    expected_x = bbox[0] + geom.source.x_m * px_per_m
    expected_y = (bbox[3] - geom.source.y_m * px_per_m) - px_per_m - 10.0

    assert label_x == expected_x
    assert label_y == expected_y
