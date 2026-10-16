from pathlib import Path

from tabs.results_tab_text import (
    canonical_source_label,
    dominant_reason_text,
    fmt_delta,
    fmt_material_with_mm,
    fmt_mm,
    largest_contribution_label,
    parse_source_contribution_parts,
    status_summary_text,
)


def test_results_tab_text_helpers_are_extracted_from_app():
    app_text = Path("app.py").read_text(encoding="utf-8")
    text_module = Path("tabs/results_tab_text.py").read_text(encoding="utf-8")

    assert "from tabs.results_tab_text import fmt_mm" in app_text
    helpers_text = Path("tabs/results_output_helpers.py").read_text(encoding="utf-8")

    assert "from tabs.results_tab_text import build_generation_summary_lines" not in app_text
    assert "from tabs.results_tab_text import build_generation_summary_lines" in helpers_text
    assert "def build_generation_summary_lines(" in text_module
    assert "def fmt_mm(" in text_module
    assert "def build_generation_summary_lines(" in text_module

    assert "Near-equal contribution to" not in app_text
    assert "Near-equal contribution to" in text_module


def test_results_tab_text_helpers_parse_and_format():
    parsed = parse_source_contribution_parts(
        "CT Secondary Scatter: 362.99 uSv/wk; NM Patient: 496.94 uSv/wk"
    )

    assert parsed[0] == ("CT Secondary Scatter", 362.99, "CT Secondary Scatter: 362.99 uSv/wk")
    assert largest_contribution_label("CT Secondary Scatter: 362.99 uSv/wk; NM Patient: 496.94 uSv/wk") == "NM Patient"
    assert canonical_source_label("ct scatter") == "CT Secondary Scatter"
    assert status_summary_text("FAIL") == "FAIL (exceeds design goal)"
    assert fmt_mm(1.234, decimals=1) == "1.2 mm"
    assert fmt_delta(-0.25) == "-0.25 mm"
    assert fmt_material_with_mm("Pb", 1.234) == "Pb: 1.23 mm"
    assert "Higher weekly dose contribution" in dominant_reason_text(
        "CT Secondary Scatter: 500.00 uSv/wk; NM Patient: 100.00 uSv/wk"
    )
