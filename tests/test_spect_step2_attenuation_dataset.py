from __future__ import annotations

import json
from math import isclose, log
from pathlib import Path

import pytest

from engine.spect_attenuation_data import (
    SPECT_ATTENUATION_DATASET_SCOPE,
    SPECT_ATTENUATION_DATASET_STATUS,
    SPECT_TC99M_REFERENCE_ENERGY_KEV,
    SpectAttenuationDataError,
    load_spect_tc99m_attenuation_dataset,
)


DATASET = Path("data/spect/spect_tc99m_attenuation_development.json")


def _mutated_dataset(tmp_path: Path, mutate) -> Path:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_spect_step2_dataset_is_tc99m_specific_headless_and_nonproduction():
    dataset = load_spect_tc99m_attenuation_dataset(DATASET)

    assert dataset.metadata.dataset_id == "spect-tc99m-attenuation-nist-xcom-development"
    assert dataset.metadata.approval_status == SPECT_ATTENUATION_DATASET_STATUS
    assert dataset.metadata.model_scope == SPECT_ATTENUATION_DATASET_SCOPE
    assert set(dataset.records) == {"lead", "concrete_2300kg_m3"}

    for record in dataset.records.values():
        assert record.radionuclide == "Tc99m"
        assert record.nominal_energy_kev == pytest.approx(SPECT_TC99M_REFERENCE_ENERGY_KEV)
        assert record.radiation_type == "tc99m_140kev"
        assert record.tvl_key == "tc99m_140kev"
        assert record.attenuation_geometry == "narrow_beam"
        assert record.provenance.source_organisation.startswith("National Institute")
        assert "Narrow-beam" in record.provenance.notes


def test_spect_step2_nist_xcom_derived_values_are_internally_consistent():
    dataset = load_spect_tc99m_attenuation_dataset(DATASET)

    for record in dataset.records.values():
        mu = record.mass_attenuation_coefficient_cm2_g * record.density_g_cm3
        assert record.linear_attenuation_coefficient_cm_inv == pytest.approx(mu, rel=2e-6)
        assert record.hvl_mm == pytest.approx(log(2.0) / mu * 10.0, rel=2e-6)
        assert record.tvl_mm == pytest.approx(log(10.0) / mu * 10.0, rel=2e-6)

    assert dataset.records["lead"].tvl_mm == pytest.approx(0.855499524522)
    assert dataset.records["concrete_2300kg_m3"].tvl_mm == pytest.approx(67.604098823401)


def test_spect_step2_dataset_digest_fails_closed_on_record_edit(tmp_path):
    path = _mutated_dataset(
        tmp_path,
        lambda payload: payload["records"][0].__setitem__("tvl_mm", 1.0),
    )
    with pytest.raises(SpectAttenuationDataError, match="digest"):
        load_spect_tc99m_attenuation_dataset(path)


def test_spect_step2_rejects_production_status_even_if_record_digest_is_valid(tmp_path):
    def mutate(payload):
        payload["metadata"]["approval_status"] = "production_approved"

    path = _mutated_dataset(tmp_path, mutate)
    with pytest.raises(SpectAttenuationDataError, match="development_nonproduction"):
        load_spect_tc99m_attenuation_dataset(path)


def test_spect_step2_rejects_broad_beam_or_other_radionuclide_claims_before_digest(tmp_path):
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["metadata"]["model_scope"] = "broad_beam"
    # Metadata is outside the records digest, so this exercises the scope gate.
    path = tmp_path / "wrong_scope.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SpectAttenuationDataError, match="narrow-beam reference-only"):
        load_spect_tc99m_attenuation_dataset(path)


def test_spect_step2_remains_disconnected_from_solver_ui_reports_and_spect_plugin():
    forbidden = (
        "spect_tc99m_attenuation_development",
        "load_spect_tc99m_attenuation_dataset",
        "SpectTc99mAttenuationRecord",
    )
    paths = [Path("app.py"), Path("engine/shielding_engine.py"), Path("modalities/spect.py")]
    paths.extend(Path("reports").glob("*.py"))
    paths.extend(Path("tabs").glob("*.py"))
    paths.extend(Path("ui").glob("*.py"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production/headless Step 1 path {path}"
