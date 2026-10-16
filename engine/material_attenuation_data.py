"""Validated material attenuation data boundary for isotropic sources.

This module owns radionuclide/energy-keyed TVL records and their provenance.
It intentionally contains no built-in PET or SPECT attenuation values: a
future reviewed data file can populate the same contract without coupling the
library to UI, reports, modality registration, or production dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


MATERIAL_ATTENUATION_CONTRACT_VERSION = 1


class MaterialAttenuationDataError(ValueError):
    """Raised when attenuation data or lookup input violates the contract."""


def _text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MaterialAttenuationDataError(f"{name} must not be blank.")
    return text


def _positive(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MaterialAttenuationDataError(f"{name} must be numeric.") from exc
    if not isfinite(number) or number <= 0.0:
        raise MaterialAttenuationDataError(f"{name} must be finite and greater than zero.")
    return number


@dataclass(frozen=True)
class AttenuationProvenance:
    """Auditable citation for one attenuation record."""

    source_title: str
    source_organisation: str
    publication_year: int
    table_or_section: str
    reference_id: str
    edition: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_title", _text("source_title", self.source_title))
        object.__setattr__(
            self, "source_organisation", _text("source_organisation", self.source_organisation)
        )
        try:
            year = int(self.publication_year)
        except (TypeError, ValueError) as exc:
            raise MaterialAttenuationDataError("publication_year must be an integer.") from exc
        if not 1900 <= year <= 2100:
            raise MaterialAttenuationDataError("publication_year must be between 1900 and 2100.")
        object.__setattr__(self, "publication_year", year)
        object.__setattr__(self, "table_or_section", _text("table_or_section", self.table_or_section))
        object.__setattr__(self, "reference_id", _text("reference_id", self.reference_id))
        object.__setattr__(self, "edition", str(self.edition or "").strip())
        object.__setattr__(self, "notes", str(self.notes or "").strip())

    @property
    def summary(self) -> str:
        edition = f", {self.edition}" if self.edition else ""
        return (
            f"{self.source_organisation}, {self.source_title}{edition} "
            f"({self.publication_year}), {self.table_or_section}; {self.reference_id}"
        )


@dataclass(frozen=True)
class MaterialAttenuationRecord:
    """One material TVL record keyed by radiation identity and material."""

    record_id: str
    tvl_key: str
    radiation_type: str
    material_key: str
    tvl1_mm: float
    tvle_mm: float
    provenance: AttenuationProvenance
    radionuclides: tuple[str, ...] = ()
    nominal_energy_kev: float | None = None
    contract_version: int = MATERIAL_ATTENUATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _text("record_id", self.record_id))
        object.__setattr__(self, "tvl_key", _text("tvl_key", self.tvl_key))
        object.__setattr__(self, "radiation_type", _text("radiation_type", self.radiation_type))
        object.__setattr__(self, "material_key", _text("material_key", self.material_key))
        object.__setattr__(self, "tvl1_mm", _positive("tvl1_mm", self.tvl1_mm))
        object.__setattr__(self, "tvle_mm", _positive("tvle_mm", self.tvle_mm))
        if not isinstance(self.provenance, AttenuationProvenance):
            raise MaterialAttenuationDataError("provenance must be AttenuationProvenance.")
        radionuclides = tuple(_text("radionuclide", item) for item in self.radionuclides)
        if len(set(radionuclides)) != len(radionuclides):
            raise MaterialAttenuationDataError("radionuclides must not contain duplicates.")
        object.__setattr__(self, "radionuclides", radionuclides)
        if self.nominal_energy_kev is not None:
            object.__setattr__(
                self, "nominal_energy_kev", _positive("nominal_energy_kev", self.nominal_energy_kev)
            )
        if int(self.contract_version) != MATERIAL_ATTENUATION_CONTRACT_VERSION:
            raise MaterialAttenuationDataError(
                f"Unsupported material attenuation contract version {self.contract_version!r}."
            )

    @property
    def lookup_key(self) -> tuple[str, str]:
        return (self.tvl_key, self.material_key)


class MaterialAttenuationLibrary:
    """Immutable, validated collection of attenuation records."""

    def __init__(self, records: Iterable[MaterialAttenuationRecord], *, library_id: str, revision: str):
        self.library_id = _text("library_id", library_id)
        self.revision = _text("revision", revision)
        resolved = tuple(records)
        by_key: dict[tuple[str, str], MaterialAttenuationRecord] = {}
        ids: set[str] = set()
        for record in resolved:
            if not isinstance(record, MaterialAttenuationRecord):
                raise MaterialAttenuationDataError(
                    "records must contain only MaterialAttenuationRecord values."
                )
            if record.lookup_key in by_key:
                raise MaterialAttenuationDataError(
                    "Duplicate attenuation lookup key "
                    f"tvl_key={record.tvl_key!r}, material_key={record.material_key!r}."
                )
            if record.record_id in ids:
                raise MaterialAttenuationDataError(
                    f"Duplicate attenuation record_id {record.record_id!r}."
                )
            by_key[record.lookup_key] = record
            ids.add(record.record_id)
        self.records = resolved
        self._by_key = by_key

    def lookup(
        self,
        *,
        tvl_key: str,
        material_key: str,
        radiation_type: str | None = None,
    ) -> MaterialAttenuationRecord:
        key = (_text("tvl_key", tvl_key), _text("material_key", material_key))
        try:
            record = self._by_key[key]
        except KeyError as exc:
            raise MaterialAttenuationDataError(
                f"No attenuation record for tvl_key={key[0]!r}, material_key={key[1]!r}."
            ) from exc
        if radiation_type is not None and _text("radiation_type", radiation_type) != record.radiation_type:
            raise MaterialAttenuationDataError(
                "Resolved attenuation radiation_type does not match the requested radiation_type."
            )
        return record


def attenuation_record_to_solver_input(record: MaterialAttenuationRecord):
    """Resolve a reviewed record into the isotropic solver's narrow input type."""

    if not isinstance(record, MaterialAttenuationRecord):
        raise MaterialAttenuationDataError("record must be a MaterialAttenuationRecord.")
    from engine.isotropic_barrier_solver import TvlAttenuationInput

    return TvlAttenuationInput(
        material_key=record.material_key,
        tvl_key=record.tvl_key,
        tvl1_mm=record.tvl1_mm,
        tvle_mm=record.tvle_mm,
        attenuation_record_id=record.record_id,
        attenuation_provenance=record.provenance.summary,
    )

