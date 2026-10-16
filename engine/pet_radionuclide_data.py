"""Versioned PET radionuclide physics dataset and provenance loader.

The dataset is pre-production and deliberately requires explicit user approval
before any future production integration.  Preview calculations may load the
reviewed dataset while exposing its pending approval state.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Mapping

PENDING = "reviewed_pending_user_approval"
APPROVED = "production_approved"

PRODUCTION_DATASET_ID = "pet-radionuclide-physics-source-model"
PRODUCTION_DATASET_REVISION = "2026-07-21-review-1"
PRODUCTION_RECORDS_SHA256 = "1d7e62d9938aa68868f384f36e1923edb67aa4a2d4943293f862e473103b8971"

class PetRadionuclideDataError(ValueError):
    pass

@dataclass(frozen=True)
class PetRadionuclideProvenance:
    source_title: str
    source_organisation: str
    source_value: str
    reference_id: str
    accessed_date: str
    derivation: str

@dataclass(frozen=True)
class PetRadionuclideRecord:
    code: str
    display_name: str
    half_life_h: float
    dose_rate_constant_uSv_h_per_MBq_at_1m: float
    radiation_type: str
    tvl_key: str
    half_life_provenance: PetRadionuclideProvenance
    dose_rate_provenance: PetRadionuclideProvenance

@dataclass(frozen=True)
class PetRadionuclideDatasetMetadata:
    dataset_id: str
    revision: str
    description: str
    approval_status: str
    reviewed_by: str
    reviewed_date: str
    approved_by: str | None
    approved_date: str | None
    records_sha256: str

@dataclass(frozen=True)
class LoadedPetRadionuclideDataset:
    metadata: PetRadionuclideDatasetMetadata
    records: Mapping[str, PetRadionuclideRecord]
    source_path: Path


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PetRadionuclideDataError(f"{field} must not be blank.")
    return text


def _prov(raw: object, field: str) -> PetRadionuclideProvenance:
    if not isinstance(raw, dict):
        raise PetRadionuclideDataError(f"{field} must be an object.")
    return PetRadionuclideProvenance(
        source_title=_text(raw.get("source_title"), f"{field}.source_title"),
        source_organisation=_text(raw.get("source_organisation"), f"{field}.source_organisation"),
        source_value=_text(raw.get("source_value"), f"{field}.source_value"),
        reference_id=_text(raw.get("reference_id"), f"{field}.reference_id"),
        accessed_date=_text(raw.get("accessed_date"), f"{field}.accessed_date"),
        derivation=_text(raw.get("derivation"), f"{field}.derivation"),
    )


def records_sha256(payload: dict) -> str:
    canonical = json.dumps(payload.get("records"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def load_pet_radionuclide_dataset(path: str | Path, *, allow_unapproved: bool = False) -> LoadedPetRadionuclideDataset:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PetRadionuclideDataError(f"Unable to load PET radionuclide dataset {source}.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict) or not isinstance(payload.get("records"), list):
        raise PetRadionuclideDataError("PET radionuclide dataset requires metadata and records.")
    meta = payload["metadata"]
    status = _text(meta.get("approval_status"), "metadata.approval_status")
    if status not in (PENDING, APPROVED):
        raise PetRadionuclideDataError(f"Unsupported approval status {status!r}.")
    if status != APPROVED and not allow_unapproved:
        raise PetRadionuclideDataError("PET radionuclide dataset is not production approved.")
    digest = records_sha256(payload)
    approved_digest = meta.get("approved_records_sha256")
    if status == APPROVED and approved_digest != digest:
        raise PetRadionuclideDataError("Approved PET radionuclide record digest does not match metadata.")
    records = {}
    for index, raw in enumerate(payload["records"]):
        if not isinstance(raw, dict):
            raise PetRadionuclideDataError(f"records[{index}] must be an object.")
        code = _text(raw.get("code"), f"records[{index}].code")
        if code in records:
            raise PetRadionuclideDataError(f"Duplicate PET radionuclide code {code!r}.")
        half_life = float(raw.get("half_life_h"))
        constant = float(raw.get("dose_rate_constant_uSv_h_per_MBq_at_1m"))
        if not isfinite(half_life) or half_life <= 0 or not isfinite(constant) or constant <= 0:
            raise PetRadionuclideDataError(f"Invalid positive physics value for {code}.")
        records[code] = PetRadionuclideRecord(
            code=code,
            display_name=_text(raw.get("display_name"), f"records[{index}].display_name"),
            half_life_h=half_life,
            dose_rate_constant_uSv_h_per_MBq_at_1m=constant,
            radiation_type=_text(raw.get("radiation_type"), f"records[{index}].radiation_type"),
            tvl_key=_text(raw.get("tvl_key"), f"records[{index}].tvl_key"),
            half_life_provenance=_prov(raw.get("half_life_provenance"), f"records[{index}].half_life_provenance"),
            dose_rate_provenance=_prov(raw.get("dose_rate_provenance"), f"records[{index}].dose_rate_provenance"),
        )
    metadata = PetRadionuclideDatasetMetadata(
        dataset_id=_text(meta.get("dataset_id"), "metadata.dataset_id"),
        revision=_text(meta.get("revision"), "metadata.revision"),
        description=_text(meta.get("description"), "metadata.description"),
        approval_status=status,
        reviewed_by=_text(meta.get("reviewed_by"), "metadata.reviewed_by"),
        reviewed_date=_text(meta.get("reviewed_date"), "metadata.reviewed_date"),
        approved_by=str(meta.get("approved_by") or "").strip() or None,
        approved_date=str(meta.get("approved_date") or "").strip() or None,
        records_sha256=digest,
    )
    return LoadedPetRadionuclideDataset(metadata, records, source.resolve())


def load_production_pet_radionuclide_dataset(
    path: str | Path,
) -> LoadedPetRadionuclideDataset:
    """Load only the exact radionuclide dataset approved for production use.

    Production eligibility is deliberately pinned to dataset identity, revision,
    approval state, and the immutable records digest.  A separately approved
    dataset or a re-hashed edited copy therefore cannot become production
    eligible merely by being internally self-consistent.
    """

    dataset = load_pet_radionuclide_dataset(path)
    metadata = dataset.metadata
    if metadata.dataset_id != PRODUCTION_DATASET_ID:
        raise PetRadionuclideDataError(
            "PET radionuclide dataset ID is not the production-approved dataset."
        )
    if metadata.revision != PRODUCTION_DATASET_REVISION:
        raise PetRadionuclideDataError(
            "PET radionuclide dataset revision is not the production-approved revision."
        )
    if metadata.records_sha256 != PRODUCTION_RECORDS_SHA256:
        raise PetRadionuclideDataError(
            "PET radionuclide dataset records do not match the production-approved digest."
        )
    return dataset
