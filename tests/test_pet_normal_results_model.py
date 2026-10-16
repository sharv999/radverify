from pathlib import Path

from engine.shielding_engine import default_barriers
from models.shielding_models import Project, Room
from geometry.geometry_model import RoomGeometry
from serialization.pet_working_project_state import set_room_pet_working_state
from modalities.pet import PetExposurePhase, PetSourceDomain
from geometry.pet_preview_position import PetPreviewPosition
from services.pet_results_model import build_room_results_model
from services.source_readiness import validate_project_source_readiness


def _project():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18", injected_activity_mbq=250.0, patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0, 1.0),),
    )
    from serialization.pet_working_project_state import PetWorkingProjectState
    set_room_pet_working_state(room, PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.0, 1.0)))
    return Project(project_name="PET", rooms=[room]), room


def test_persisted_pet_dispatch_populates_normal_results_model_only():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    assert len(rows) == len(room.barriers)
    assert all(row["results_source"] == "persisted_pet_single_source" for row in rows)
    assert all(row["source_type"] == "pet_patient" for row in rows)
    assert {row["compliance_status"] for row in rows} <= {"PASS", "FAIL"}
    assert all("required_thickness_mm" in row for row in rows)


def test_pet_results_model_does_not_remove_export_blocker():
    project, room = _project()
    assert build_room_results_model(project, room, fallback_results=[])
    readiness = validate_project_source_readiness(project)
    assert any(item.get("output_blocking") is True for item in readiness["source_results"])


def test_report_modules_do_not_import_pet_results_model():
    for path in Path("reports").glob("*.py"):
        assert "pet_results_model" not in path.read_text(encoding="utf-8")


def test_results_and_barriers_tabs_share_the_canonical_room_results_model():
    text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")
    assert text.count("get_room_results_model(room)") >= 3
    refresh_block = text.split("def refresh_barrier_schedule", 1)[1].split("def render_barrier_risk_panel", 1)[0]
    assert "room_results = app.get_room_results_model(room)" in refresh_block
    assert "room_results = app.get_room_barrier_results(room)" not in refresh_block
