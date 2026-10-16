from pathlib import Path


def test_room_source_enforcement_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    module_text = Path("sources/room_source_enforcement.py").read_text(encoding="utf-8")

    assert "from sources.room_source_enforcement import enforce_room_source_types" in app_text
    assert "return enforce_room_source_types(self, room)" in app_text
    assert "repair_ct_family_params_for_source_type" in module_text
    assert "normalize_source_params" in module_text


def test_app_enforce_room_source_types_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def enforce_room_source_types(self, room: Room) -> None:\n        from sources.room_source_enforcement import enforce_room_source_types" in app_text
    assert "self.project.sources.append(src)" not in _method_body(app_text, "enforce_room_source_types")


def _method_body(text: str, method_name: str) -> str:
    marker = f"    def {method_name}"
    start = text.index(marker)
    next_start = text.find("\n    def ", start + 1)
    if next_start == -1:
        return text[start:]
    return text[start:next_start]
