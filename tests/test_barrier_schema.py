from pathlib import Path


def test_barrier_schema_module_exists_and_owns_coercion_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    schema_text = Path("services/barrier_schema.py").read_text(encoding="utf-8")

    assert "from services.barrier_schema import coerce_barrier_schema" in app_text
    assert "def coerce_barrier_schema" in schema_text
    assert "parse_material_option(" in schema_text


def test_app_barrier_schema_method_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def _coerce_barrier_schema(self, barrier: Barrier) -> None:\n        from services.barrier_schema import coerce_barrier_schema" in app_text
    assert "material_legacy" not in app_text
    assert "parse_material_option(" not in app_text
