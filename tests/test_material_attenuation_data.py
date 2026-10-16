from __future__ import annotations

from pathlib import Path

import pytest

from engine.barrier_input_contract import BarrierSourceInput
from engine.isotropic_barrier_solver import (
    ISOTROPIC_NON_BEAM_SOLVER_MODE,
    IsotropicBarrierDesign,
    IsotropicBarrierGeometry,
    IsotropicBarrierSolverInput,
    solve_isotropic_non_beam_barrier,
)
from engine.material_attenuation_data import (
    AttenuationProvenance,
    MaterialAttenuationDataError,
    MaterialAttenuationLibrary,
    MaterialAttenuationRecord,
    attenuation_record_to_solver_input,
)


def _provenance(**overrides):
    values = dict(
        source_title="Example reviewed shielding data",
        source_organisation="Example standards body",
        publication_year=2025,
        table_or_section="Table 4",
        reference_id="EXAMPLE-2025-04",
        edition="1st ed.",
    )
    values.update(overrides)
    return AttenuationProvenance(**values)


def _record(**overrides):
    values = dict(
        record_id="f18-511-concrete-example",
        tvl_key="f18_511kev",
        radiation_type="f18_511kev",
        material_key="concrete",
        tvl1_mm=176.0,
        tvle_mm=154.0,
        radionuclides=("F18",),
        nominal_energy_kev=511.0,
        provenance=_provenance(),
    )
    values.update(overrides)
    return MaterialAttenuationRecord(**values)


def test_library_resolves_pet_record_by_tvl_key_and_material_with_provenance():
    library = MaterialAttenuationLibrary([_record()], library_id="test-library", revision="1")

    record = library.lookup(
        tvl_key="f18_511kev",
        material_key="concrete",
        radiation_type="f18_511kev",
    )

    assert record.radionuclides == ("F18",)
    assert record.nominal_energy_kev == 511.0
    assert record.provenance.reference_id == "EXAMPLE-2025-04"
    assert "Example standards body" in record.provenance.summary


def test_same_contract_supports_future_spect_energy_key_without_pet_dependency():
    tc99m = _record(
        record_id="tc99m-140-lead-example",
        tvl_key="tc99m_140kev",
        radiation_type="tc99m_140kev",
        material_key="lead",
        tvl1_mm=1.0,
        tvle_mm=1.0,
        radionuclides=("Tc99m",),
        nominal_energy_kev=140.5,
    )
    library = MaterialAttenuationLibrary([tc99m], library_id="test-library", revision="1")

    assert library.lookup(tvl_key="tc99m_140kev", material_key="lead") is tc99m


def test_record_adapter_carries_tvl_values_and_provenance_into_solver_result():
    record = _record()
    attenuation = attenuation_record_to_solver_input(record)
    source = BarrierSourceInput(
        source_name="PET patient",
        source_type="pet_patient",
        radiation_type="f18_511kev",
        tvl_key="f18_511kev",
        weekly_dose_uSv_at_1m=1000.0,
        contribution_group="pet_patient",
        solver_mode=ISOTROPIC_NON_BEAM_SOLVER_MODE,
    )
    result = solve_isotropic_non_beam_barrier(
        IsotropicBarrierSolverInput(
            source=source,
            geometry=IsotropicBarrierGeometry(2.0),
            design=IsotropicBarrierDesign(10.0, 1.0),
            attenuation=attenuation,
        )
    )

    assert result.attenuation_record_id == record.record_id
    assert result.attenuation_provenance == record.provenance.summary
    assert result.material_key == "concrete"


def test_library_rejects_duplicate_keys_and_duplicate_record_ids():
    with pytest.raises(MaterialAttenuationDataError, match="Duplicate attenuation lookup key"):
        MaterialAttenuationLibrary(
            [_record(), _record(record_id="another-id")], library_id="x", revision="1"
        )

    with pytest.raises(MaterialAttenuationDataError, match="Duplicate attenuation record_id"):
        MaterialAttenuationLibrary(
            [_record(), _record(tvl_key="ga68_511kev")], library_id="x", revision="1"
        )


def test_lookup_rejects_missing_or_radiation_mismatched_records():
    library = MaterialAttenuationLibrary([_record()], library_id="x", revision="1")
    with pytest.raises(MaterialAttenuationDataError, match="No attenuation record"):
        library.lookup(tvl_key="tc99m_140kev", material_key="lead")
    with pytest.raises(MaterialAttenuationDataError, match="radiation_type does not match"):
        library.lookup(
            tvl_key="f18_511kev", material_key="concrete", radiation_type="ga68_511kev"
        )


def test_record_and_provenance_validation_reject_incomplete_or_invalid_data():
    with pytest.raises(MaterialAttenuationDataError, match="source_title must not be blank"):
        _provenance(source_title="")
    with pytest.raises(MaterialAttenuationDataError, match="publication_year"):
        _provenance(publication_year=1800)
    with pytest.raises(MaterialAttenuationDataError, match="tvl1_mm"):
        _record(tvl1_mm=0.0)
    with pytest.raises(MaterialAttenuationDataError, match="radionuclides must not contain duplicates"):
        _record(radionuclides=("F18", "F18"))