# Dataset-loader contract.  The loader is intentionally strict: datasets that
# have not been explicitly approved for production are rejected unless the
# caller opts into a non-production/test override.

import json
from pathlib import Path
from typing import Any

MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION = 1
APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL = "reviewed_pending_user_approval"
APPROVAL_STATUS_PRODUCTION_APPROVED = "production_approved"
_ALLOWED_APPROVAL_STATUSES = {
    APPROVAL_STATUS_REVIEWED_PENDING_USER_APPROVAL,
    APPROVAL_STATUS_PRODUCTION_APPROVED,
}


@dataclass(frozen=True)
class AttenuationDatasetMetadata:
    """Identity, review state and provenance scope for one JSON dataset."""

    dataset_id: str
    revision: str
    description: str
    approval_status: str
    reviewed_by: str
    reviewed_date: str
    approved_by: str = ""
    approved_date: str = ""
    schema_version: int = MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text("dataset_id", self.dataset_id))
        object.__setattr__(self, "revision", _text("revision", self.revision))
        object.__setattr__(self, "description", _text("description", self.description))
        status = _text("approval_status", self.approval_status)
        if status not in _ALLOWED_APPROVAL_STATUSES:
            raise MaterialAttenuationDataError(
                f"Unsupported attenuation dataset approval_status {status!r}."
            )
        object.__setattr__(self, "approval_status", status)
        object.__setattr__(self, "reviewed_by", _text("reviewed_by", self.reviewed_by))
        object.__setattr__(self, "reviewed_date", _text("reviewed_date", self.reviewed_date))
        object.__setattr__(self, "approved_by", str(self.approved_by or "").strip())
        object.__setattr__(self, "approved_date", str(self.approved_date or "").strip())
        if int(self.schema_version) != MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION:
            raise MaterialAttenuationDataError(
                f"Unsupported attenuation dataset schema version {self.schema_version!r}."
            )
        if status == APPROVAL_STATUS_PRODUCTION_APPROVED:
            if not self.approved_by or not self.approved_date:
                raise MaterialAttenuationDataError(
                    "Production-approved datasets require approved_by and approved_date."
                )
        elif self.approved_by or self.approved_date:
            raise MaterialAttenuationDataError(
                "Unapproved datasets must not contain approval sign-off fields."
            )

    @property
    def production_approved(self) -> bool:
        return self.approval_status == APPROVAL_STATUS_PRODUCTION_APPROVED


