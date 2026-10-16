"""Frozen PET calculation-input provenance compatibility boundary.

This module binds the exact production-approved PET radionuclide and attenuation
datasets to the physics and isotropic solver contract versions used by the
single-source PET calculation model.  Loading is fail-closed: all four
components must match the frozen manifest before PET preview calculations may
proceed.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from engine.pet_radionuclide_data import LoadedPetRadionuclideDataset


PET_CALCULATION_INPUT_PROVENANCE_SCHEMA_VERSION = 1
PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID = "pet-calculation-input-provenance"
PET_CALCULATION_INPUT_PROVENANCE_REVISION = "2026-08-17-v2"


class PetCalculationInputProvenanceError(ValueError):
    """Raised when the frozen PET calculation-input provenance boundary fails."""


@dataclass(frozen=True)
class FrozenDatasetIdentity:
    dataset_id: str
    revision: str
    records_sha256: str


@dataclass(frozen=True)
class PetCalculationInputProvenanceManifest:
    schema_version: int
    manifest_id: str
    revision: str
    radionuclide_dataset: FrozenDatasetIdentity
    attenuation_dataset: FrozenDatasetIdentity
    physics_contract_version: int
    solver_contract_version: int
    source_path: Path


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PetCalculationInputProvenanceError(f"{field} must not be blank.")
    return text


def _positive_int(value: object, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PetCalculationInputProvenanceError(f"{field} must be an integer.") from exc
    if number <= 0:
        raise PetCalculationInputProvenanceError(f"{field} must be greater than zero.")
    return number


def _dataset_identity(raw: object, field: str) -> FrozenDatasetIdentity:
    if not isinstance(raw, dict):
        raise PetCalculationInputProvenanceError(f"{field} must be an object.")
    digest = _text(raw.get("records_sha256"), f"{field}.records_sha256")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise PetCalculationInputProvenanceError(
            f"{field}.records_sha256 must be a lowercase SHA-256 hex digest."
        )
    return FrozenDatasetIdentity(
        dataset_id=_text(raw.get("dataset_id"), f"{field}.dataset_id"),
        revision=_text(raw.get("revision"), f"{field}.revision"),
        records_sha256=digest,
    )


def load_pet_calculation_input_provenance_manifest(
    path: str | Path,
) -> PetCalculationInputProvenanceManifest:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetCalculationInputProvenanceError(
            f"Unable to load PET calculation-input provenance manifest {source}."
        ) from exc
    if not isinstance(payload, dict):
        raise PetCalculationInputProvenanceError("PET provenance manifest root must be an object.")

    schema_version = _positive_int(payload.get("schema_version"), "schema_version")
    if schema_version != PET_CALCULATION_INPUT_PROVENANCE_SCHEMA_VERSION:
        raise PetCalculationInputProvenanceError(
            f"Unsupported PET provenance manifest schema version {schema_version!r}."
        )
    manifest_id = _text(payload.get("manifest_id"), "manifest_id")
    if manifest_id != PET_CALCULATION_INPUT_PROVENANCE_MANIFEST_ID:
        raise PetCalculationInputProvenanceError(
            "PET provenance manifest ID does not match the frozen production manifest."
        )
    revision = _text(payload.get("revision"), "revision")
    if revision != PET_CALCULATION_INPUT_PROVENANCE_REVISION:
        raise PetCalculationInputProvenanceError(
            "PET provenance manifest revision does not match the frozen production revision."
        )

    return PetCalculationInputProvenanceManifest(
        schema_version=schema_version,
        manifest_id=manifest_id,
        revision=revision,
        radionuclide_dataset=_dataset_identity(
            payload.get("radionuclide_dataset"), "radionuclide_dataset"
        ),
        attenuation_dataset=_dataset_identity(
            payload.get("attenuation_dataset"), "attenuation_dataset"
        ),
        physics_contract_version=_positive_int(
            payload.get("physics_contract_version"), "physics_contract_version"
        ),
        solver_contract_version=_positive_int(
            payload.get("solver_contract_version"), "solver_contract_version"
        ),
        source_path=source.resolve(),
    )


def canonical_records_sha256_from_file(path: str | Path) -> str:
    """Return the canonical SHA-256 of a dataset's ``records`` array."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetCalculationInputProvenanceError(
            f"Unable to hash PET dataset {source}."
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise PetCalculationInputProvenanceError(
            f"PET dataset {source} must contain a records array."
        )
    canonical = json.dumps(
        payload["records"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_pet_calculation_input_provenance(
    manifest: PetCalculationInputProvenanceManifest,
    *,
    radionuclide_dataset: LoadedPetRadionuclideDataset,
    attenuation_dataset: Any,
    attenuation_dataset_path: str | Path,
    physics_contract_version: int,
    solver_contract_version: int,
) -> None:
    """Fail closed unless all frozen PET calculation inputs match the manifest."""

    rad = manifest.radionuclide_dataset
    rad_meta = radionuclide_dataset.metadata
    if (
        rad_meta.dataset_id != rad.dataset_id
        or rad_meta.revision != rad.revision
        or rad_meta.records_sha256 != rad.records_sha256
    ):
        raise PetCalculationInputProvenanceError(
            "PET radionuclide dataset does not match the frozen provenance manifest."
        )

    att = manifest.attenuation_dataset
    att_meta = attenuation_dataset.metadata
    att_digest = canonical_records_sha256_from_file(attenuation_dataset_path)
    if (
        att_meta.dataset_id != att.dataset_id
        or att_meta.revision != att.revision
        or att_digest != att.records_sha256
    ):
        raise PetCalculationInputProvenanceError(
            "PET attenuation dataset does not match the frozen provenance manifest."
        )

    if int(physics_contract_version) != manifest.physics_contract_version:
        raise PetCalculationInputProvenanceError(
            "PET physics contract version does not match the frozen provenance manifest."
        )
    if int(solver_contract_version) != manifest.solver_contract_version:
        raise PetCalculationInputProvenanceError(
            "PET solver contract version does not match the frozen provenance manifest."
        )
