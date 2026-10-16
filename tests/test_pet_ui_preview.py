from pathlib import Path

import pytest

from geometry.pet_preview_position import PetPreviewPosition
from tabs.pet_preview_panel import (
    PET_UI_PREVIEW_BASELINE,
    PET_UI_PREVIEW_CONTRACT_VERSION,
    build_pet_preview_barrier_request,
    build_pet_preview_barrier_values_from_room,
    build_pet_preview_request_envelope,
    build_pet_preview_barrier_requests,
    build_pet_preview_source_domain,
    calculate_pet_barrier_preview,
    calculate_pet_barrier_schedule_preview,
    calculate_pet_preview,
    pet_preview_request_to_form_values,
)

ROOT = Path(__file__).resolve().parents[1]


def _values(radionuclide="F18"):
    return {
        "room_mode": "Imaging Room",
        "radionuclide": radionuclide,
        "injected_activity_mbq": "250",
        "patients_per_week": "30",
        "residual_activity_factor": "1.0",
        "phase_1_name": "Uptake",
        "phase_1_start_h": "0",
        "phase_1_duration_h": "1",
        "phase_1_activity_retention_factor": "1.0",
        "phase_2_name": "Imaging",
        "phase_2_start_h": "1",
        "phase_2_duration_h": "0.5",
        "phase_2_activity_retention_factor": "1.0",
        "material_key": "lead",
        "distance_m": "2.0",
        "occupancy_factor": "1.0",
        "design_goal_uSv_per_week": "10",
        "provided_thickness_mm": "",
    }


def test_pet_ui_preview_builds_validated_source_domain():
    source = build_pet_preview_source_domain(_values())
    assert source.radionuclide == "F18"
    assert source.injected_activity_mbq == 250.0
    assert source.patients_per_week == 30.0
    assert len(source.exposure_phases) == 1
    assert source.exposure_phases[0].name == "Imaging"


def test_pet_ui_preview_uptake_room_uses_uptake_duration_from_administration():
    values = _values()
    values["room_mode"] = "Uptake Room"
    values["phase_1_start_h"] = "1.0"
    values["phase_1_duration_h"] = "0.5"
    values["phase_1_activity_retention_factor"] = "0.85"
    source = build_pet_preview_source_domain(values)
    phase = source.exposure_phases[0]
    assert phase.name == "Uptake"
    assert phase.start_time_h == 0.0
    assert phase.duration_h == 1.0
    assert phase.activity_retention_factor == 1.0


def test_pet_ui_preview_calculates_nonproduction_weekly_dose():
    preview = calculate_pet_preview(_values("Ga68"))
    assert preview["contract_version"] == PET_UI_PREVIEW_CONTRACT_VERSION == 14
    assert preview["baseline"] == PET_UI_PREVIEW_BASELINE == "pet-ui-preview-v14-activity-retention"
    assert preview["radionuclide"] == "Ga-68"
    assert preview["weekly_dose_uSv_at_1m"] > 0.0
    assert preview["phase_count"] == 1
    assert preview["production_eligible"] is False


def test_pet_ui_preview_rejects_invalid_inputs():
    values = _values()
    values["phase_1_activity_retention_factor"] = "1.2"
    with pytest.raises(ValueError, match="activity_retention_factor"):
        build_pet_preview_source_domain(values)



def test_pet_ui_preview_builds_validated_barrier_request():
    request = build_pet_preview_barrier_request(_values())
    assert request.material_key == "lead"
    assert request.distance_m == 2.0
    assert request.occupancy_factor == 1.0
    assert request.design_goal_uSv_per_week == 10.0
    assert request.provided_thickness_mm is None