@dataclass(frozen=True)
class LoadedMaterialAttenuationDataset:
    """Validated metadata and immutable attenuation library loaded from JSON."""

    metadata: AttenuationDatasetMetadata
    library: MaterialAttenuationLibrary
    source_path: Path


def _mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MaterialAttenuationDataError(f"{name} must be a JSON object.")
    return value


def _sequence(name: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise MaterialAttenuationDataError(f"{name} must be a JSON array.")
    return value


def _provenance_from_mapping(value: Any) -> AttenuationProvenance:
    data = _mapping("provenance", value)
    try:
        return AttenuationProvenance(
            source_title=data["source_title"],
            source_organisation=data["source_organisation"],
            publication_year=data["publication_year"],
            table_or_section=data["table_or_section"],
            reference_id=data["reference_id"],
            edition=data.get("edition", ""),
            notes=data.get("notes", ""),
        )
    except KeyError as exc:
        raise MaterialAttenuationDataError(
            f"provenance is missing required field {exc.args[0]!r}."
        ) from exc


def _record_from_mapping(value: Any) -> MaterialAttenuationRecord:
    data = _mapping("record", value)
    try:
        return MaterialAttenuationRecord(
            record_id=data["record_id"],
            tvl_key=data["tvl_key"],
            radiation_type=data["radiation_type"],
            material_key=data["material_key"],
            tvl1_mm=data["tvl1_mm"],
            tvle_mm=data["tvle_mm"],
            provenance=_provenance_from_mapping(data["provenance"]),
            radionuclides=tuple(data.get("radionuclides", ())),
            nominal_energy_kev=data.get("nominal_energy_kev"),
            contract_version=data.get(
                "contract_version", MATERIAL_ATTENUATION_CONTRACT_VERSION
            ),
        )
    except KeyError as exc:
        raise MaterialAttenuationDataError(
            f"record is missing required field {exc.args[0]!r}."
        ) from exc


def load_material_attenuation_dataset(
    path: str | Path,
    *,
    allow_unapproved: bool = False,
) -> LoadedMaterialAttenuationDataset:
    """Load and validate a JSON attenuation dataset.

    Production use is fail-closed.  A dataset whose approval status is not
    ``production_approved`` can only be loaded when ``allow_unapproved=True``;
    that override exists for tests and explicit pre-production review tools.
    """

    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MaterialAttenuationDataError(
            f"Unable to read attenuation dataset {source_path}."
        ) from exc
    except json.JSONDecodeError as exc:
        raise MaterialAttenuationDataError(
            f"Attenuation dataset {source_path} is not valid JSON."
        ) from exc

    root = _mapping("dataset", payload)
    metadata_data = _mapping("metadata", root.get("metadata"))
    try:
        metadata = AttenuationDatasetMetadata(
            dataset_id=metadata_data["dataset_id"],
            revision=metadata_data["revision"],
            description=metadata_data["description"],
            approval_status=metadata_data["approval_status"],
            reviewed_by=metadata_data["reviewed_by"],
            reviewed_date=metadata_data["reviewed_date"],
            approved_by=metadata_data.get("approved_by", ""),
            approved_date=metadata_data.get("approved_date", ""),
            schema_version=metadata_data.get(
                "schema_version", MATERIAL_ATTENUATION_DATASET_SCHEMA_VERSION
            ),
        )
    except KeyError as exc:
        raise MaterialAttenuationDataError(
            f"metadata is missing required field {exc.args[0]!r}."
        ) from exc

    if not metadata.production_approved and not allow_unapproved:
        raise MaterialAttenuationDataError(
            "Attenuation dataset is not approved for production use; "
            "set allow_unapproved=True only for tests or explicit review."
        )

    records = tuple(_record_from_mapping(item) for item in _sequence("records", root.get("records")))
    if not records:
        raise MaterialAttenuationDataError("Attenuation dataset must contain at least one record.")

    library = MaterialAttenuationLibrary(
        records,
        library_id=metadata.dataset_id,
        revision=metadata.revision,
    )
    return LoadedMaterialAttenuationDataset(
        metadata=metadata,
        library=library,
        source_path=source_path.resolve(),
    )
