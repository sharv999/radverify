from __future__ import annotations

from geometry.geometry_model import Opening
from radverify.models import MeasurementPoint, RadVerifyProject


def test_radverify_round_trip_and_radstatus_payload():
    p = RadVerifyProject()
    p.details.project_id = "RV-TEST"
    p.details.site_name = "Test Site"
    p.geometry.openings.append(
        Opening(
            wall="S",
            opening_type="door",
            offset_m=1.2,
            width_m=0.9,
            label="D1",
            material="Lead-lined door",
            pb_equiv_mm=0.88,
            id="D1",
        )
    )
    p.sync_opening_inspections()
    p.barriers[0].status = "Pass"
    mp = MeasurementPoint(
        point_id="MP01",
        x_m=2.0,
        y_m=1.0,
        reading_uSv_h=1.2,
        background_uSv_h=0.2,
        status="Pass",
    )
    mp.recalculate()
    p.measurements.append(mp)

    saved = p.to_dict()
    assert saved["schema_version"] == "radverify-0.1"
    assert saved["radstatus_payload"]["project_id"] == "RV-TEST"
    assert saved["radstatus_payload"]["barrier_summary"]["pass"] == 1
    assert saved["radstatus_payload"]["measurement_points"][0]["corrected_uSv_h"] == 1.0

    restored = RadVerifyProject.from_dict(saved)
    assert restored.details.site_name == "Test Site"
    assert restored.geometry.openings[0].id == "D1"
    assert restored.measurements[0].corrected_uSv_h == 1.0


def test_not_inspected_maps_to_neutral_renderer_state():
    p = RadVerifyProject()
    assert p.barriers[0].risk_state() == "not_inspected"
