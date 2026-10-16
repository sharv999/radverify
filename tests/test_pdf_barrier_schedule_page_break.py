from pathlib import Path


def test_preliminary_pdf_builds_client_facing_pages_in_order():
    text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    build_start = text.index("def _build_pdf")
    build_end = text.index("def _section_preliminary_cover", build_start)
    build = text[build_start:build_end]

    design_pos = build.index("_section_preliminary_design_basis")
    plan_pos = build.index("_section_preliminary_barrier_plan")
    schedule_pos = build.index("_section_preliminary_barrier_schedule")
    actions_pos = build.index("_section_preliminary_actions")
    conclusion_pos = build.index("_section_preliminary_conclusion")
    assert design_pos < plan_pos < schedule_pos < actions_pos < conclusion_pos
    assert build.count("story.append(PageBreakIfNotEmpty())") >= 5


def test_preliminary_pdf_uses_client_facing_top_level_section_headings():
    text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    for heading in (
        'Paragraph(f"{section_number}. Design basis", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Barrier plan", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Barrier schedule", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Design actions and verification", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Conclusion and next stage", styles["SectionHeading"])',
    ):
        assert heading in text

    assert "3.2 Source and workload assumptions" in text
    assert "5.1 Construction interpretation" not in text
    assert "6.1 Project coordination actions" in text
    assert "7.2 Recommended next stage" in text
