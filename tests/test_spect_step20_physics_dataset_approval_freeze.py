"""SPECT Step 20 physics dataset approval/freeze regression guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from engine.spect_barrier_calculation import SPECT_PRACTICAL_DATASET_PATH
from engine.spect_practical_transmission import (
    SPECT_FROZEN_PRACTICAL_DATASET_ID,
    SPECT_FROZEN_PRACTICAL_DATASET_REVISION,
    SPECT_FROZEN_PRACTICAL_RECORDS_SHA256,
    SpectPracticalTransmissionError,
    load_frozen_spect_tc99m_practical_dataset,
    load_spect_tc99m_practical_dataset,
)
from engine.spect_radionuclide_data import (
    SPECT_FROZEN_RADIONUCLIDE_DATASET_ID,
    SPECT_FROZEN_RADIONUCLIDE_DATASET_REVISION,
    SPECT_FROZEN_RADIONUCLIDE_RECORDS_SHA256,
    SpectRadionuclideDataError,
    load_frozen_spect_radionuclide_dataset,
    load_spect_radionuclide_dataset,
    records_sha256,
)
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import (
    SPECT_CALCULATION_BLOCK_REASON,
    SPECT_RADIONUCLIDE_DATASET_METADATA,
    SPECT_RADIONUCLIDE_DATASET_PATH,
)
from tools.spect_physics_dataset_approval import (
    DEFAULT_MANIFEST,
    canonical_json_sha256,
    verify_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FROZEN = ROOT / "data" / "spect" / "spect_radionuclide_physics_approved_frozen.json"
PRACTICAL_FROZEN = ROOT / "data" / "spect" / "spect_tc99m_practical_transmission_approved_frozen.json"
SOURCE_DEVELOPMENT = ROOT / "data" / "spect" / "spect_radionuclide_physics_development.json"
PRACTICAL_DEVELOPMENT = ROOT / "data" / "spect" / "spect_tc99m_practical_transmission_development.json"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_step20_active_source_dataset_is_exact_frozen_revision():
    dataset = load_frozen_spect_radionuclide_dataset(SPECT_RADIONUCLIDE_DATASET_PATH)

    assert SPECT_RADIONUCLIDE_DATASET_PATH == SOURCE_FROZEN
    assert dataset.metadata.dataset_id == SPECT_FROZEN_RADIONUCLIDE_DATASET_ID
    assert dataset.metadata.revision == SPECT_FROZEN_RADIONUCLIDE_DATASET_REVISION
    assert dataset.metadata.records_sha256 == SPECT_FROZEN_RADIONUCLIDE_RECORDS_SHA256
    assert dataset.metadata.approval_status == "physics_approved_frozen_nonproduction"
    assert SPECT_RADIONUCLIDE_DATASET_METADATA == dataset.metadata


def test_step20_tc99m_point_source_constant_is_source_derived_and_frozen():
    dataset = load_frozen_spect_radionuclide_dataset(SOURCE_FROZEN)
    tc99m = dataset.records["Tc99m"]

    # Oumano et al. Table 4 (citing Smith & Stabin):
    # 0.795 R/(mCi h) at 1 cm and f-factor 0.959 cGy/R.
    # Convert cGy -> uGy, 1 cm -> 1 m, and mCi -> MBq.
    derived = 0.795 * 0.959 * 10000.0 / (100.0 ** 2) / 37.0
    assert derived == pytest.approx(0.02060554054054054)
    assert tc99m.dose_rate_constant_uSv_h_per_MBq_at_1m == pytest.approx(
        derived, abs=0.00001
    )
    assert tc99m.half_life_h == pytest.approx(6.0067)
    assert "10.1002/acm2.70084" in tc99m.dose_rate_provenance
    assert "unattenuated point-source constant" in tc99m.dose_rate_provenance


def test_step20_active_practical_dataset_is_exact_frozen_revision():
    dataset = load_frozen_spect_tc99m_practical_dataset(SPECT_PRACTICAL_DATASET_PATH)

    assert SPECT_PRACTICAL_DATASET_PATH == PRACTICAL_FROZEN
    assert dataset.metadata.dataset_id == SPECT_FROZEN_PRACTICAL_DATASET_ID
    assert dataset.metadata.revision == SPECT_FROZEN_PRACTICAL_DATASET_REVISION
    assert dataset.metadata.records_sha256 == SPECT_FROZEN_PRACTICAL_RECORDS_SHA256
    assert dataset.metadata.approval_status == "physics_approved_frozen_nonproduction"

    lead = dataset.records["lead"]
    concrete = dataset.records["concrete_2300kg_m3"]
    assert (lead.alpha_mm_inv, lead.beta_mm_inv, lead.gamma) == pytest.approx(
        (2.558, 1.010, 4.344)
    )
    assert lead.reference_fractional_layers_mm["tvl"] == pytest.approx(0.870)
    assert concrete.reference_fractional_layers_mm["tvl"] == pytest.approx(122.0)


def test_step20_strict_source_loader_rejects_edited_rehashed_copy(tmp_path):
    payload = json.loads(SOURCE_FROZEN.read_text(encoding="utf-8"))
    payload["records"][0]["half_life_h"] = 6.1
    digest = records_sha256(payload)
    payload["metadata"]["records_sha256"] = digest
    payload["metadata"]["approved_records_sha256"] = digest
    changed = tmp_path / "source-rehashed.json"
    _write_json(changed, payload)

    # It is internally self-consistent, but not the exact Step 20 freeze.
    assert load_spect_radionuclide_dataset(changed).metadata.records_sha256 == digest
    with pytest.raises(SpectRadionuclideDataError, match="frozen Step 20 digest"):
        load_frozen_spect_radionuclide_dataset(changed)


def test_step20_strict_practical_loader_rejects_edited_rehashed_copy(tmp_path):
    payload = json.loads(PRACTICAL_FROZEN.read_text(encoding="utf-8"))
    payload["records"][0]["alpha_mm_inv"] = 2.559
    canonical = json.dumps(
        payload["records"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload["metadata"]["records_sha256"] = digest
    changed = tmp_path / "practical-rehashed.json"
    _write_json(changed, payload)

    assert load_spect_tc99m_practical_dataset(changed).metadata.records_sha256 == digest
    with pytest.raises(SpectPracticalTransmissionError, match="frozen Step 20 digest"):
        load_frozen_spect_tc99m_practical_dataset(changed)


def test_step20_manifest_pins_canonical_payload_hashes_and_verifies():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["status"] == "approved_locked_verified_nonproduction"
    assert manifest["production_enabled"] is False
    source_entry = manifest["datasets"]["radionuclide_source"]
    practical_entry = manifest["datasets"]["practical_transmission"]
    assert source_entry["canonical_payload_sha256"] == canonical_json_sha256(SOURCE_FROZEN)
    assert practical_entry["canonical_payload_sha256"] == canonical_json_sha256(PRACTICAL_FROZEN)

    text = verify_manifest()
    assert "APPROVED / LOCKED / VERIFIED" in text
    assert "SPECT production enabled: NO" in text


def test_step20_canonical_payload_hash_is_line_ending_independent(tmp_path):
    payload = SOURCE_FROZEN.read_text(encoding="utf-8")
    crlf_copy = tmp_path / SOURCE_FROZEN.name
    crlf_copy.write_bytes(payload.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    assert canonical_json_sha256(crlf_copy) == canonical_json_sha256(SOURCE_FROZEN)


def test_step20_manifest_detects_semantic_dataset_edit(tmp_path, monkeypatch):
    manifest_payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    changed = json.loads(SOURCE_FROZEN.read_text(encoding="utf-8"))
    changed["metadata"]["description"] += " altered"

    copied = ROOT / "data" / "spect" / "_step20_semantic_edit_test.json"
    try:
        _write_json(copied, changed)
        manifest_payload["datasets"]["radionuclide_source"]["path"] = str(
            copied.relative_to(ROOT)
        ).replace("\\", "/")
        manifest = tmp_path / "manifest.json"
        _write_json(manifest, manifest_payload)

        with pytest.raises(ValueError, match="canonical payload SHA-256 mismatch"):
            verify_manifest(manifest)
    finally:
        copied.unlink(missing_ok=True)


def test_step20_development_datasets_remain_as_historical_nonproduction_inputs():
    source = json.loads(SOURCE_DEVELOPMENT.read_text(encoding="utf-8"))
    practical = json.loads(PRACTICAL_DEVELOPMENT.read_text(encoding="utf-8"))

    assert source["metadata"]["approval_status"] == "development_nonproduction"
    assert "pending separate dataset approval" in source["records"][0]["dose_rate_provenance"]
    assert practical["metadata"]["approval_status"] == "development_nonproduction"


def test_step20_does_not_enable_spect_production():
    assert "SPECT" in production_modality_names()
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON

    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["production_enabled"] is False


def test_step20_keeps_narrow_beam_attenuation_reference_only():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    reference = manifest["datasets"]["narrow_beam_reference"]
    assert reference["approval_status"] == "development_nonproduction"
    assert reference["role"] == "reference_only_not_practical_shielding"


def test_step20_approval_freeze_does_not_leak_into_results_or_reports():
    forbidden = (
        "spect_physics_approval_manifest",
        "load_frozen_spect_radionuclide_dataset",
        "load_frozen_spect_tc99m_practical_dataset",
    )
    paths = [ROOT / "app.py", ROOT / "engine" / "shielding_engine.py"]
    paths.extend((ROOT / "reports").glob("*.py"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production/report path {path}"
