from copy import deepcopy
from pathlib import Path

import pytest

from engine.shielding_engine import default_barriers
from geometry.geometry_model import RoomGeometry
from geometry.pet_preview_position import PetPreviewPosition
from models.shielding_models import Project, Room
from modalities.pet import PetExposurePhase, PetSourceDomain
from serialization.pet_working_project_state import (
    PetWorkingProjectState,
    set_room_pet_working_state,
)
from services.export_eligibility import assess_export_eligibility
from services.pet_combined_report_payload_harness import (
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE,
    PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION,
    PET_COMBINED_SHARED_PROVENANCE_FIELDS,
    PetCombinedReportPayloadEnvelopeError,
    build_non_issueable_pet_combined_report_payload_envelope,
)
from services.pet_report_payload_harness import build_non_issueable_pet_report_payload
from services.pet_results_model import build_room_results_model
from services.pet_source_summary_harness import build_non_issueable_pet_source_summary
from services.source_readiness import validate_project_source_readiness


def _project_room_and_payloads():
    room = Room(name="PET Room", modality="CT", barriers=default_barriers(), geometry=RoomGeometry())
    source = PetSourceDomain(
        radionuclide="F18",
        injected_activity_mbq=250.0,
        patients_per_week=30.0,
        residual_activity_factor=1.0,
        exposure_phases=(
            PetExposurePhase("Uptake", 0.0, 1.0, 1.0),
            PetExposurePhase("Imaging", 1.0, 0.5, 1.0),
        ),
    )
    set_room_pet_working_state(
        room,
        PetWorkingProjectState(source=source, position=PetPreviewPosition(2.0, 2.5, 1.0)),
    )
    project = Project(project_name="PET", rooms=[room])
    rows = build_room_results_model(project, room, fallback_results=[])
    source_payload = build_non_issueable_pet_source_summary(room)
    barrier_payload = build_non_issueable_pet_report_payload(rows)
    return project, source_payload, barrier_payload


def test_combined_envelope_joins_frozen_payloads_and_shared_provenance():
    _project, source_payload, barrier_payload = _project_room_and_payloads()
    envelope = build_non_issueable_pet_combined_report_payload_envelope(
        source_payload=source_payload,
        barrier_payload=barrier_payload,
    )

    assert envelope["envelope_contract_version"] == PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_CONTRACT_VERSION
    assert envelope["envelope_baseline"] == PET_COMBINED_REPORT_PAYLOAD_ENVELOPE_BASELINE
    assert envelope["non_issueable"] is True
    assert envelope["report_integration_open"] is False
    assert envelope["replay_verified"] is True
    assert envelope["source_summary_payload"] == source_payload
    assert envelope["barrier_payload"] == barrier_payload
    assert tuple(envelope["shared_provenance"].keys()) == (
        *PET_COMBINED_SHARED_PROVENANCE_FIELDS,
        "replay_verified",
    )
    assert envelope["shared_provenance"]["replay_verified"] is True


def test_combined_envelope_fails_closed_for_provenance_mismatch():
    _project, source_payload, barrier_payload = _project_room_and_payloads()
    tampered = deepcopy(source_payload)
    tampered["source_summary"]["attenuation_records_sha256"] = "0" * 64

    with pytest.raises(PetCombinedReportPayloadEnvelopeError, match="do not share frozen provenance"):
        build_non_issueable_pet_combined_report_payload_envelope(
            source_payload=tampered,
            barrier_payload=barrier_payload,
        )


def test_combined_envelope_fails_closed_for_unverified_replay():
    _project, source_payload, barrier_payload = _project_room_and_payloads()
    tampered = deepcopy(barrier_payload)
    tampered["shared_provenance"]["replay_verified"] = False

    with pytest.raises(PetCombinedReportPayloadEnvelopeError, match="not deterministic-replay verified"):
        build_non_issueable_pet_combined_report_payload_envelope(
            source_payload=source_payload,
            barrier_payload=tampered,
        )


def test_combined_envelope_rejects_open_or_drifted_child_payloads():
    _project, source_payload, barrier_payload = _project_room_and_payloads()

    open_source = deepcopy(source_payload)
    open_source["report_integration_open"] = True
    with pytest.raises(PetCombinedReportPayloadEnvelopeError, match="not closed and non-issueable"):
        build_non_issueable_pet_combined_report_payload_envelope(
            source_payload=open_source,
            barrier_payload=barrier_payload,
        )

    drifted_barriers = deepcopy(barrier_payload)
    drifted_barriers["permitted_field_count"] = 30
    with pytest.raises(PetCombinedReportPayloadEnvelopeError, match="31-field count"):
        build_non_issueable_pet_combined_report_payload_envelope(
            source_payload=source_payload,
            barrier_payload=drifted_barriers,
        )


def test_combined_envelope_is_disconnected_and_outputs_remain_blocked():
    project, source_payload, barrier_payload = _project_room_and_payloads()
    envelope = build_non_issueable_pet_combined_report_payload_envelope(
        source_payload=source_payload,
        barrier_payload=barrier_payload,
    )
    assert envelope["non_issueable"] is True

    forbidden_token = "pet_combined_report_payload_harness"
    for path in Path("reports").glob("*.py"):
        assert forbidden_token not in path.read_text(encoding="utf-8")
    for path in (
        Path("services/export_eligibility.py"),
        Path("reports/output_pipeline.py"),
    ):
        assert forbidden_token not in path.read_text(encoding="utf-8")

    readiness = validate_project_source_readiness(project)
    assert readiness["blocking"] is True
    eligibility = assess_export_eligibility(preflight=readiness, requested_report_status="Final")
    assert eligibility.can_export_pdf is False
    assert eligibility.can_export_csv is False
    assert eligibility.can_certify is False
