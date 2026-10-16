"""Tc-99m SPECT attenuation reference-data boundary.

SPECT Step 2 is deliberately headless and non-production.  The dataset loaded
here contains narrow-beam monoenergetic attenuation reference data for the
140.511 keV Tc-99m photon.  It is suitable for provenance/contract validation
only; it is not a practical broad-beam shielding model and is intentionally
not connected to the SPECT solver, desktop UI, project serialization, or
reports.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isclose, isfinite, log
from pathlib import Path
from typing import Mapping


SPECT_ATTENUATION_DATASET_STATUS = "development_nonproduction"
SPECT_ATTENUATION_DATASET_SCOPE = "narrow_beam_exponential_reference_only"
SPECT_TC99M_RADIONUCLIDE = "Tc99m"
SPECT_TC99M_RADIATION_TYPE = "tc99m_140kev"
SPECT_TC99M_TVL_KEY = "tc99m_140kev"
SPECT_TC99M_REFERENCE_ENERGY_KEV = 140.511
SPECT_ATTENUATION_CONTRACT_VERSION = 1


class SpectAttenuationDataError(ValueError):
    """Raised when the Tc-99m attenuation reference dataset is invalid."""


@dataclass(frozen=True)
class SpectAttenuationProvenance:
    source_title: str
    source_organisation: str
    publication_year: int
    reference_id: str
    table_or_section: str
    source_values: str
    derivation: str
    notes: str


@dataclass(frozen=True)
class SpectTc99mAttenuationRecord:
    record_id: str
    material_key: str
    density_g_cm3: float
    nominal_energy_kev: float
    mass_attenuation_coefficient_cm2_g: float
    linear_attenuation_coefficient_cm_inv: float
    hvl_mm: float
    tvl_mm: float
    radionuclide: str
    radiation_type: str
    tvl_key: str
    attenuation_geometry: str
    provenance: SpectAttenuationProvenance


@dataclass(frozen=True)
class SpectAttenuationDatasetMetadata:
    dataset_id: str
    revision: str
    description: str
    approval_status: str
    model_scope: str
    records_sha256: str
    contract_version: int


@dataclass(frozen=True)
class LoadedSpectAttenuationDataset:
    metadata: SpectAttenuationDatasetMetadata
    records: Mapping[str, SpectTc99mAttenuationRecord]
    source_path: Path


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SpectAttenuationDataError(f"{field} must not be blank.")
    return text


def _positive(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectAttenuationDataError(f"{field} must be numeric.") from exc
    if not isfinite(number) or number <= 0.0:
        raise SpectAttenuationDataError(f"{field} must be finite and greater than zero.")
    return number


def _records_sha256(payload: dict) -> str:
    canonical = json.dumps(
        payload.get("records"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _provenance(raw: object, field: str) -> SpectAttenuationProvenance:
    if not isinstance(raw, dict):
        raise SpectAttenuationDataError(f"{field} must be an object.")
    try:
        year = int(raw.get("publication_year"))
    except (TypeError, ValueError) as exc:
        raise SpectAttenuationDataError(f"{field}.publication_year must be an integer.") from exc
    if not 1900 <= year <= 2100:
        raise SpectAttenuationDataError(f"{field}.publication_year is outside the accepted range.")
    return SpectAttenuationProvenance(
        source_title=_text(raw.get("source_title"), f"{field}.source_title"),
        source_organisation=_text(raw.get("source_organisation"), f"{field}.source_organisation"),
        publication_year=year,
        reference_id=_text(raw.get("reference_id"), f"{field}.reference_id"),
        table_or_section=_text(raw.get("table_or_section"), f"{field}.table_or_section"),
        source_values=_text(raw.get("source_values"), f"{field}.source_values"),
        derivation=_text(raw.get("derivation"), f"{field}.derivation"),
        notes=_text(raw.get("notes"), f"{field}.notes"),
    )


def load_spect_tc99m_attenuation_dataset(path: str | Path) -> LoadedSpectAttenuationDataset:
    """Load the frozen Step 2 Tc-99m narrow-beam reference dataset.

    The function intentionally has no ``allow_production`` switch.  Step 2 data
    must remain development/non-production even if internally valid.
    """

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectAttenuationDataError(f"Unable to load SPECT attenuation dataset {source}.") from exc
    if not isinstance(payload, dict):
        raise SpectAttenuationDataError("SPECT attenuation dataset root must be an object.")
    metadata_raw = payload.get("metadata")
    records_raw = payload.get("records")
    if not isinstance(metadata_raw, dict) or not isinstance(records_raw, list):
        raise SpectAttenuationDataError("SPECT attenuation dataset requires metadata and records.")

    status = _text(metadata_raw.get("approval_status"), "metadata.approval_status")
    if status != SPECT_ATTENUATION_DATASET_STATUS:
        raise SpectAttenuationDataError(
            "SPECT Step 2 attenuation dataset must remain development_nonproduction."
        )
    scope = _text(metadata_raw.get("model_scope"), "metadata.model_scope")
    if scope != SPECT_ATTENUATION_DATASET_SCOPE:
        raise SpectAttenuationDataError(
            "SPECT Step 2 attenuation dataset must remain narrow-beam reference-only."
        )
    try:
        contract_version = int(metadata_raw.get("contract_version"))
    except (TypeError, ValueError) as exc:
        raise SpectAttenuationDataError("metadata.contract_version must be an integer.") from exc
    if contract_version != SPECT_ATTENUATION_CONTRACT_VERSION:
        raise SpectAttenuationDataError(
            f"Unsupported SPECT attenuation contract version {contract_version!r}."
        )

    digest = _records_sha256(payload)
    expected_digest = _text(metadata_raw.get("records_sha256"), "metadata.records_sha256")
    if digest != expected_digest:
        raise SpectAttenuationDataError("SPECT attenuation record digest does not match metadata.")

    records: dict[str, SpectTc99mAttenuationRecord] = {}
    record_ids: set[str] = set()
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise SpectAttenuationDataError(f"records[{index}] must be an object.")
        field = f"records[{index}]"
        record_id = _text(raw.get("record_id"), f"{field}.record_id")
        material_key = _text(raw.get("material_key"), f"{field}.material_key")
        if material_key in records:
            raise SpectAttenuationDataError(f"Duplicate SPECT attenuation material {material_key!r}.")
        if record_id in record_ids:
            raise SpectAttenuationDataError(f"Duplicate SPECT attenuation record_id {record_id!r}.")

        density = _positive(raw.get("density_g_cm3"), f"{field}.density_g_cm3")
        energy = _positive(raw.get("nominal_energy_kev"), f"{field}.nominal_energy_kev")
        mass_mu = _positive(
            raw.get("mass_attenuation_coefficient_cm2_g"),
            f"{field}.mass_attenuation_coefficient_cm2_g",
        )
        linear_mu = _positive(
            raw.get("linear_attenuation_coefficient_cm_inv"),
            f"{field}.linear_attenuation_coefficient_cm_inv",
        )
        hvl_mm = _positive(raw.get("hvl_mm"), f"{field}.hvl_mm")
        tvl_mm = _positive(raw.get("tvl_mm"), f"{field}.tvl_mm")

        if not isclose(energy, SPECT_TC99M_REFERENCE_ENERGY_KEV, rel_tol=0.0, abs_tol=0.001):
            raise SpectAttenuationDataError(
                f"{record_id} is not at the Tc-99m reference photon energy."
            )
        if _text(raw.get("radionuclide"), f"{field}.radionuclide") != SPECT_TC99M_RADIONUCLIDE:
            raise SpectAttenuationDataError(f"{record_id} is not explicitly Tc99m-only.")
        if _text(raw.get("radiation_type"), f"{field}.radiation_type") != SPECT_TC99M_RADIATION_TYPE:
            raise SpectAttenuationDataError(f"{record_id} has the wrong radiation_type.")
        if _text(raw.get("tvl_key"), f"{field}.tvl_key") != SPECT_TC99M_TVL_KEY:
            raise SpectAttenuationDataError(f"{record_id} has the wrong tvl_key.")
        if _text(raw.get("attenuation_geometry"), f"{field}.attenuation_geometry") != "narrow_beam":
            raise SpectAttenuationDataError(f"{record_id} must be explicitly narrow_beam.")

        calculated_linear_mu = mass_mu * density
        calculated_hvl_mm = log(2.0) / calculated_linear_mu * 10.0
        calculated_tvl_mm = log(10.0) / calculated_linear_mu * 10.0
        if not isclose(linear_mu, calculated_linear_mu, rel_tol=2e-6):
            raise SpectAttenuationDataError(f"{record_id} linear attenuation derivation is inconsistent.")
        if not isclose(hvl_mm, calculated_hvl_mm, rel_tol=2e-6):
            raise SpectAttenuationDataError(f"{record_id} HVL derivation is inconsistent.")
        if not isclose(tvl_mm, calculated_tvl_mm, rel_tol=2e-6):
            raise SpectAttenuationDataError(f"{record_id} TVL derivation is inconsistent.")

        records[material_key] = SpectTc99mAttenuationRecord(
            record_id=record_id,
            material_key=material_key,
            density_g_cm3=density,
            nominal_energy_kev=energy,
            mass_attenuation_coefficient_cm2_g=mass_mu,
            linear_attenuation_coefficient_cm_inv=linear_mu,
            hvl_mm=hvl_mm,
            tvl_mm=tvl_mm,
            radionuclide=SPECT_TC99M_RADIONUCLIDE,
            radiation_type=SPECT_TC99M_RADIATION_TYPE,
            tvl_key=SPECT_TC99M_TVL_KEY,
            attenuation_geometry="narrow_beam",
            provenance=_provenance(raw.get("provenance"), f"{field}.provenance"),
        )
        record_ids.add(record_id)

    if not records:
        raise SpectAttenuationDataError("SPECT attenuation dataset must contain at least one record.")

    metadata = SpectAttenuationDatasetMetadata(
        dataset_id=_text(metadata_raw.get("dataset_id"), "metadata.dataset_id"),
        revision=_text(metadata_raw.get("revision"), "metadata.revision"),
        description=_text(metadata_raw.get("description"), "metadata.description"),
        approval_status=status,
        model_scope=scope,
        records_sha256=digest,
        contract_version=contract_version,
    )
    return LoadedSpectAttenuationDataset(metadata=metadata, records=records, source_path=source.resolve())
