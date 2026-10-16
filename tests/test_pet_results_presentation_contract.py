from pathlib import Path

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import PetWorkingProjectState, set_room_pet_working_state
from services.pet_results_model import build_room_results_model
from services.pet_results_presentation_contract import (
    PET_RESULTS_FIELD_ORDER,
    PET_RESULTS_NON_ISSUEABLE_NOTE,
    PET_RESULTS_PRESENTATION_BASELINE,
    PET_RESULTS_PRESENTATION_CONTRACT_VERSION,
    PET_RESULTS_PROVENANCE_ORDER,
    pet_results_error_text,
    pet_results_room_lines,
)


def _project():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(PetExposurePhase("Uptake", 0.0, 1.0, 1.0),),
    )
    set_room_pet_working_state(room, PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.0, 1.0)))
    return Project(project_name="PET", rooms=[room]), room


def test_pet_results_rows_bind_to_frozen_presentation_and_provenance_contract():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    assert rows
    first = rows[0]
    assert first["results_presentation_contract_version"] == PET_RESULTS_PRESENTATION_CONTRACT_VERSION
    assert first["results_presentation_baseline"] == PET_RESULTS_PRESENTATION_BASELINE
    assert first["replay_verified"] is True
    for key in PET_RESULTS_PROVENANCE_ORDER:
        assert key in first
    for key in PET_RESULTS_FIELD_ORDER:
        assert key in first


def test_pet_results_lines_have_frozen_order_notes_and_provenance():
    project, room = _project()
    rows = build_room_results_model(project, room, fallback_results=[])
    text = "\n".join(line for line, _tag in pet_results_room_lines(room.name, rows))
    assert PET_RESULTS_NON_ISSUEABLE_NOTE in text
    positions = [text.index(label) for label in (
        "Source-to-barrier distance",
        "Occupancy factor T",
        "Design goal",
        "Unshielded weekly dose at barrier",
        "Transmitted weekly dose",
        "Compliance status",
    )]
    assert positions == sorted(positions)
    assert "Provenance manifest:" in text
    assert "Radionuclide records SHA-256:" in text
    assert "Attenuation records SHA-256:" in text
    assert "Calculation reasoning:" in text


def test_pet_results_error_text_is_deterministic_and_user_visible():
    assert pet_results_error_text(ValueError("bad PET state")) == "PET Results unavailable: bad PET state"


def test_pet_results_presentation_contract_is_not_imported_by_reports():
    for path in Path("reports").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "pet_results_presentation_contract" not in text
        assert "pet_results_model" not in text


def test_results_rendering_uses_pet_contract_and_preserves_export_blocker_boundary():
    text = Path("tabs/results_tab_rendering.py").read_text(encoding="utf-8")
    assert "pet_results_room_lines" in text
    assert "pet_results_error_text" in text
    readiness = Path("services/source_readiness.py").read_text(encoding="utf-8")
    assert "output_blocking" in readiness
