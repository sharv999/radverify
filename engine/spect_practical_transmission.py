"""Tc-99m practical broad-beam shielding/transmission boundary.

SPECT Step 3 remains headless and non-production.  It introduces a validated
Tc-99m Archer-equation transmission dataset and pure forward/inverse model
functions based on published broad-beam Monte Carlo fits.  Nothing in this
module is connected to the desktop UI, report generation, project
serialization, or production shielding dispatch.

The source paper also shows that room/ceiling/floor scatter becomes increasingly
important at very low barrier transmissions.  Results at or below the dataset's
configured caution threshold therefore carry an explicit scope warning instead
of silently implying that the infinite-extent barrier fit is a complete room
model.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import exp, isfinite, log
from pathlib import Path
from typing import Mapping


SPECT_PRACTICAL_DEVELOPMENT_STATUS = "development_nonproduction"
SPECT_PRACTICAL_FROZEN_STATUS = "physics_approved_frozen_nonproduction"
SPECT_PRACTICAL_DATASET_STATUS = SPECT_PRACTICAL_DEVELOPMENT_STATUS
SPECT_FROZEN_PRACTICAL_DATASET_ID = "spect-tc99m-practical-transmission-oumano-2025-frozen"
SPECT_FROZEN_PRACTICAL_DATASET_REVISION = "2026-08-23-step20-1"
SPECT_FROZEN_PRACTICAL_RECORDS_SHA256 = "9af69cf321e62435553b89ec4803206e72f648760d73b8176903e8fb2acb38de"
SPECT_PRACTICAL_MODEL_SCOPE = "broad_beam_archer_reference_model"
SPECT_PRACTICAL_CONTRACT_VERSION = 1
SPECT_TC99M_RADIONUCLIDE = "Tc99m"
SPECT_TC99M_RADIATION_TYPE = "tc99m_140kev"
SPECT_TC99M_TVL_KEY = "tc99m_140kev"


class SpectPracticalTransmissionError(ValueError):
    """Raised when the Step 3 practical transmission contract is invalid."""


@dataclass(frozen=True)
class SpectPracticalProvenance:
    source_title: str
    source_organisation: str
    publication_year: int
    reference_id: str
    table_or_section: str
    model_notes: str

    @property
    def summary(self) -> str:
        return (
            f"{self.source_organisation}, {self.source_title} ({self.publication_year}), "
            f"{self.table_or_section}; {self.reference_id}"
        )


@dataclass(frozen=True)
class SpectTc99mArcherRecord:
    record_id: str
    material_key: str
    material_label: str
    alpha_mm_inv: float
    beta_mm_inv: float
    gamma: float
    reference_fractional_layers_mm: Mapping[str, float]
    radionuclide: str
    radiation_type: str
    tvl_key: str
    provenance: SpectPracticalProvenance


@dataclass(frozen=True)
class SpectPracticalDatasetMetadata:
    dataset_id: str
    revision: str
    description: str
    approval_status: str
    model_scope: str
    contract_version: int
    room_scatter_caution_below_transmission: float
    source_model_min_transmission: float
    records_sha256: str


@dataclass(frozen=True)
class LoadedSpectPracticalDataset:
    metadata: SpectPracticalDatasetMetadata
    records: Mapping[str, SpectTc99mArcherRecord]
    source_path: Path


@dataclass(frozen=True)
class SpectTransmissionResult:
    material_key: str
    thickness_mm: float
    transmission: float
    record_id: str
    provenance: str
    room_scatter_caution: bool
    scope_note: str


@dataclass(frozen=True)
class SpectRequiredThicknessResult:
    material_key: str
    target_transmission: float
    required_thickness_mm: float
    record_id: str
    provenance: str
    room_scatter_caution: bool
    source_model_extrapolation: bool
    scope_note: str


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SpectPracticalTransmissionError(f"{field} must not be blank.")
    return text


def _finite(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectPracticalTransmissionError(f"{field} must be numeric.") from exc
    if not isfinite(number):
        raise SpectPracticalTransmissionError(f"{field} must be finite.")
    return number


def _positive(value: object, field: str) -> float:
    number = _finite(value, field)
    if number <= 0.0:
        raise SpectPracticalTransmissionError(f"{field} must be greater than zero.")
    return number


def _unit_interval(value: object, field: str, *, include_zero: bool = False) -> float:
    number = _finite(value, field)
    lower_ok = number >= 0.0 if include_zero else number > 0.0
    if not lower_ok or number > 1.0:
        qualifier = "between 0 and 1 inclusive" if include_zero else "greater than 0 and <= 1"
        raise SpectPracticalTransmissionError(f"{field} must be {qualifier}.")
    return number


def _records_sha256(payload: dict) -> str:
    canonical = json.dumps(
        payload.get("records"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _provenance(raw: object, field: str) -> SpectPracticalProvenance:
    if not isinstance(raw, dict):
        raise SpectPracticalTransmissionError(f"{field} must be an object.")
    try:
        year = int(raw.get("publication_year"))
    except (TypeError, ValueError) as exc:
        raise SpectPracticalTransmissionError(f"{field}.publication_year must be an integer.") from exc
    if not 1900 <= year <= 2100:
        raise SpectPracticalTransmissionError(f"{field}.publication_year is outside the accepted range.")
    return SpectPracticalProvenance(
        source_title=_text(raw.get("source_title"), f"{field}.source_title"),
        source_organisation=_text(raw.get("source_organisation"), f"{field}.source_organisation"),
        publication_year=year,
        reference_id=_text(raw.get("reference_id"), f"{field}.reference_id"),
        table_or_section=_text(raw.get("table_or_section"), f"{field}.table_or_section"),
        model_notes=_text(raw.get("model_notes"), f"{field}.model_notes"),
    )


def archer_transmission(record: SpectTc99mArcherRecord, thickness_mm: float) -> float:
    """Return broad-beam transmission for a material thickness using Archer Eq. 3."""

    if not isinstance(record, SpectTc99mArcherRecord):
        raise SpectPracticalTransmissionError("record must be a SpectTc99mArcherRecord.")
    thickness = _finite(thickness_mm, "thickness_mm")
    if thickness < 0.0:
        raise SpectPracticalTransmissionError("thickness_mm must be greater than or equal to zero.")
    ratio = record.beta_mm_inv / record.alpha_mm_inv
    bracket = (1.0 + ratio) * exp(record.alpha_mm_inv * record.gamma * thickness) - ratio
    if bracket <= 0.0:
        raise SpectPracticalTransmissionError("Archer equation produced a non-positive bracket.")
    return bracket ** (-1.0 / record.gamma)


def archer_required_thickness(record: SpectTc99mArcherRecord, transmission: float) -> float:
    """Return required material thickness for target transmission using Archer Eq. 4."""

    if not isinstance(record, SpectTc99mArcherRecord):
        raise SpectPracticalTransmissionError("record must be a SpectTc99mArcherRecord.")
    target = _unit_interval(transmission, "transmission")
    if target == 1.0:
        return 0.0
    ratio = record.beta_mm_inv / record.alpha_mm_inv
    numerator = target ** (-record.gamma) + ratio
    denominator = 1.0 + ratio
    if numerator <= 0.0 or denominator <= 0.0:
        raise SpectPracticalTransmissionError("Archer inverse is undefined for this parameter set.")
    return log(numerator / denominator) / (record.alpha_mm_inv * record.gamma)


def _validate_reference_layers(record: SpectTc99mArcherRecord) -> None:
    expected = {
        "hvl": 0.5,
        "qvl": 0.25,
        "tvl": 0.1,
        "cvl": 0.01,
        "mvl": 0.001,
    }
    if set(record.reference_fractional_layers_mm) != set(expected):
        raise SpectPracticalTransmissionError(
            f"{record.record_id} must provide hvl/qvl/tvl/cvl/mvl reference values."
        )
    for key, transmission in expected.items():
        published = _positive(
            record.reference_fractional_layers_mm[key],
            f"{record.record_id}.reference_fractional_layers_mm.{key}",
        )
        calculated = archer_required_thickness(record, transmission)
        # Published Table 3 values are rounded, so validate to 1% or 0.02 mm.
        tolerance = max(abs(published) * 0.01, 0.02)
        if abs(calculated - published) > tolerance:
            raise SpectPracticalTransmissionError(
                f"{record.record_id} {key} does not reproduce the published fractional layer."
            )


def load_spect_tc99m_practical_dataset(
    path: str | Path,
    *,
    require_frozen: bool = False,
) -> LoadedSpectPracticalDataset:
    """Load and validate a Step 3/20 practical Tc-99m transmission dataset."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectPracticalTransmissionError(
            f"Unable to load SPECT practical transmission dataset {source}."
        ) from exc
    if not isinstance(payload, dict):
        raise SpectPracticalTransmissionError("SPECT practical dataset root must be an object.")
    metadata_raw = payload.get("metadata")
    records_raw = payload.get("records")
    if not isinstance(metadata_raw, dict) or not isinstance(records_raw, list):
        raise SpectPracticalTransmissionError("SPECT practical dataset requires metadata and records.")

    status = _text(metadata_raw.get("approval_status"), "metadata.approval_status")
    if status not in {
        SPECT_PRACTICAL_DEVELOPMENT_STATUS,
        SPECT_PRACTICAL_FROZEN_STATUS,
    }:
        raise SpectPracticalTransmissionError(
            "SPECT practical dataset approval_status must be development_nonproduction "
            "or physics_approved_frozen_nonproduction."
        )
    scope = _text(metadata_raw.get("model_scope"), "metadata.model_scope")
    if scope != SPECT_PRACTICAL_MODEL_SCOPE:
        raise SpectPracticalTransmissionError(
            "SPECT Step 3 practical dataset must remain broad-beam Archer reference-only."
        )
    try:
        contract_version = int(metadata_raw.get("contract_version"))
    except (TypeError, ValueError) as exc:
        raise SpectPracticalTransmissionError("metadata.contract_version must be an integer.") from exc
    if contract_version != SPECT_PRACTICAL_CONTRACT_VERSION:
        raise SpectPracticalTransmissionError(
            f"Unsupported SPECT practical contract version {contract_version!r}."
        )

    caution = _unit_interval(
        metadata_raw.get("room_scatter_caution_below_transmission"),
        "metadata.room_scatter_caution_below_transmission",
    )
    minimum = _unit_interval(
        metadata_raw.get("source_model_min_transmission"),
        "metadata.source_model_min_transmission",
    )
    if minimum >= caution:
        raise SpectPracticalTransmissionError(
            "source_model_min_transmission must be below room_scatter_caution_below_transmission."
        )

    digest = _records_sha256(payload)
    expected_digest = _text(metadata_raw.get("records_sha256"), "metadata.records_sha256")
    if digest != expected_digest:
        raise SpectPracticalTransmissionError("SPECT practical record digest does not match metadata.")

    records: dict[str, SpectTc99mArcherRecord] = {}
    ids: set[str] = set()
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise SpectPracticalTransmissionError(f"records[{index}] must be an object.")
        field = f"records[{index}]"
        record_id = _text(raw.get("record_id"), f"{field}.record_id")
        material_key = _text(raw.get("material_key"), f"{field}.material_key")
        if record_id in ids:
            raise SpectPracticalTransmissionError(f"Duplicate SPECT practical record_id {record_id!r}.")
        if material_key in records:
            raise SpectPracticalTransmissionError(f"Duplicate SPECT practical material {material_key!r}.")

        if _text(raw.get("radionuclide"), f"{field}.radionuclide") != SPECT_TC99M_RADIONUCLIDE:
            raise SpectPracticalTransmissionError(f"{record_id} is not explicitly Tc99m-only.")
        if _text(raw.get("radiation_type"), f"{field}.radiation_type") != SPECT_TC99M_RADIATION_TYPE:
            raise SpectPracticalTransmissionError(f"{record_id} has the wrong radiation_type.")
        if _text(raw.get("tvl_key"), f"{field}.tvl_key") != SPECT_TC99M_TVL_KEY:
            raise SpectPracticalTransmissionError(f"{record_id} has the wrong tvl_key.")

        layers_raw = raw.get("reference_fractional_layers_mm")
        if not isinstance(layers_raw, dict):
            raise SpectPracticalTransmissionError(
                f"{field}.reference_fractional_layers_mm must be an object."
            )
        record = SpectTc99mArcherRecord(
            record_id=record_id,
            material_key=material_key,
            material_label=_text(raw.get("material_label"), f"{field}.material_label"),
            alpha_mm_inv=_positive(raw.get("alpha_mm_inv"), f"{field}.alpha_mm_inv"),
            beta_mm_inv=_finite(raw.get("beta_mm_inv"), f"{field}.beta_mm_inv"),
            gamma=_positive(raw.get("gamma"), f"{field}.gamma"),
            reference_fractional_layers_mm={
                str(key): _positive(value, f"{field}.reference_fractional_layers_mm.{key}")
                for key, value in layers_raw.items()
            },
            radionuclide=SPECT_TC99M_RADIONUCLIDE,
            radiation_type=SPECT_TC99M_RADIATION_TYPE,
            tvl_key=SPECT_TC99M_TVL_KEY,
            provenance=_provenance(raw.get("provenance"), f"{field}.provenance"),
        )
        if 1.0 + record.beta_mm_inv / record.alpha_mm_inv <= 0.0:
            raise SpectPracticalTransmissionError(
                f"{record_id} Archer parameters do not define a valid zero-thickness transmission."
            )
        _validate_reference_layers(record)
        records[material_key] = record
        ids.add(record_id)

    if not records:
        raise SpectPracticalTransmissionError("SPECT practical dataset must contain at least one record.")

    dataset = LoadedSpectPracticalDataset(
        metadata=SpectPracticalDatasetMetadata(
            dataset_id=_text(metadata_raw.get("dataset_id"), "metadata.dataset_id"),
            revision=_text(metadata_raw.get("revision"), "metadata.revision"),
            description=_text(metadata_raw.get("description"), "metadata.description"),
            approval_status=status,
            model_scope=scope,
            contract_version=contract_version,
            room_scatter_caution_below_transmission=caution,
            source_model_min_transmission=minimum,
            records_sha256=digest,
        ),
        records=records,
        source_path=source.resolve(),
    )
    if require_frozen:
        metadata = dataset.metadata
        if metadata.approval_status != SPECT_PRACTICAL_FROZEN_STATUS:
            raise SpectPracticalTransmissionError(
                "SPECT practical dataset is not physics-approved and frozen."
            )
        if metadata.dataset_id != SPECT_FROZEN_PRACTICAL_DATASET_ID:
            raise SpectPracticalTransmissionError(
                "SPECT practical dataset ID is not the frozen Step 20 dataset."
            )
        if metadata.revision != SPECT_FROZEN_PRACTICAL_DATASET_REVISION:
            raise SpectPracticalTransmissionError(
                "SPECT practical dataset revision is not the frozen Step 20 revision."
            )
        if metadata.records_sha256 != SPECT_FROZEN_PRACTICAL_RECORDS_SHA256:
            raise SpectPracticalTransmissionError(
                "SPECT practical records do not match the frozen Step 20 digest."
            )
    return dataset


