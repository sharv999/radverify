from pathlib import Path


def test_ai_qc_tab_removed_from_main_window_and_app_delegates():
    app_text = Path("app.py").read_text(encoding="utf-8")
    main_window_text = Path("ui/main_window.py").read_text(encoding="utf-8")

    forbidden = [
        "app.ai_qa_tab",
        "AI QA",
        "_build_ai_qa_tab",
        "run_ai_qa_review",
        "tabs.ai_qa_tab_layout",
        "tabs.ai_qa_tab_actions",
        "tabs.ai_qa_tab_rendering",
        "ai_qa_last_report",
    ]

    for token in forbidden:
        assert token not in app_text
        assert token not in main_window_text


def test_ai_qc_tab_files_and_sqlite_store_removed():
    removed_paths = [
        Path("tabs/ai_qa_tab_actions.py"),
        Path("tabs/ai_qa_tab_layout.py"),
        Path("tabs/ai_qa_tab_rendering.py"),
        Path("data/ai_qa.sqlite3"),
        Path("engine/ai_qa.py"),
    ]

    for path in removed_paths:
        assert not path.exists()


def test_output_pipeline_does_not_run_ai_qc():
    pipeline_text = Path("reports/output_pipeline.py").read_text(encoding="utf-8")
    results_action_text = Path("tabs/results_tab_actions.py").read_text(encoding="utf-8")

    assert "run_ai_qa" not in pipeline_text
    assert "run_ai_qa_review" not in pipeline_text
    assert "run_ai_qa=False" not in results_action_text


def test_pdf_uses_preliminary_ct_schedule_not_ai_qc_appendix():
    payload_text = Path("reports/results_payload_builder.py").read_text(encoding="utf-8")
    pdf_text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")

    assert "report_wording_for_modality" in payload_text
    assert "Preliminary CT Shielding Schedule" in ct_text
    assert "Preliminary / quotation-only CT shielding assessment schedule" in ct_text
    assert "Preliminary / quotation-only CT shielding assessment schedule" not in pdf_text
    assert "AI QA Review Appendix" not in pdf_text
    assert '"ai_qa"' not in payload_text
