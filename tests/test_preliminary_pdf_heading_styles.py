from pathlib import Path


def test_client_facing_top_level_pdf_sections_use_larger_section_heading_style():
    text = (Path(__file__).resolve().parents[1] / "reports" / "report_generator.py").read_text(encoding="utf-8")
    expected = (
        'Paragraph("1. Project details", styles["SectionHeading"])',
        'Paragraph("2. Assessment outcome", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Design basis", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Barrier plan", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Barrier schedule", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Design actions and verification", styles["SectionHeading"])',
        'Paragraph(f"{section_number}. Conclusion and next stage", styles["SectionHeading"])',
        'Paragraph("8. Preliminary assessment limitations", styles["SectionHeading"])',
    )
    for heading in expected:
        assert heading in text
