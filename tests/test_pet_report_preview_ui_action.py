from pathlib import Path
import inspect

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetContractError, PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from services.export_eligibility import assess_export_eligibility
from services.pet_results_model import build_room_results_model
from services.source_readiness import validate_project_source_readiness
from tabs.pet_preview_panel import (
    build_pet_report_preview_lines_for_app,
    show_pet_report_preview,
)

ROOT = Path(__file__).resolve().parents[1]


def _project_and_room():
    room = Room(
        name="PET Room",
        modality="CT",
        barriers=default_barriers(),
        geometry=RoomGeometry(),
    )
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 0.8),
        ),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(
            source=source,
            position=PetPreviewPosition(2.0, 2.5, 1.0),
        ),
    )
    return Project(project_name="PET", rooms=[room]), room


class _PreviewApp:
    def __init__(self, project):
        self.project = project

    def get_room_results_model(self, room):
        return build_room_results_model(self.project, room, fallback_results=[])


def test_pet_ui_action_builds_frozen_plain_text_preview_in_memory_only():
    project, room = _project_and_room()
    lines = build_pet_report_preview_lines_for_app(_PreviewApp(project), room=room)

    assert isinstance(lines, list)
    assert lines[0] == "PET shielding assessment — non-issueable preview"
    assert lines[-1] == "END OF NON-ISSUEABLE PET PREVIEW"
    assert any(line == "Administered activity per patient: 250.000 MBq/patient" for line in lines)
    assert any("Barrier | Material | Distance [m]" in line for line in lines)


def test_pet_ui_action_requires_selected_room_and_canonical_results_model():
    class EmptyApp:
        pass

    with pytest.raises(PetContractError, match="Select a room"):
        build_pet_report_preview_lines_for_app(EmptyApp())

    _project, room = _project_and_room()
    with pytest.raises(PetContractError, match="Canonical PET Results"):
        build_pet_report_preview_lines_for_app(EmptyApp(), room=room)


def test_pet_preview_window_is_read_only_and_has_no_issueable_actions():
    source = inspect.getsource(show_pet_report_preview)
    assert 'tk.Toplevel(app)' in source
    assert 'preview_text.configure(state="disabled")' in source
    assert 'text="Close"' in source
    assert "filedialog" not in source
    assert "asksaveasfilename" not in source
    assert "print(" not in source
    assert "report_generator" not in source
    assert "results_exporter" not in source
    assert "output_pipeline" not in source


def test_sources_panel_exposes_dedicated_nonproduction_read_only_action():
    text = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert 'text="PET report preview — non-production"' in text
    assert 'text="Open Read-only PET Report Preview..."' in text
    assert "In-memory display only — no save, print, PDF, CSV/JSON, certification or report output." in text
    assert "show_pet_report_preview(app)" in text


def test_pet_ui_preview_action_does_not_open_output_paths_and_blocker_remains():
    forbidden_token = "build_pet_report_preview_lines_for_app"
    for path in tuple((ROOT / "reports").glob("*.py")) + (
        ROOT / "services" / "export_eligibility.py",
        ROOT / "services" / "report_certification.py",
        ROOT / "services" / "file_output_guard.py",
    ):
        assert forbidden_token not in path.read_text(encoding="utf-8")

    project, _room = _project_and_room()
    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
