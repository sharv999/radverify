from pathlib import Path


APP_TEXT = Path("app.py").read_text(encoding="utf-8")


def test_app_does_not_regress_to_legacy_ct_database_code():
    forbidden = [
        "CTShieldingDatabase",
        "CT_DB_AVAILABLE",
        "conservative_default_ksec",
        "_json_worst_case_ksec_per_100mAs",
        "_ct_csv_default_path",
        "_update_ct_ksec_from_database",
        "_ct_scanner_resolution_service",
        "from reports.output_pipeline import generate_outputs_from_app",
    ]

    for token in forbidden:
        assert token not in APP_TEXT


def test_app_keeps_extracted_tab_layout_action_boundaries():
    required = [
        "from tabs.project_tab_layout import build_project_tab",
        "from tabs.project_tab_actions import new_project",
        "from tabs.project_tab_actions import refresh_single_room_state",
        "from tabs.project_tab_actions import on_room_form_change",
        "from tabs.source_tab_layout import build_sources_tab",
        "from tabs.source_tab_actions import refresh_sources_list",
        "from tabs.barriers_tab_layout import build_barriers_tab",
        "from tabs.barriers_tab_actions import add_barrier",
        "from tabs.results_tab_layout import build_results_tab",
        "from tabs.results_tab_actions import generate_outputs",
    ]

    for token in required:
        assert token in APP_TEXT


def test_app_has_single_critical_method_definitions():
    singletons = [
        "def prepare_project_for_save",
        "def get_selected_room_index",
    ]

    for token in singletons:
        assert APP_TEXT.count(token) == 1

def test_output_pipeline_uses_single_export_eligibility_gate():
    pipeline_text = Path("reports/output_pipeline.py").read_text(encoding="utf-8")
    payload_text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8")

    assert "from services.export_eligibility import" in pipeline_text
    assert "assess_export_eligibility" in pipeline_text
    assert "apply_export_eligibility_to_payload" in pipeline_text
    assert "if not can_export_pdf" in pipeline_text
    assert "authorize_issueable_preliminary_pet_spect_pdf" in pipeline_text
    assert "can_export_csv = bool(final_eligibility_dict.get(\"can_export_csv\", False))" in pipeline_text
    assert "can_export_barrier_results_json = can_export_csv or pet_spect_preliminary_candidate" in pipeline_text
    assert "include_csv=False" in pipeline_text

    assert "from services.export_eligibility import apply_export_eligibility_to_payload" in payload_text
    assert "apply_export_eligibility_to_payload(" in payload_text


def test_source_validation_uses_stable_null_ksec_block_reason():
    modality_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    validation_text = Path("sources/source_validation.py").read_text(encoding="utf-8")
    assert "BLOCKED: selected CT scanner has NULL/missing ksec." in modality_text
    assert "source_readiness_result_for_source" in validation_text