def load_frozen_spect_tc99m_practical_dataset(
    path: str | Path,
) -> LoadedSpectPracticalDataset:
    """Load only the exact Step 20 physics-approved/frozen practical dataset."""

    return load_spect_tc99m_practical_dataset(path, require_frozen=True)


def calculate_tc99m_transmission(
    dataset: LoadedSpectPracticalDataset,
    *,
    material_key: str,
    thickness_mm: float,
) -> SpectTransmissionResult:
    """Evaluate Step 3 broad-beam transmission with explicit low-transmission caution."""

    try:
        record = dataset.records[str(material_key).strip()]
    except KeyError as exc:
        raise SpectPracticalTransmissionError(
            f"Unsupported Tc-99m practical shielding material {material_key!r}."
        ) from exc
    transmission = archer_transmission(record, thickness_mm)
    caution = transmission <= dataset.metadata.room_scatter_caution_below_transmission
    note = (
        "Transmission is at/below the room-scatter caution threshold; ceiling/floor and "
        "finite-barrier scatter may dominate and require geometry-specific assessment."
        if caution
        else "Within the Step 3 broad-beam Archer reference-model range above the room-scatter caution threshold."
    )
    return SpectTransmissionResult(
        material_key=record.material_key,
        thickness_mm=float(thickness_mm),
        transmission=transmission,
        record_id=record.record_id,
        provenance=record.provenance.summary,
        room_scatter_caution=caution,
        scope_note=note,
    )