def test_pet_ui_preview_calculates_replay_verified_barrier_result():
    values = _values()
    values["provided_thickness_mm"] = "20"
    preview = calculate_pet_barrier_preview(values)

    assert preview["contract_version"] == 14
    assert preview["baseline"] == "pet-ui-preview-v14-activity-retention"
    assert preview["production_eligible"] is False
    assert preview["replay_verified"] is True
    assert preview["material_key"] == "lead"
    assert preview["required_tvl_count"] > 0.0
    assert preview["required_thickness_mm"] > 0.0
    assert preview["provided_thickness_mm"] == 20.0
    assert preview["compliance_status"] in {"PASS", "FAIL"}
    assert preview["attenuation_record_id"]
    assert preview["dataset_id"]


def test_pet_ui_preview_barrier_without_provided_thickness_is_not_assessed():
    preview = calculate_pet_barrier_preview(_values("Ga68"))
    assert preview["provided_thickness_mm"] is None
    assert preview["transmitted_weekly_dose_uSv"] is None
    assert preview["compliance_status"] == "NOT_ASSESSED"


def test_pet_ui_preview_rejects_invalid_barrier_inputs():
    values = _values()
    values["occupancy_factor"] = "1.2"
    with pytest.raises(ValueError, match="occupancy_factor"):
        calculate_pet_barrier_preview(values)

    values = _values()
    values["provided_thickness_mm"] = "-1"
    with pytest.raises(ValueError, match="provided_thickness_mm"):
        calculate_pet_barrier_preview(values)


