from __future__ import annotations

from pathlib import Path

import pytest

from app import RadVerifyApp
from radverify.models import EvidenceItem, MeasurementPoint, MeasurementRecord, RadVerifyProject
from radverify.radtwin import project_to_radtwin


def make_complete_project() -> RadVerifyProject:
    project = RadVerifyProject()
    project.details.inspection_date = "2026-10-17"
    project.details.inspector = "Inspector A"
    for barrier in project.barriers:
        barrier.expected_construction = "Design shielding"
        barrier.expected_pb_mm = 1.0
        barrier.observed_construction = "Verified shielding"
        barrier.observed_pb_mm = 1.0
        barrier.status = "Pass"
        barrier.evidence_ref = f"{barrier.barrier_id}-EV01"

    point = MeasurementPoint(
        point_id="MP01",
        x_m=1.0,
        y_m=1.0,
        location="Control position",
    )
    point.add_measurement_record(
        MeasurementRecord(
            record_id="MP01-M01",
            measured_at="2026-10-17",
            instrument="Survey meter",
            instrument_id="METER-01",
            calibration_due_date="2027-01-01",
            reading_uSv_h=0.8,
            background_uSv_h=0.1,
            status="Pass",
        )
    )
    project.measurements.append(point)
    return project


def test_default_project_summary_is_incomplete_and_not_ready():
    project = RadVerifyProject()
    summary = project.verification_summary()
    assert summary["verification_state"] == "Incomplete"
    assert summary["radstatus_ready"] is False
    assert summary["barriers"]["not_inspected"] == 6
    assert summary["measurements"]["points_total"] == 0
    assert any(issue["issue"] == "No measurement points recorded" for issue in summary["issues"])


def test_complete_pass_project_is_verified_and_ready_for_radstatus():
    project = make_complete_project()
    summary = project.verification_summary()
    assert summary["verification_state"] == "Verified"
    assert summary["radstatus_ready"] is True
    assert summary["barriers"]["pass"] == 6
    assert summary["barriers"]["as_built_complete"] == 6
    assert summary["barriers"]["evidence_complete"] == 6
    assert summary["measurements"]["points_recorded"] == 1
    assert summary["measurements"]["calibration_current"] == 1
    assert summary["issues"] == []


def test_complete_fail_package_is_still_ready_for_radstatus_handoff():
    project = make_complete_project()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    north.status = "Fail"
    north.notes = "As-built shielding below design"
    summary = project.verification_summary()
    assert summary["verification_state"] == "Failed"
    assert summary["radstatus_ready"] is True
    assert any(issue["severity"] == "Fail" and issue["item_id"] == "N wall" for issue in summary["issues"])


def test_evidence_integrity_issue_requires_review_and_blocks_ready_flag(tmp_path: Path):
    project = make_complete_project()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    evidence_file = tmp_path / "north-wall.txt"
    evidence_file.write_text("original", encoding="utf-8")
    item = EvidenceItem(
        evidence_id="N-WALL-EV01",
        evidence_type="Photo",
        reference="IMG_1001",
        file_path=str(evidence_file),
    )
    item.refresh_hash()
    north.evidence_items = [item]
    north.evidence_ref = "IMG_1001"
    evidence_file.write_text("changed", encoding="utf-8")

    summary = project.verification_summary()
    assert summary["verification_state"] == "Review required"
    assert summary["radstatus_ready"] is False
    assert summary["barriers"]["evidence_integrity_issues"] == 1
    assert any("File changed" in issue["issue"] for issue in summary["issues"])


def test_summary_is_exported_to_radstatus_and_digital_twin():
    project = make_complete_project()
    radstatus = project.to_radstatus_payload()
    twin = project_to_radtwin(project)
    assert radstatus["verification_summary"]["verification_state"] == "Verified"
    assert radstatus["verification_summary"]["radstatus_ready"] is True
    assert twin["verification_summary"]["verification_state"] == "Verified"
    assert twin["verification_summary"]["radstatus_ready"] is True


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


def test_room_summary_tab_refreshes_from_current_project(app):
    app.project = make_complete_project()
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()
    summary = app.summary_tab.refresh()
    assert summary["verification_state"] == "Verified"
    assert app.summary_tab.state_var.get() == "Verified"
    assert app.summary_tab.ready_var.get() == "READY FOR RADSTATUS"
    assert len(app.summary_tab.issue_tree.get_children()) == 1
    values = app.summary_tab.issue_tree.item(app.summary_tab.issue_tree.get_children()[0], "values")
    assert values[-1] == "No outstanding items"
