from pathlib import Path
import inspect

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetContractError, PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from services.pet_results_model import build_room_results_model
from tabs.pet_preview_panel import (
    PET_BARRIER_RESULTS_PREVIEW_COLUMNS,
    build_pet_barrier_results_preview_rows,
    refresh_pet_barrier_results_preview,
)

ROOT = Path(__file__).resolve().parents[1]


def _project_and_room():
    room = Room(
        name="PET Room",
        modality="CT",
        barriers=default_barriers(),
        geometry=RoomGeometry(),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(
            source=PetSourceDomain(
                radionuclide="F18",
                injected_activity_mbq=250.0,
                patients_per_week=30.0,
                residual_activity_factor=1.0,
                exposure_phases=(
                    PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
                    PetExposurePhase("Imaging", 1.0, 0.5, 1.0),
                ),
            ),
            position=PetPreviewPosition(2.0, 2.5, 1.0),
        ),
    )
    return Project(project_name="PET", rooms=[room]), room


class _App:
    def __init__(self, project):
        self.project = project

    def get_room_results_model(self, room):
        return build_room_results_model(self.project, room, fallback_results=[])


def test_pet_barrier_results_preview_freezes_requested_read_only_columns():
    assert tuple(key for key, _heading, _width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS) == (
        "barrier_name",
        "material",
        "distance_m",
        "occupancy_factor",
        "design_goal_uSv_per_week",
        "unshielded_weekly_dose_uSv",
        "required_thickness_mm",
        "provided_thickness_mm",
        "margin_mm",
        "transmitted_dose_uSv_per_week",
        "barrier_transmission_factor_B",
        "required_tvl_count",
        "compliance_status",
    )


def test_pet_barrier_results_preview_consumes_canonical_pet_results_only():
    project, room = _project_and_room()
    rows = build_pet_barrier_results_preview_rows(_App(project), room=room)
    assert len(rows) == len(room.barriers)
    assert set(rows[0]) == {key for key, _heading, _width in PET_BARRIER_RESULTS_PREVIEW_COLUMNS}
    assert rows[0]["barrier_name"] == room.barriers[0].name
    assert rows[0]["compliance_status"] in {"PASS", "FAIL"}


def test_pet_barrier_results_preview_rejects_non_pet_results_rows():
    class BadApp:
        def get_room_results_model(self, room):
            return [{"results_source": "ct", "barrier_name": "N wall"}]

    _project, room = _project_and_room()
    with pytest.raises(PetContractError, match="non-PET canonical Results row"):
        build_pet_barrier_results_preview_rows(BadApp(), room=room)


def test_sources_panel_places_nonproduction_results_table_below_provenance():
    text = (ROOT / "tabs" / "pet_preview_panel.py").read_text(encoding="utf-8")
    assert 'text="PET Barrier Results Preview — non-production"' in text
    assert "app.pet_barrier_results_preview_tree = ttk.Treeview(" in text
    assert 'show="headings"' in text
    assert 'orient="horizontal"' in text
    assert "refresh_pet_barrier_results_preview(app, room=room)" in text
    assert text.index('text="PET input and provenance preview"') < text.index(
        'text="PET Barrier Results Preview — non-production"'
    )


def test_pet_barrier_results_preview_remains_read_only_and_outside_output_paths():
    source = inspect.getsource(refresh_pet_barrier_results_preview)
    assert "tree.insert" in source
    assert "tree.delete" in source
    assert "filedialog" not in source
    assert "report_generator" not in source
    assert "results_exporter" not in source
    assert "output_pipeline" not in source

    forbidden_token = "pet_barrier_results_preview_tree"
    for path in tuple((ROOT / "reports").glob("*.py")) + (
        ROOT / "services" / "export_eligibility.py",
        ROOT / "services" / "report_certification.py",
        ROOT / "services" / "file_output_guard.py",
    ):
        assert forbidden_token not in path.read_text(encoding="utf-8")