def test_pet_working_source_is_wired_into_unified_sources_form_not_separate_panel():
    source_layout = (ROOT / "tabs" / "source_tab_layout.py").read_text(encoding="utf-8")
    source_form = (ROOT / "tabs" / "source_form_layout.py").read_text(encoding="utf-8")
    assert "build_pet_preview_panel" not in source_layout
    assert "build_pet_source_controls" in source_form

    forbidden = (
        ROOT / "app.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    )
    forbidden += tuple((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        assert "tabs.pet_preview_panel" not in path.read_text(encoding="utf-8")


def test_pet_is_production_host_enabled_and_report_blocked():
    from modalities.registry import get_modality_plugin, production_modality_names

    pet = get_modality_plugin("PET")
    assert pet.spec.production_enabled is True
    assert pet.spec.expected_sources[0].dose_model == "pet_patient_production_dispatch"
    assert "PET" in production_modality_names()


def _barriers():
    return [
        {
            "source_name": "North wall",
            "material_key": "lead",
            "distance_m": "2.0",
            "occupancy_factor": "1.0",
            "design_goal_uSv_per_week": "10",
            "provided_thickness_mm": "20",
        },
        {
            "source_name": "East wall",
            "material_key": "concrete_2350kg_m3",
            "distance_m": "3.0",
            "occupancy_factor": "0.25",
            "design_goal_uSv_per_week": "10",
            "provided_thickness_mm": "",
        },
        {
            "source_name": "Control barrier",
            "material_key": "iron",
            "distance_m": "2.5",
            "occupancy_factor": "1.0",
            "design_goal_uSv_per_week": "10",
            "provided_thickness_mm": "50",
        },
    ]


def test_pet_ui_preview_builds_multiple_independent_barrier_requests():
    requests = build_pet_preview_barrier_requests(_barriers())
    assert len(requests) == 3
    assert [request.source_name for request in requests] == [
        "North wall", "East wall", "Control barrier"
    ]
    assert [request.material_key for request in requests] == [
        "lead", "concrete_2350kg_m3", "iron"
    ]


def test_pet_ui_preview_calculates_read_only_multi_barrier_schedule():
    schedule = calculate_pet_barrier_schedule_preview(_values(), _barriers())
    assert schedule["contract_version"] == 14
    assert schedule["baseline"] == "pet-ui-preview-v14-activity-retention"
    assert schedule["production_eligible"] is False
    assert schedule["replay_verified"] is True
    assert len(schedule["rows"]) == 3
    assert [row["source_name"] for row in schedule["rows"]] == [
        "North wall", "East wall", "Control barrier"
    ]
    assert all(row["required_tvl_count"] > 0 for row in schedule["rows"])
    assert all(row["required_thickness_mm"] > 0 for row in schedule["rows"])
    assert schedule["rows"][1]["compliance_status"] == "NOT_ASSESSED"
    assert schedule["rows"][0]["compliance_status"] in {"PASS", "FAIL"}


def test_pet_ui_preview_multi_barrier_schedule_rejects_invalid_row():
    rows = _barriers()
    rows[1]["occupancy_factor"] = "1.5"
    with pytest.raises(ValueError, match="occupancy_factor"):
        calculate_pet_barrier_schedule_preview(_values(), rows)


def test_pet_ui_preview_request_envelope_round_trips_form_values():
    request = build_pet_preview_request_envelope(_values(), _barriers())
    source_values, barrier_values = pet_preview_request_to_form_values(request)
    assert source_values["room_mode"] == "Imaging Room"
    assert source_values["radionuclide"] == "F18"
    assert float(source_values["injected_activity_mbq"]) == 250.0
    assert len(barrier_values) == 3
    assert [row["source_name"] for row in barrier_values] == [
        "North wall", "East wall", "Control barrier"
    ]
    assert barrier_values[1]["provided_thickness_mm"] == ""



def test_pet_ui_preview_legacy_multiphase_restore_selects_imaging_phase():
    from modalities.pet import PetExposurePhase, PetSourceDomain
    from serialization.pet_calculation_request_contract import PetCalculationRequestEnvelope

    request = PetCalculationRequestEnvelope(
        source=PetSourceDomain(
            radionuclide="F18",
            injected_activity_mbq=555.0,
            patients_per_week=40.0,
            exposure_phases=(
                PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
                PetExposurePhase("Imaging", 1.0, 0.5, 0.85),
            ),
        ),
        barrier_requests=(),
    )
    source_values, _ = pet_preview_request_to_form_values(request)
    assert source_values["room_mode"] == "Imaging Room"
    assert source_values["phase_1_start_h"] == "1.0"
    assert source_values["phase_1_duration_h"] == "0.5"
    assert source_values["phase_1_activity_retention_factor"] == "0.85"


def test_pet_ui_preview_persistence_is_separate_from_production_paths():
    preview_module = (ROOT / "serialization" / "pet_preview_state.py").read_text(encoding="utf-8")
    assert "radshield_pet_ui_preview_state_v2" in preview_module
    assert "production_eligible" in preview_module
    forbidden = (
        ROOT / "app.py",
        ROOT / "services" / "project_serializer.py",
        ROOT / "engine" / "shielding_engine.py",
    )
    forbidden += tuple((ROOT / "reports").glob("*.py"))
    for path in forbidden:
        assert "pet_preview_state" not in path.read_text(encoding="utf-8")


def test_pet_step7_derives_preview_barriers_from_room_inventory():
    from models.shielding_models import Barrier, Room

    room = Room(
        name="PET Room Preview",
        modality="CT",
        barriers=[
            Barrier(
                name="N wall", material="Pb", thickness_mm=1.32, distance_m=2.4,
                occupancy_factor=0.2, design_goal_uSv_per_week=10.0,
            ),
            Barrier(
                name="Floor", material="Concrete", thickness_mm=150.0, distance_m=1.1,
                occupancy_factor=1.0, design_goal_uSv_per_week=10.0,
            ),
            Barrier(
                name="Steel screen", material="Steel", thickness_mm=12.0, distance_m=1.8,
                occupancy_factor=1.0, design_goal_uSv_per_week=50.0,
            ),
        ],
    )

    position = PetPreviewPosition(x_from_west_m=1.5, y_from_south_m=1.6, height_above_ffl_m=1.1)
    rows = build_pet_preview_barrier_values_from_room(room, position)

    assert [row["source_name"] for row in rows] == ["N wall", "Floor", "Steel screen"]
    assert [row["material_key"] for row in rows] == [
        "lead", "concrete_2350kg_m3", "iron"
    ]
    assert rows[0]["distance_m"] == "4.4"
    assert rows[0]["provided_thickness_mm"] == "1.32"
    assert rows[1]["occupancy_factor"] == "1.0"
    assert rows[2]["design_goal_uSv_per_week"] == "50.0"


def test_pet_step7_rejects_room_barrier_with_unsupported_material():
    from models.shielding_models import Barrier, Room

    room = Room(barriers=[Barrier(name="Timber wall", material="Timber")])
    with pytest.raises(ValueError, match="unsupported PET preview material"):
        build_pet_preview_barrier_values_from_room(room)


def test_pet_step7_ui_has_no_editable_placeholder_barrier_rows():
    preview_inputs = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert "Room-derived barrier inventory" in preview_inputs
    assert "Independent barrier requests" not in preview_inputs
    assert "app.pet_preview_barrier_vars" not in preview_inputs
    assert "build_pet_preview_barrier_values_from_room(room, position)" in preview_inputs


def test_pet_step8_position_derives_all_six_room_boundary_distances_independently():
    from models.shielding_models import Barrier, Room
    from geometry.geometry_model import RoomGeometry

    geometry = RoomGeometry(length_m=8.0, width_m=6.0, height_m=3.4)
    geometry.source.x_m = 5.5
    geometry.source.y_m = 7.5
    room = Room(
        geometry=geometry,
        barriers=[
            Barrier(name="N wall"), Barrier(name="E wall"), Barrier(name="S wall"),
            Barrier(name="W wall"), Barrier(name="Floor", material="Concrete"),
            Barrier(name="Ceiling", material="Concrete"),
        ],
    )
    position = PetPreviewPosition(2.0, 3.0, 1.2)
    rows = build_pet_preview_barrier_values_from_room(room, position)
    distances = {row["source_name"]: float(row["distance_m"]) for row in rows}

    assert distances == {
        "N wall": 5.0, "E wall": 4.0, "S wall": 3.0,
        "W wall": 2.0, "Floor": 1.2, "Ceiling": 2.2,
    }
    assert distances["N wall"] != geometry.source_to_barrier_distances()["N"]


def test_pet_step8_position_rejects_point_outside_selected_room():
    from models.shielding_models import Barrier, Room
    from geometry.geometry_model import RoomGeometry

    room = Room(geometry=RoomGeometry(length_m=4.0, width_m=6.0, height_m=3.0), barriers=[Barrier()])
    with pytest.raises(ValueError, match="from West"):
        build_pet_preview_barrier_values_from_room(room, PetPreviewPosition(6.1, 2.0, 1.0))


def test_pet_step8_position_remains_outside_production_geometry_but_is_working_project_persisted():
    geometry_model = (ROOT / "geometry" / "geometry_model.py").read_text(encoding="utf-8")
    project_serializer = (ROOT / "services" / "project_serializer.py").read_text(encoding="utf-8")
    preview_panel = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    working_state = (ROOT / "serialization" / "pet_working_project_state.py").read_text(encoding="utf-8")

    assert "pet_preview_position" not in geometry_model
    assert "pet_preview_position" not in project_serializer
    assert "pet_preview_position_vars" in preview_panel
    assert "persisted working state" in preview_panel
    assert "production_eligible" in working_state
    assert "single_source_per_room" in working_state


def test_pet_step9_contract_is_explicitly_single_source_per_room():
    preview = calculate_pet_preview(_values())
    schedule = calculate_pet_barrier_schedule_preview(_values(), _barriers())
    assert preview["single_source_per_room"] is True
    assert schedule["single_source_per_room"] is True
    assert preview["calculation_basis"] == "decay_integrated_point_source_at_1m"

    panel = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert "Exactly one PET patient/source position is modelled per selected room" in panel
    assert "Single PET patient/source position" in panel
