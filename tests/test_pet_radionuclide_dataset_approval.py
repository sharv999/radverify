from pathlib import Path
import pytest
from engine.pet_radionuclide_data import load_pet_radionuclide_dataset
from tools.pet_radionuclide_dataset_approval import (
    PetRadionuclideApprovalError, approve_dataset, confirmation_token, review_dataset,
)

PENDING_DATASET_PATH = Path(__file__).resolve().parents[1] / 'data' / 'pet' / 'pet_radionuclide_physics_reviewed_pending_approval.json'

def test_review_prints_sources_digest_and_confirmation_token():
    text=review_dataset(PENDING_DATASET_PATH)
    ds=load_pet_radionuclide_dataset(PENDING_DATASET_PATH,allow_unapproved=True)
    assert ds.metadata.records_sha256 in text
    assert confirmation_token(ds) in text
    assert "IAEA" in text and "AAPM" in text and "MIRD" in text

def test_approval_is_explicit_separate_and_digest_preserving(tmp_path):
    ds=load_pet_radionuclide_dataset(PENDING_DATASET_PATH,allow_unapproved=True)
    out=tmp_path/'approved.json'
    approve_dataset(PENDING_DATASET_PATH,out,approved_by='Test Physicist',approved_date='2026-07-21',confirmation=confirmation_token(ds))
    approved=load_pet_radionuclide_dataset(out)
    assert approved.metadata.approved_by == 'Test Physicist'
    assert approved.metadata.records_sha256 == ds.metadata.records_sha256
    with pytest.raises(PetRadionuclideApprovalError, match='separate file'):
        approve_dataset(PENDING_DATASET_PATH,PENDING_DATASET_PATH,approved_by='X',approved_date='2026-07-21',confirmation=confirmation_token(ds))
