from pathlib import Path

from reports.report_generator import (
    _patient_source_summary_from_room,
    _preliminary_design_decision,
    _preliminary_overall_status,
)


def test_client_facing_preliminary_report_is_presentation_only():
    text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    build_start = text.index("def _build_pdf")
    # The client-facing report path must consume canonical payload values rather
    # than importing or invoking shielding engine functions.
    client_section = text[build_start:text.index("def _payload_report_wording", build_start)]
    assert "shielding_engine" not in client_section
    assert "calculate_" not in client_section
    assert "compute_room_barrier_table" not in client_section


def test_client_outcome_rollup_and_decision_text():
    payload = {
        "summary": {"pass_count": 6, "review_count": 0, "fail_count": 0},
        "rooms": [{"overall_status": "PASS"}],
    }
    assert _preliminary_overall_status(payload) == "PASS"
    assert "Proceed with design development" in _preliminary_design_decision(payload)

    payload["summary"]["fail_count"] = 1
    assert _preliminary_overall_status(payload) == "FAIL"
    assert "Do not rely" in _preliminary_design_decision(payload)


def test_spect_design_basis_reads_existing_route_source_summary_without_recalculation():
    room = {
        "pet_spect_report_route": {
            "payload": {
                "source_summary": {
                    "radionuclide": "Tc99m",
                    "administered_activity_mbq": 740.0,
                    "patients_per_week": 40.0,
                    "imaging_duration_h": 0.5,
                    "source_position_x_m": 2.5,
                    "source_position_y_m": 3.0,
                }
            }
        }
    }
    summary = _patient_source_summary_from_room(room)
    assert summary["administered_activity_mbq"] == 740.0
    assert summary["patients_per_week"] == 40.0


def test_client_report_requested_labels_and_section_numbering():
    text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    assert 'Paragraph("7.3 Information normally required for the detailed/final assessment", styles["RoomHeading"])' in text
    assert 'Paragraph("8. Preliminary assessment limitations", styles["SectionHeading"])' in text
    assert '"Occupancy T"' in text
    assert '["Barrier", "Adjacent area", "Distance (m)", "Occupancy T", "P (uSv/wk)"]' in text
    assert 'Any increase in administered activity' in text
    assert 'Any change to room dimensions' in text
    assert 'Any change to barrier construction' in text
    assert '6.1 Project coordination actions' in text
    assert '6.2 Changes that trigger reassessment' in text
    assert '6.3 Changes that trigger reassessment' not in text
    assert '_verification_schedule_table(' not in text
    assert 'Overall status:' not in text[text.index("def _section_preliminary_barrier_plan"):text.index("def _section_preliminary_barrier_schedule")]


def test_client_key_value_tables_use_dark_label_column():
    text = Path("reports/report_generator.py").read_text(encoding="utf-8")
    assert '_client_key_value_table(rows, [38 * mm, 114 * mm])' in text
    assert '_client_key_value_table(room_rows, [42 * mm, 110 * mm])' in text
    outcome = text[text.index("def _client_outcome_table"):text.index("def _fmt_dimension")]
    assert '("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#182230"))' in outcome
    assert '("TEXTCOLOR", (0, 0), (0, -1), colors.white)' in outcome


def test_barrier_schedule_distance_column_is_compact():
    from reports.report_generator import PDF_BARRIER_COLUMN_WIDTHS_MM
    assert PDF_BARRIER_COLUMN_WIDTHS_MM[3] == 22
