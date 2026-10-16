from pathlib import Path
from types import SimpleNamespace

from services.output_status_messages import build_output_status_message, output_result_summary_lines


def _result(**overrides):
    data = {
        "pdf_path": Path("C:/tmp/report.pdf"),
        "export_paths": {"barrier_results_json": Path("C:/tmp/report_barrier_results.json")},
        "warnings": [],
        "blocking_issues": [],
        "ai_report": None,
        "export_eligibility": {
            "can_export_pdf": True,
            "can_export_csv": True,
            "can_certify": True,
            "report_status_effective": "Draft",
        },
        "cancelled": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_clean_output_message_lists_pdf_exports_and_effective_status():
    message = build_output_status_message(_result())

    assert message.title == "Generation complete"
    assert message.severity == "info"
    assert "Outputs generated successfully." in message.lines
    assert "PDF report:" in message.lines
    assert "Machine-readable exports:" in message.lines
    assert "Effective report status:" in message.lines
    assert "Draft" in message.lines


def test_blocked_source_output_message_says_pdf_only_and_not_certified():
    message = build_output_status_message(_result(
        export_paths={},
        blocking_issues=["BLOCKED: selected CT scanner has NULL/missing ksec."],
        export_eligibility={
            "can_export_pdf": True,
            "can_export_csv": False,
            "can_certify": False,
            "report_status_effective": "Draft — Incomplete Source Data",
        },
    ))

    assert message.title == "Draft PDF generated — exports blocked"
    assert message.severity == "warning"
    body = message.body
    assert "Draft PDF generated with source-data blocking issue(s)." in body
    assert "Machine-readable exports were not generated." in body
    assert "Draft — Incomplete Source Data" in body
    assert "Certification permitted:\nNo" in body
    assert "BLOCKED: selected CT scanner has NULL/missing ksec." in body


def test_blocked_payload_integrity_message_names_calculation_integrity():
    message = build_output_status_message(_result(
        export_paths={},
        blocking_issues=["BLOCKED: barrier result count does not match the room barrier schedule."],
        export_eligibility={
            "can_export_pdf": True,
            "can_export_csv": False,
            "can_certify": False,
            "report_status_effective": "Draft — Incomplete Source Data",
        },
    ))

    assert "Draft PDF generated with calculation-integrity issue(s)." in message.lines[0]
    assert "Machine-readable exports were not generated." in message.body


def test_cancelled_output_message_is_clear():
    message = build_output_status_message(_result(
        pdf_path=None,
        export_paths={},
        cancelled=True,
    ))

    assert message.title == "Generation cancelled"
    assert message.status_line == "Report generation cancelled."
    assert message.lines == ["Output generation cancelled."]


def test_output_result_summary_lines_delegates_to_status_formatter():
    result = _result(
        export_paths={},
        blocking_issues=["BLOCKED: source validation has unresolved critical issue(s)."],
        export_eligibility={
            "can_export_pdf": True,
            "can_export_csv": False,
            "can_certify": False,
            "report_status_effective": "Draft — Incomplete Source Data",
        },
    )

    assert output_result_summary_lines(result) == build_output_status_message(result).lines
