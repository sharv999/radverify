from pathlib import Path

from tabs.barrier_table_formatting import format_barrier_table_cell


def test_barriers_material_column_is_next_to_actual():
    source = Path("app.py").read_text(encoding="utf-8")
    edit_columns = source.split("BARRIER_EDIT_COLUMNS = [", 1)[1].split("]", 1)[0]
    assert edit_columns.index('"thickness_mm"') < edit_columns.index('"material"') < edit_columns.index('"barrier_role"')
    layout = Path("tabs/barriers_tab.py").read_text(encoding="utf-8")
    assert '"material": "Material"' in layout


def test_material_column_uses_canonical_schedule_value():
    assert format_barrier_table_cell({"material": "Pb", "thickness_mm": 0.88}, "material") == "Pb"
    assert format_barrier_table_cell({"material": "Concrete", "thickness_mm": 150}, "material") == "Concrete"
