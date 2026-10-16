import json
from copy import deepcopy
from pathlib import Path

import pytest

from engine.pet_radionuclide_data import (
    PRODUCTION_DATASET_ID,
    PRODUCTION_DATASET_REVISION,
    PRODUCTION_RECORDS_SHA256,
    PetRadionuclideDataError,
    load_pet_radionuclide_dataset,
    load_production_pet_radionuclide_dataset,
    records_sha256,
)
from modalities.pet import PET_RADIONUCLIDE_DATASET_PATH, PET_RADIONUCLIDES


PENDING_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "pet"
    / "pet_radionuclide_physics_reviewed_pending_approval.json"
)


def _write_payload(tmp_path: Path, payload: dict, name: str = "dataset.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def test_pet_runtime_uses_exact_production_approved_dataset():
    dataset = load_production_pet_radionuclide_dataset(PET_RADIONUCLIDE_DATASET_PATH)
    assert PET_RADIONUCLIDE_DATASET_PATH.name == "pet_radionuclide_physics_approved.json"
    assert dataset.metadata.dataset_id == PRODUCTION_DATASET_ID
    assert dataset.metadata.revision == PRODUCTION_DATASET_REVISION
    assert dataset.metadata.approval_status == "production_approved"
    assert dataset.metadata.records_sha256 == PRODUCTION_RECORDS_SHA256

    payload = json.loads(Path(PET_RADIONUCLIDE_DATASET_PATH).read_text(encoding="utf-8"))
    assert dataset.metadata.records_sha256 == records_sha256(payload)
    assert payload["metadata"]["approved_records_sha256"] == PRODUCTION_RECORDS_SHA256


def test_pending_review_dataset_remains_blocked_from_production_loading():
    reviewed = load_pet_radionuclide_dataset(PENDING_DATASET_PATH, allow_unapproved=True)
    assert reviewed.metadata.approval_status == "reviewed_pending_user_approval"
    with pytest.raises(PetRadionuclideDataError, match="not production approved"):
        load_production_pet_radionuclide_dataset(PENDING_DATASET_PATH)


def test_production_loading_fails_closed_for_wrong_revision_even_if_self_consistent(tmp_path):
    payload = json.loads(Path(PET_RADIONUCLIDE_DATASET_PATH).read_text(encoding="utf-8"))
    payload = deepcopy(payload)
    payload["metadata"]["revision"] = "2026-07-21-review-2"
    path = _write_payload(tmp_path, payload, "wrong_revision.json")

    # The generic approved loader accepts the unchanged, self-consistent records,
    # but production eligibility is pinned to the explicitly approved revision.
    assert load_pet_radionuclide_dataset(path).metadata.records_sha256 == PRODUCTION_RECORDS_SHA256
    with pytest.raises(PetRadionuclideDataError, match="revision"):
        load_production_pet_radionuclide_dataset(path)


def test_production_loading_fails_closed_for_changed_records_even_if_rehashed(tmp_path):
    payload = json.loads(Path(PET_RADIONUCLIDE_DATASET_PATH).read_text(encoding="utf-8"))
    payload = deepcopy(payload)
    payload["records"][0]["half_life_h"] = 1.83
    payload["metadata"]["approved_records_sha256"] = records_sha256(payload)
    path = _write_payload(tmp_path, payload, "rehashed_modified_records.json")

    # Internal approval hash consistency is necessary but not sufficient: the
    # production loader also requires the frozen approved digest.
    changed = load_pet_radionuclide_dataset(path)
    assert changed.metadata.records_sha256 != PRODUCTION_RECORDS_SHA256
    with pytest.raises(PetRadionuclideDataError, match="production-approved digest"):
        load_production_pet_radionuclide_dataset(path)


def test_production_loading_fails_closed_for_wrong_dataset_id(tmp_path):
    payload = json.loads(Path(PET_RADIONUCLIDE_DATASET_PATH).read_text(encoding="utf-8"))
    payload = deepcopy(payload)
    payload["metadata"]["dataset_id"] = "pet-radionuclide-physics-other"
    path = _write_payload(tmp_path, payload, "wrong_dataset_id.json")

    with pytest.raises(PetRadionuclideDataError, match="dataset ID"):
        load_production_pet_radionuclide_dataset(path)


def test_verified_half_lives_and_source_backed_dose_constants_are_frozen():
    f18 = PET_RADIONUCLIDES["F18"]
    ga68 = PET_RADIONUCLIDES["Ga68"]
    assert f18.half_life_h == 1.8295
    assert ga68.half_life_h == 1.1285
    assert f18.dose_rate_constant_uSv_h_per_MBq_at_1m == 0.092
    assert ga68.dose_rate_constant_uSv_h_per_MBq_at_1m == 0.085
    assert "IAEA" in f18.half_life_provenance.source_title
    assert "AAPM" in f18.dose_rate_provenance.source_title
    assert "MIRD" in ga68.half_life_provenance.source_title
    assert "model-derived" in ga68.dose_rate_provenance.derivation
