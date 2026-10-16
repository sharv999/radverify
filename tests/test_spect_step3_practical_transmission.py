from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.spect_practical_transmission import (
    SPECT_PRACTICAL_DATASET_STATUS,
    SPECT_PRACTICAL_MODEL_SCOPE,
    SpectPracticalTransmissionError,
    archer_required_thickness,
    archer_transmission,
    calculate_tc99m_required_thickness,
    calculate_tc99m_transmission,
    load_spect_tc99m_practical_dataset,
)


DATASET = Path("data/spect/spect_tc99m_practical_transmission_development.json")


def _mutated_dataset(tmp_path: Path, mutate) -> Path:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "mutated_step3.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_spect_step3_dataset_is_tc99m_broad_beam_headless_nonproduction():
    dataset = load_spect_tc99m_practical_dataset(DATASET)

    assert dataset.metadata.approval_status == SPECT_PRACTICAL_DATASET_STATUS
    assert dataset.metadata.model_scope == SPECT_PRACTICAL_MODEL_SCOPE
    assert dataset.metadata.room_scatter_caution_below_transmission == pytest.approx(0.01)
    assert dataset.metadata.source_model_min_transmission == pytest.approx(0.001)
    assert set(dataset.records) == {
        "lead",
        "gypsum",
        "concrete_1600kg_m3",
        "concrete_2300kg_m3",
        "a514_steel",
        "glass_2500kg_m3",
    }

    for record in dataset.records.values():
        assert record.radionuclide == "Tc99m"
        assert record.radiation_type == "tc99m_140kev"
        assert record.tvl_key == "tc99m_140kev"
        assert "10.1002/acm2.70084" in record.provenance.reference_id
        assert "Table 2" in record.provenance.table_or_section
        assert "broad-beam" in record.provenance.model_notes


def test_spect_step3_archer_coefficients_reproduce_published_fractional_layers():
    dataset = load_spect_tc99m_practical_dataset(DATASET)

    lead = dataset.records["lead"]
    concrete = dataset.records["concrete_2300kg_m3"]

    assert archer_required_thickness(lead, 0.5) == pytest.approx(0.243, abs=0.02)
    assert archer_required_thickness(lead, 0.1) == pytest.approx(0.870, abs=0.02)
    assert archer_required_thickness(lead, 0.01) == pytest.approx(1.77, abs=0.03)
    assert archer_required_thickness(concrete, 0.5) == pytest.approx(44.3, rel=0.01)
    assert archer_required_thickness(concrete, 0.1) == pytest.approx(122.0, rel=0.01)
    assert archer_required_thickness(concrete, 0.01) == pytest.approx(211.0, rel=0.01)


def test_spect_step3_archer_forward_inverse_round_trip():
    dataset = load_spect_tc99m_practical_dataset(DATASET)

    for record in dataset.records.values():
        for target in (0.5, 0.1, 0.03, 0.01, 0.001):
            thickness = archer_required_thickness(record, target)
            assert archer_transmission(record, thickness) == pytest.approx(target, rel=1e-10)
        assert archer_transmission(record, 0.0) == pytest.approx(1.0)
        assert archer_required_thickness(record, 1.0) == pytest.approx(0.0)


def test_spect_step3_low_transmission_scope_is_explicit_not_silently_clamped():
    dataset = load_spect_tc99m_practical_dataset(DATASET)

    ordinary = calculate_tc99m_required_thickness(
        dataset, material_key="lead", target_transmission=0.1
    )
    caution = calculate_tc99m_required_thickness(
        dataset, material_key="lead", target_transmission=0.01
    )
    extrapolated = calculate_tc99m_required_thickness(
        dataset, material_key="lead", target_transmission=0.0005
    )

    assert ordinary.room_scatter_caution is False
    assert ordinary.source_model_extrapolation is False
    assert caution.room_scatter_caution is True
    assert caution.source_model_extrapolation is False
    assert "room-scatter" in caution.scope_note
    assert extrapolated.room_scatter_caution is True
    assert extrapolated.source_model_extrapolation is True
    assert "extrapolation" in extrapolated.scope_note


def test_spect_step3_forward_result_carries_provenance_and_scope_warning():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    lead = dataset.records["lead"]

    normal = calculate_tc99m_transmission(dataset, material_key="lead", thickness_mm=0.87)
    low_thickness = archer_required_thickness(lead, 0.01)
    low = calculate_tc99m_transmission(dataset, material_key="lead", thickness_mm=low_thickness)

    assert normal.transmission == pytest.approx(0.1, rel=0.02)
    assert normal.room_scatter_caution is False
    assert normal.record_id == lead.record_id
    assert "J Appl Clin Med Phys" in normal.provenance
    assert low.transmission == pytest.approx(0.01, rel=0.02)
    assert low.room_scatter_caution is True


def test_spect_step3_dataset_digest_fails_closed_on_coefficient_edit(tmp_path):
    path = _mutated_dataset(
        tmp_path,
        lambda payload: payload["records"][0].__setitem__("alpha_mm_inv", 2.0),
    )
    with pytest.raises(SpectPracticalTransmissionError, match="digest"):
        load_spect_tc99m_practical_dataset(path)


def test_spect_step3_rejects_production_or_wrong_model_scope(tmp_path):
    production = _mutated_dataset(
        tmp_path,
        lambda payload: payload["metadata"].__setitem__("approval_status", "production_approved"),
    )
    with pytest.raises(SpectPracticalTransmissionError, match="development_nonproduction"):
        load_spect_tc99m_practical_dataset(production)

    wrong_scope = _mutated_dataset(
        tmp_path,
        lambda payload: payload["metadata"].__setitem__("model_scope", "single_tvl"),
    )
    with pytest.raises(SpectPracticalTransmissionError, match="broad-beam Archer"):
        load_spect_tc99m_practical_dataset(wrong_scope)


def test_spect_step3_rejects_invalid_inputs_and_unsupported_material():
    dataset = load_spect_tc99m_practical_dataset(DATASET)
    lead = dataset.records["lead"]

    with pytest.raises(SpectPracticalTransmissionError, match="greater than or equal to zero"):
        archer_transmission(lead, -1.0)
    with pytest.raises(SpectPracticalTransmissionError, match="greater than 0"):
        archer_required_thickness(lead, 0.0)
    with pytest.raises(SpectPracticalTransmissionError, match="Unsupported"):
        calculate_tc99m_transmission(dataset, material_key="unobtainium", thickness_mm=1.0)


def test_spect_step3_remains_disconnected_from_ui_reports_serialization_and_spect_plugin():
    forbidden = (
        "spect_tc99m_practical_transmission_development",
        "load_spect_tc99m_practical_dataset",
        "calculate_tc99m_required_thickness",
        "calculate_tc99m_transmission",
    )
    paths = [Path("app.py"), Path("engine/shielding_engine.py"), Path("modalities/spect.py")]
    for directory in ("reports", "tabs", "ui", "serialization", "services"):
        paths.extend(Path(directory).glob("*.py"))
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into production/application path {path}"
