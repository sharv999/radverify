from pathlib import Path

from geometry.default_room_geometry import create_default_room_geometry
from config.geometry_constants import (
    DEFAULT_ROOM_HEIGHT_M,
    DEFAULT_ROOM_LENGTH_M,
    DEFAULT_ROOM_WIDTH_M,
)


def test_default_room_geometry_uses_central_geometry_defaults():
    geometry = create_default_room_geometry("CT Room 1", modality="CT")

    assert geometry.room_name == "CT Room 1"
    assert geometry.length_m == DEFAULT_ROOM_LENGTH_M
    assert geometry.width_m == DEFAULT_ROOM_WIDTH_M
    assert geometry.height_m == DEFAULT_ROOM_HEIGHT_M
    assert geometry.source.label == "CT"


def test_app_delegates_default_room_geometry_factory():
    app_text = Path("app.py").read_text(encoding="utf-8")
    module_text = Path("geometry/default_room_geometry.py").read_text(encoding="utf-8")

    assert "from geometry.default_room_geometry import create_default_room_geometry" in app_text
    assert "return create_default_room_geometry(room_name=room_name, modality=modality)" in app_text
    assert "RoomGeometry(" not in app_text
    assert "RoomGeometry(" in module_text
