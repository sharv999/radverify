from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_separate_pet_preview_results_tab_is_retired():
    main_window = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    preview_inputs = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")

    assert not (ROOT / "tabs" / "pet_preview_results_tab.py").exists()
    assert "pet_preview_results_tab" not in main_window
    assert "PET_PREVIEW_RESULTS_TAB_LABEL" not in main_window
    assert "build_pet_preview_results_tab" not in main_window
    assert "Read-only PET barrier preview schedule" not in preview_inputs
    assert "pet_preview_results_tree" not in preview_inputs


def test_sources_panel_is_input_and_provenance_preview_only():
    preview_inputs = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")

    assert 'text="PET input and provenance preview"' in preview_inputs
    assert "pet_preview_validation_var" in preview_inputs
    assert "pet_preview_provenance_var" in preview_inputs
    assert "Provenance manifest:" in preview_inputs
    assert "Radionuclide dataset:" in preview_inputs
    assert "Attenuation dataset:" in preview_inputs
    assert "Canonical barrier calculations are displayed only through the normal Results model" in preview_inputs
    assert "format_pet_calculation_summary" not in preview_inputs


def test_pet_input_preview_remains_outside_report_and_export_paths():
    project_serializer = (ROOT / "services" / "project_serializer.py").read_text(encoding="utf-8")
    shielding_engine = (ROOT / "engine" / "shielding_engine.py").read_text(encoding="utf-8")
    report_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "reports").glob("*.py")
    )
    readiness = (ROOT / "services" / "source_readiness.py").read_text(encoding="utf-8")

    assert "pet_preview_provenance_var" not in project_serializer
    assert "pet_preview_provenance_var" not in shielding_engine
    assert "pet_preview_provenance_var" not in report_text
    assert "output_blocking" in readiness
