from pathlib import Path


def test_source_inventory_repair_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    repair_text = Path("sources/source_inventory_repair.py").read_text(encoding="utf-8")

    assert "from sources.source_inventory_repair import repair_invalid_source_inventory" in app_text
    assert "return repair_invalid_source_inventory(self)" in app_text
    assert "def repair_invalid_source_inventory(app)" in repair_text
    assert "app.enforce_room_source_types(room)" in repair_text
    assert "app._default_source_for_type" in repair_text


def test_app_source_inventory_repair_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _repair_invalid_source_inventory(self):\n        from sources.source_inventory_repair import repair_invalid_source_inventory" in app_text
    assert "Only keep supported source types" not in app_text
