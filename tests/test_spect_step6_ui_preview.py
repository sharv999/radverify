"""Tests for SPECT Step 6 read-only UI preview boundary."""
from pathlib import Path

import pytest

from models.shielding_models import Barrier, Room
from tabs.spect_preview_panel import (
    SPECT_UI_PREVIEW_BASELINE,
    SPECT_UI_PREVIEW_CONTRACT_VERSION,
    SPECT_UI_PREVIEW_SOURCE,
    SpectPreviewError,
    build_spect_preview_barrier_requests,
    calculate_spect_room_preview,
    spect_material_key_for_room_barrier,
    spect_preview_display_rows,
)


ROOT = Path(__file__).resolve().parents[1]


def _room() -> Room:
    return Room(
        name="SPECT Room 1",
        modality="SPECT",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy="Pb 0.88 mm (10 kg/m2)",
                thickness_mm=1.1,
                distance_m=2.0,
                occupancy_factor=0.5,
                design_goal_uSv_per_week=1.0,
            ),
            Barrier(
                name="East wall",
                material="Concrete",
                material_legacy="Concrete 150 mm",
                thickness_mm=150.0,
                distance_m=3.0,
                occupancy_factor=0.25,
                design_goal_uSv_per_week=1.0,
            ),
        ],
    )


def test_step6_preview_contract_is_fixed_readonly_nonproduction_source_assumption():
    assert SPECT_UI_PREVIEW_CONTRACT_VERSION == 1
    assert SPECT_UI_PREVIEW_BASELINE == "spect-ui-preview-v1-readonly-step5"
    assert SPECT_UI_PREVIEW_SOURCE.radionuclide == "Tc99m"
    assert SPECT_UI_PREVIEW_SOURCE.administered_activity_mbq == pytest.approx(600.0)
    assert SPECT_UI_PREVIEW_SOURCE.patients_per_week == pytest.approx(20.0)
    assert SPECT_UI_PREVIEW_SOURCE.imaging_duration_h == pytest.approx(0.5)


def test_step6_maps_room_materials_to_step5_keys_without_attenuation_data():
    assert spect_material_key_for_room_barrier(Barrier(material="Pb")) == "lead"
    assert spect_material_key_for_room_barrier(Barrier(material="Concrete")) == "concrete_2300kg_m3"
    assert spect_material_key_for_room_barrier(Barrier(material="Gypsum")) == "gypsum"
    assert spect_material_key_for_room_barrier(Barrier(material="A514 steel")) == "steel_a514"
    assert spect_material_key_for_room_barrier(Barrier(material="Glass")) == "glass"


def test_step6_builds_step5_requests_from_existing_room_barrier_values_in_order():
    requests = build_spect_preview_barrier_requests(_room())
    assert [r.barrier_id for r in requests] == ["room-barrier-1", "room-barrier-2"]
    assert [r.barrier_name for r in requests] == ["North wall", "East wall"]
    assert requests[0].material_key == "lead"
    assert requests[0].distance_m == pytest.approx(2.0)
    assert requests[0].occupancy_factor == pytest.approx(0.5)
    assert requests[0].design_goal_uSv_per_week == pytest.approx(1.0)
    assert requests[0].provided_thickness_mm == pytest.approx(1.1)
    assert requests[1].material_key == "concrete_2300kg_m3"


def test_step6_calculates_only_through_step5_schedule_contract():
    result = calculate_spect_room_preview(_room())
    assert result.production_eligible is False
    assert result.status == "development_nonproduction"
    assert len(result.rows) == 2
    assert result.rows[0].barrier_name == "North wall"
    assert result.rows[1].barrier_name == "East wall"
    assert result.source_physics.radionuclide == "Tc99m"


def test_step6_display_rows_are_presentation_strings_and_include_step5_cautions():
    result = calculate_spect_room_preview(_room())
    rows = spect_preview_display_rows(result)
    assert len(rows) == 2
    assert rows[0]["barrier_name"] == "North wall"
    assert rows[0]["compliance_status"] in {"PASS", "FAIL", "NOT_ASSESSED"}
    assert isinstance(rows[0]["required_thickness_mm"], str)
    assert isinstance(rows[0]["caution"], str)


def test_step6_rejects_non_spect_empty_and_unsupported_material_rooms():
    with pytest.raises(SpectPreviewError, match="not a SPECT room"):
        build_spect_preview_barrier_requests(Room(name="CT", modality="CT"))
    with pytest.raises(SpectPreviewError, match="no barriers"):
        build_spect_preview_barrier_requests(Room(name="S", modality="SPECT"))
    room = _room()
    room.barriers[0].material = "Unobtainium"
    room.barriers[0].material_legacy = ""
    with pytest.raises(SpectPreviewError, match="unsupported SPECT preview material"):
        build_spect_preview_barrier_requests(room)


def test_spect_working_source_is_wired_into_unified_sources_form_and_not_reports_serialization():
    source_layout = (ROOT / "tabs" / "source_tab_layout.py").read_text(encoding="utf-8")
    source_form = (ROOT / "tabs" / "source_form_layout.py").read_text(encoding="utf-8")
    source_actions = (ROOT / "tabs" / "source_tab_actions.py").read_text(encoding="utf-8")
    assert "build_spect_preview_panel" not in source_layout
    assert "build_spect_source_controls" in source_form
    assert "refresh_spect_preview" in source_actions

    forbidden = [
        ROOT / "app.py",
        ROOT / "engine" / "shielding_engine.py",
        ROOT / "services" / "project_serializer.py",
    ]
    forbidden += list((ROOT / "reports").glob("*.py"))
    forbidden += list((ROOT / "serialization").glob("*.py"))
    for path in forbidden:
        text = path.read_text(encoding="utf-8")
        assert "tabs.spect_preview_panel" not in text
        assert "calculate_spect_tc99m_barrier_schedule" not in text


def test_step6_tk_module_contains_no_shielding_equations_or_coefficients():
    panel = (ROOT / "tabs" / "spect_preview_panel.py").read_text(encoding="utf-8")
    forbidden_physics_tokens = (
        "alpha_mm_inv",
        "beta_mm_inv",
        "gamma",
        "archer_required_thickness",
        "archer_transmission",
        "exp(",
        "log(",
        "dose_rate_constant_uSv_h_per_MBq_at_1m",
    )
    for token in forbidden_physics_tokens:
        assert token not in panel
