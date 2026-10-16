from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_xr20e1_opening_controller_snapshots_and_restores_parent_wall_design_fields():
    text = (ROOT / "geometry" / "opening_controller.py").read_text(encoding="utf-8")
    assert "_snapshot_parent_wall_design_fields" in text
    assert "_restore_parent_wall_design_fields" in text
    for field in (
        "barrier.material = material",
        "barrier.thickness_mm = thickness",
        "barrier.occupancy_factor = occupancy",
        "barrier.design_goal_uSv_per_week = design_goal",
    ):
        assert field in text


def test_xr20e1_all_opening_mutation_paths_preserve_parent_wall_design():
    text = (ROOT / "geometry" / "opening_controller.py").read_text(encoding="utf-8")
    for method in (
        "def add_opening",
        "def clear_openings",
        "def update_selected_opening_from_fields",
        "def update_current_opening_thickness",
    ):
        start = text.index(method)
        next_def = text.find("\n    def ", start + 5)
        body = text[start: next_def if next_def != -1 else len(text)]
        assert "_snapshot_parent_wall_design_fields()" in body
        assert "_restore_parent_wall_design_fields(wall_design)" in body
