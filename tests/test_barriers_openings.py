from pathlib import Path


def test_barriers_openings_module_owns_only_opening_ui_presentation_helpers():
    app_text = Path("app.py").read_text(encoding="utf-8")
    openings_text = Path("tabs/barriers_openings.py").read_text(encoding="utf-8")

    assert "def barrier_table_values_for_barrier_live(" in openings_text
    assert "def insert_opening_physics_rows(" in openings_text
    assert "from services.opening_physics import (" in openings_text

    physics_functions = [
        "def opening_type_normalized(",
        "def opening_parent_barrier(",
        "def opening_barrier_id(",
        "def opening_display_material(",
        "def opening_physics_material(",
        "def opening_pb_equiv_mm(",
        "def make_opening_physics_barrier(",
        "def opening_live_result(",
    ]
    for token in physics_functions:
        assert token not in openings_text

    assert "from tabs.barriers_openings import opening_type_normalized" not in app_text
    assert "from tabs.barriers_openings import opening_live_result" not in app_text
    assert "from tabs.barriers_openings import insert_opening_physics_rows" not in app_text


def test_app_opening_helpers_removed():
    app_text = Path("app.py").read_text(encoding="utf-8")

    removed_app_methods = [
        "def _opening_type_normalized(self",
        "def _opening_parent_barrier(self",
        "def _opening_barrier_id(self",
        "def _opening_display_material(self",
        "def _opening_physics_material(self",
        "def _opening_pb_equiv_mm(self",
        "def _make_opening_physics_barrier(self",
        "def _opening_live_result(self",
        "def _barrier_table_values_for_barrier_live(self",
        "def _insert_opening_physics_rows(self",
    ]

    for token in removed_app_methods:
        assert token not in app_text


def test_opening_callers_do_not_route_physics_through_app_or_ui():
    joined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "tabs/results_barrier_maps.py",
            "tabs/results_tab_rendering.py",
            "reports/results_payload_builder.py",
            "reports/barrier_schedule.py",
        ]
    )

    forbidden = [
        "app._opening_live_result(",
        "app._opening_type_normalized(",
        "app._opening_display_material(",
        "app._opening_parent_barrier(",
        "app._insert_opening_physics_rows(",
        "from tabs.barriers_openings import opening_live_result",
        "from reports.opening_helpers import",
    ]

    for token in forbidden:
        assert token not in joined

    assert "opening_live_result(app," in joined
    assert "build_canonical_barrier_schedule_payload(" in joined or "build_canonical_barrier_schedule_payload" in Path("reports/barrier_schedule.py").read_text(encoding="utf-8")