def test_no_unreviewed_pet_or_spect_tvl_values_are_embedded_in_boundary_module():
    text = Path("engine/material_attenuation_data.py").read_text(encoding="utf-8")
    assert "176.0" not in text
    assert "154.0" not in text
    assert "tc99m_140kev" not in text
    assert "f18_511kev" not in text


def test_material_boundary_remains_disconnected_from_ui_reports_and_production_dispatch():
    forbidden = "material_attenuation_data"
    assert forbidden not in Path("app.py").read_text(encoding="utf-8")
    assert forbidden not in Path("engine/shielding_engine.py").read_text(encoding="utf-8")
    assert forbidden not in Path("modalities/ct.py").read_text(encoding="utf-8")
    assert forbidden not in Path("modalities/xray.py").read_text(encoding="utf-8")
    assert forbidden not in "\n".join(
        path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")
    )


def _pet_fixture_path() -> Path:
    return Path("tests/fixtures/pet_511kev_attenuation_reviewed_pending_approval.json")


def test_pet_511kev_fixture_is_fail_closed_until_explicitly_approved():
    from engine.material_attenuation_data import load_material_attenuation_dataset

    with pytest.raises(MaterialAttenuationDataError, match="not approved for production"):
        load_material_attenuation_dataset(_pet_fixture_path())


def test_pet_511kev_fixture_loads_only_with_explicit_nonproduction_override():
    from engine.material_attenuation_data import (
        APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL,
        load_material_attenuation_dataset,
    )

    dataset = load_material_attenuation_dataset(
        _pet_fixture_path(), allow_unapproved=True
    )

    assert dataset.metadata.approval_status == APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL
    assert dataset.metadata.production_approved is False
    assert dataset.library.library_id == "pet-511kev-aapm-tg108-review-fixture"
    assert len(dataset.library.records) == 3
    assert dataset.source_path == _pet_fixture_path().resolve()


def test_pet_511kev_fixture_has_material_specific_records_and_full_provenance():
    from engine.material_attenuation_data import load_material_attenuation_dataset

    dataset = load_material_attenuation_dataset(
        _pet_fixture_path(), allow_unapproved=True
    )
    lead = dataset.library.lookup(
        tvl_key="pet_511kev",
        material_key="lead",
        radiation_type="annihilation_511kev",
    )
    concrete = dataset.library.lookup(
        tvl_key="pet_511kev",
        material_key="concrete_2350kg_m3",
    )
    iron = dataset.library.lookup(tvl_key="pet_511kev", material_key="iron")

    assert lead.nominal_energy_kev == 511.0
    assert lead.radionuclides == ("F18", "Ga68", "Cu64")
    assert lead.provenance.source_organisation == "American Association of Physicists in Medicine"
    assert "Table IV" in lead.provenance.table_or_section
    assert "10.1118/1.2135911" in lead.provenance.reference_id
    assert lead.provenance.notes
    assert concrete.material_key == "concrete_2350kg_m3"
    assert concrete.provenance.notes
    assert iron.provenance.notes


def test_loaded_pet_fixture_resolves_into_existing_isotropic_solver_input():
    from engine.material_attenuation_data import load_material_attenuation_dataset

    dataset = load_material_attenuation_dataset(
        _pet_fixture_path(), allow_unapproved=True
    )
    record = dataset.library.lookup(tvl_key="pet_511kev", material_key="lead")
    solver_input = attenuation_record_to_solver_input(record)

    assert solver_input.tvl_key == "pet_511kev"
    assert solver_input.material_key == "lead"
    assert solver_input.attenuation_record_id == record.record_id
    assert "AAPM" in solver_input.attenuation_provenance


def test_loader_rejects_invalid_json_empty_records_and_false_approval(tmp_path):
    from engine.material_attenuation_data import load_material_attenuation_dataset
    import json

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(MaterialAttenuationDataError, match="not valid JSON"):
        load_material_attenuation_dataset(invalid, allow_unapproved=True)

    payload = json.loads(_pet_fixture_path().read_text(encoding="utf-8"))
    payload["records"] = []
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MaterialAttenuationDataError, match="at least one record"):
        load_material_attenuation_dataset(empty, allow_unapproved=True)

    payload = json.loads(_pet_fixture_path().read_text(encoding="utf-8"))
    payload["metadata"]["approval_status"] = "production_approved"
    falsely_approved = tmp_path / "false-approval.json"
    falsely_approved.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MaterialAttenuationDataError, match="approved_by and approved_date"):
        load_material_attenuation_dataset(falsely_approved)


def test_pet_fixture_and_loader_remain_disconnected_from_ui_reports_and_production_dispatch():
    fixture_name = "pet_511kev_attenuation_reviewed_pending_approval"
    loader_name = "load_material_attenuation_dataset"
    production_texts = [
        Path("app.py").read_text(encoding="utf-8"),
        Path("engine/shielding_engine.py").read_text(encoding="utf-8"),
        Path("modalities/spect.py").read_text(encoding="utf-8"),
        "\n".join(path.read_text(encoding="utf-8") for path in Path("reports").glob("*.py")),
    ]
    assert all(fixture_name not in text for text in production_texts)
    assert all(loader_name not in text for text in production_texts)
