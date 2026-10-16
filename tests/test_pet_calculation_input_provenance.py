from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from engine.isotropic_barrier_solver import ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION
from engine.material_attenuation_data import load_material_attenuation_dataset
from engine.pet_calculation_input_provenance import (
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID,
    PET_CALCULATION_INPUT_PROVENANCE_REVISION,
    PetCalculationInputProvenanceError,
    load_pet_calculation_input_provenance_manifest,
    validate_pet_calculation_input_provenance,
)
from engine.pet_radionuclide_data import load_production_pet_radionuclide_dataset
from modalities.pet import (
    PET_ATTENUATION_DATASET_PATH,
    PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH,
    PET_PHYSICS_CONTRACT_VERSION,
    PET_RADIONUCLIDE_DATASET_PATH,
)


def _loaded_inputs():
    manifest = load_pet_calculation_input_provenance_manifest(
        PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH
    )
    radionuclides = load_production_pet_radionuclide_dataset(PET_RADIONUCLIDE_DATASET_PATH)
    attenuation = load_material_attenuation_dataset(PET_ATTENUATION_DATASET_PATH)
    return manifest, radionuclides, attenuation


def test_frozen_pet_calculation_input_manifest_accepts_exact_runtime_inputs():
    manifest, radionuclides, attenuation = _loaded_inputs()

    validate_pet_calculation_input_provenance(
        manifest,
        radionuclide_dataset=radionuclides,
        attenuation_dataset=attenuation,
        attenuation_dataset_path=PET_ATTENUATION_DATASET_PATH,
        physics_contract_version=PET_PHYSICS_CONTRACT_VERSION,
        solver_contract_version=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
    )

    assert manifest.manifest_id == PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID
    assert manifest.revision == PET_CALCULATION_INPUT_PROVENANCE_REVISION


@pytest.mark.parametrize(
    ("physics_version", "solver_version", "message"),
    [
        (PET_PHYSICS_CONTRACT_VERSION + 1, ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION, "physics"),
        (PET_PHYSICS_CONTRACT_VERSION, ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION + 1, "solver"),
    ],
)
def test_frozen_pet_manifest_rejects_contract_version_drift(
    physics_version, solver_version, message
):
    manifest, radionuclides, attenuation = _loaded_inputs()

    with pytest.raises(PetCalculationInputProvenanceError, match=message):
        validate_pet_calculation_input_provenance(
            manifest,
            radionuclide_dataset=radionuclides,
            attenuation_dataset=attenuation,
            attenuation_dataset_path=PET_ATTENUATION_DATASET_PATH,
            physics_contract_version=physics_version,
            solver_contract_version=solver_version,
        )


def test_frozen_pet_manifest_rejects_radionuclide_digest_drift():
    manifest, radionuclides, attenuation = _loaded_inputs()
    altered_meta = replace(radionuclides.metadata, records_sha256="0" * 64)
    altered_radionuclides = replace(radionuclides, metadata=altered_meta)

    with pytest.raises(PetCalculationInputProvenanceError, match="radionuclide"):
        validate_pet_calculation_input_provenance(
            manifest,
            radionuclide_dataset=altered_radionuclides,
            attenuation_dataset=attenuation,
            attenuation_dataset_path=PET_ATTENUATION_DATASET_PATH,
            physics_contract_version=PET_PHYSICS_CONTRACT_VERSION,
            solver_contract_version=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
        )


def test_frozen_pet_manifest_rejects_rehashed_attenuation_record_drift(tmp_path):
    manifest, radionuclides, attenuation = _loaded_inputs()
    payload = json.loads(Path(PET_ATTENUATION_DATASET_PATH).read_text(encoding="utf-8"))
    payload["records"][0]["tvl1_mm"] = float(payload["records"][0]["tvl1_mm"]) + 0.001
    altered_path = tmp_path / "altered_approved_attenuation.json"
    altered_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # The generic loader accepts the approved metadata; the provenance boundary
    # must independently pin the actual records digest.
    altered_attenuation = load_material_attenuation_dataset(altered_path)
    with pytest.raises(PetCalculationInputProvenanceError, match="attenuation"):
        validate_pet_calculation_input_provenance(
            manifest,
            radionuclide_dataset=radionuclides,
            attenuation_dataset=altered_attenuation,
            attenuation_dataset_path=altered_path,
            physics_contract_version=PET_PHYSICS_CONTRACT_VERSION,
            solver_contract_version=ISOTROPIC_BARRIER_SOLVER_CONTRACT_VERSION,
        )


def test_frozen_pet_manifest_rejects_manifest_revision_drift(tmp_path):
    payload = json.loads(
        Path(PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_PATH).read_text(encoding="utf-8")
    )
    payload["revision"] = "future-revision"
    path = tmp_path / "future_manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PetCalculationInputProvenanceError, match="revision"):
        load_pet_calculation_input_provenance_manifest(path)
