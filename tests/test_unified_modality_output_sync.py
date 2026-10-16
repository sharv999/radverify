from services.unified_modality_output_sync import sync_unified_modality_outputs


def test_unified_modality_output_sync_repairs_inventory_before_results_and_geometry():
    calls = []

    class GeometryTab:
        def request_redraw(self):
            calls.append("geometry")

    class App:
        geometry_tab = GeometryTab()

        def _repair_invalid_source_inventory(self):
            calls.append("repair")

        def refresh_barrier_schedule(self):
            calls.append("barriers")

        def refresh_results_tab(self):
            calls.append("results")

    sync_unified_modality_outputs(App())
    assert calls == ["repair", "barriers", "results", "geometry"]


def test_pet_and_spect_unified_paths_use_shared_output_sync():
    from pathlib import Path

    pet = Path("tabs/pet_preview_panel.py").read_text(encoding="utf-8")
    spect = Path("tabs/spect_preview_panel.py").read_text(encoding="utf-8")

    assert "sync_unified_modality_outputs(app)" in pet
    assert "sync_unified_modality_outputs(app)" in spect


def test_unified_modality_output_sync_refreshes_barriers_for_pet_and_spect_working_state_edits():
    calls = []

    class App:
        def _repair_invalid_source_inventory(self):
            calls.append("repair")

        def refresh_barrier_schedule(self):
            calls.append("barriers")

        def refresh_results_tab(self):
            calls.append("results")

    sync_unified_modality_outputs(App())

    assert "barriers" in calls
    assert calls.index("barriers") > calls.index("repair")
    assert calls.index("barriers") < calls.index("results")
