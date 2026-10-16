from pathlib import Path


def test_opening_physics_service_is_single_interpretation_boundary():
    service_text = Path("services/opening_physics.py").read_text(encoding="utf-8")
    ui_text = Path("tabs/barriers_openings.py").read_text(encoding="utf-8")
    report_helpers_text = Path("reports/opening_helpers.py").read_text(encoding="utf-8")

    canonical_functions = [
        "def opening_type_normalized(",
        "def opening_parent_barrier(",
        "def opening_barrier_id(",
        "def opening_display_material(",
        "def opening_physics_material(",
        "def opening_pb_equiv_mm(",
        "def make_opening_physics_barrier(",
        "def opening_live_result(",
    ]

    for token in canonical_functions:
        assert token in service_text
        assert token not in ui_text
        assert token not in report_helpers_text

    assert "from services.opening_physics import (" in ui_text
    assert "from services.opening_physics import (" in report_helpers_text


def test_report_and_results_paths_use_canonical_opening_physics_service():
    for path in [
        "reports/barrier_schedule.py",
        "reports/results_payload_builder.py",
        "tabs/results_barrier_maps.py",
        "tabs/results_tab_rendering.py",
    ]:
        text = Path(path).read_text(encoding="utf-8")
        assert "services.opening_physics" in text
        assert "reports.opening_helpers" not in text
