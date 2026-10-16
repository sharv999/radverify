from __future__ import annotations

from pathlib import Path

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Barrier, Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from modalities.spect import SpectSourceDomain
from reports.results_payload_builder import build_results_payload
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from serialization.spect_working_project_state import new_spect_working_project_state, set_room_spect_working_state
from services.pet_results_model import build_room_results_model as build_pet_results_model
from services.spect_results_model import build_room_results_model as build_spect_results_model
from services.pet_spect_normal_report_integration_readiness import (
    STEP40_ISSUED_OUTPUT_ENABLEMENT,
    require_step40_normal_report_integration_ready,
)
from services.pet_spect_normal_report_route import (
    PetSpectNormalReportRouteError,
    build_non_issueable_pet_spect_room_report_payload,
)

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _App:
    def __init__(self, project):
        self.project = project
        self.project_vars = {}
        self.global_energy_var = _Var("511 keV")
        self.solver_mode_var = _Var("")

    def get_sources_for_room(self, _room_name):
        return []

    def get_room_results_model(self, room):
        if str(room.modality).upper() == "PET":
            return build_pet_results_model(self.project, room, fallback_results=[])
        if str(room.modality).upper() == "SPECT":
            return build_spect_results_model(self.project, room, fallback_results=[])
        raise AssertionError("Unexpected modality in Step 40 test app")

    def _row_confidence_from_live(self, *_args):
        return 1.0


def _pet_project():
    room = Room(
        name="PET Room",
        modality="PET",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy="Pb 5 mm",
                thickness_mm=5.0,
                distance_m=4.0,
                occupancy_factor=0.25,
                design_goal_uSv_per_week=20.0,
            )
        ],
        geometry=RoomGeometry(),
    )
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=10.0,
        residual_activity_factor=1.0,
        exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0, 1.0),),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.0, 1.0)),
    )
    return Project(project_name="PET Step 40", rooms=[room]), room


def _spect_project():
    room = Room(
        name="SPECT Room",
        modality="SPECT",
        barriers=[
            Barrier(
                name="North wall",
                material="Pb",
                material_legacy="Pb 1 mm",
                thickness_mm=1.0,
                distance_m=3.0,
                occupancy_factor=0.25,
                design_goal_uSv_per_week=10.0,
            )
        ],
        geometry=RoomGeometry(),
    )
    set_room_spect_working_state(
        room,
        new_spect_working_project_state(
            SpectSourceDomain(
                radionuclide="Tc99m",
                administered_activity_mbq=600.0,
                patients_per_week=20.0,
                imaging_duration_h=0.5,
            )
        ),
    )
    return Project(project_name="SPECT Step 40", rooms=[room]), room


@pytest.mark.parametrize("factory", [_pet_project, _spect_project])
def test_step40_normal_report_builder_consumes_closed_modal_results_without_generic_fallback(factory):
    project, room = factory()
    payload = build_results_payload(_App(project))
    room_payload = payload["rooms"][0]
    assert room_payload["error"] == ""
    assert room_payload["wall_result_count"] == len(room.barriers)
    assert len(room_payload["barriers"]) == len(room.barriers)
    route = room_payload["pet_spect_report_route"]
    assert route["non_issueable"] is True
    assert route["issueable"] is False
    assert route["payload"]["non_issueable"] is True
    assert route["payload"]["issueable"] is False
    assert payload["export_eligibility"]["can_export_pdf"] is False
    assert payload["export_eligibility"]["can_export_csv"] is False
    assert payload["export_eligibility"]["can_certify"] is False


def test_step40_pet_spect_route_fails_closed_on_openings_instead_of_generic_opening_calculation():
    project, room = _pet_project()
    class Opening:
        opening_type = "door"
    room.geometry.openings = [Opening()]
    with pytest.raises(PetSpectNormalReportRouteError, match="openings"):
        build_non_issueable_pet_spect_room_report_payload(_App(project), room)


def test_step40_report_builder_has_explicit_no_fallback_wiring_for_pet_spect_but_keeps_ct_path():
    builder = (ROOT / "reports" / "results_payload_builder.py").read_text(encoding="utf-8-sig")
    schedule = (ROOT / "reports" / "barrier_schedule.py").read_text(encoding="utf-8-sig")
    assert "build_non_issueable_pet_spect_room_report_payload" in builder
    assert "canonical_result_rows_from_room_report_payload" in builder
    assert "allow_generic_fallback=not pet_spect_room" in builder
    assert "compute_room_barrier_table(" in builder  # established CT path retained
    assert "allow_generic_fallback: bool = True" in schedule
    assert "generic recalculation is disabled" in schedule
    assert "generic opening recalculation is disabled" in schedule


def test_step40_common_route_does_not_import_generic_calculation_or_issueable_output_modules():
    text = (ROOT / "services" / "pet_spect_normal_report_route.py").read_text(encoding="utf-8")
    forbidden = (
        "engine.shielding_engine",
        "compute_room_barrier_table",
        "calc_barrier_result",
        "reports.report_generator",
        "reports.output_pipeline",
        "results_exporter",
        "report_certification",
    )
    assert all(token not in text for token in forbidden)


def test_step40_readiness_is_green_while_all_issued_output_remains_closed():
    result = require_step40_normal_report_integration_ready()
    assert STEP40_ISSUED_OUTPUT_ENABLEMENT is False
    assert result["normal_report_payload_integration_ready"] is True
    assert result["pet_spect_generic_recalculation_disabled"] is True
    assert result["issued_pdf_ready"] is False
    assert result["machine_export_ready"] is False
    assert result["certification_ready"] is False


def test_step40_cli_reports_ready_payload_integration_but_closed_output(capsys):
    from tools import pet_spect_normal_report_integration

    assert pet_spect_normal_report_integration.main() == 0
    out = capsys.readouterr().out
    assert "PET/SPECT STEP 40 NORMAL REPORT INTEGRATION" in out
    assert "Normal report payload integration ready: YES" in out
    assert "PET/SPECT generic recalculation disabled: YES" in out
    assert "Issued PDF ready: NO" in out
    assert "Machine export ready: NO" in out
    assert "Certification ready: NO" in out


def test_step40_document_records_nonissueable_go_and_issued_output_no_go():
    text = (ROOT / "docs" / "architecture" / "PET_SPECT_Normal_Report_Integration_Step_40.md").read_text(encoding="utf-8")
    assert "GO for non-issueable normal report-payload integration" in text
    assert "NO-GO for issued PDF, machine export, certification, and signatures" in text
    assert "There is no PET/SPECT fallback" in text