def calculate_tc99m_required_thickness(
    dataset: LoadedSpectPracticalDataset,
    *,
    material_key: str,
    target_transmission: float,
) -> SpectRequiredThicknessResult:
    """Invert the Step 3 Archer model without promoting it to a room-design solver."""

    try:
        record = dataset.records[str(material_key).strip()]
    except KeyError as exc:
        raise SpectPracticalTransmissionError(
            f"Unsupported Tc-99m practical shielding material {material_key!r}."
        ) from exc
    target = _unit_interval(target_transmission, "target_transmission")
    thickness = archer_required_thickness(record, target)
    caution = target <= dataset.metadata.room_scatter_caution_below_transmission
    extrapolation = target < dataset.metadata.source_model_min_transmission
    if extrapolation:
        note = (
            "Target transmission is below the source model's simulated range; the calculated thickness is an "
            "extrapolation and must not be used as a production shielding result."
        )
    elif caution:
        note = (
            "Target transmission is at/below the room-scatter caution threshold; ceiling/floor and finite-barrier "
            "scatter may dominate and require geometry-specific assessment."
        )
    else:
        note = "Within the Step 3 broad-beam Archer reference-model range above the room-scatter caution threshold."
    return SpectRequiredThicknessResult(
        material_key=record.material_key,
        target_transmission=target,
        required_thickness_mm=thickness,
        record_id=record.record_id,
        provenance=record.provenance.summary,
        room_scatter_caution=caution,
        source_model_extrapolation=extrapolation,
        scope_note=note,
    )
