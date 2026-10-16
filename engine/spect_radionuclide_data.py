"""Versioned SPECT radionuclide physics dataset and freeze boundary.

SPECT Step 20 permits both the historical development dataset and one exact
physics-approved/frozen Tc-99m dataset.  The frozen status is a physics-input
approval only: it does not make SPECT production-enabled in the desktop,
project, Results, report, or production dispatch paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Mapping


SPECT_RADIONUCLIDE_DEVELOPMENT_STATUS = "development_nonproduction"
SPECT_RADIONUCLIDE_FROZEN_STATUS = "physics_approved_frozen_nonproduction"
SPECT_RADIONUCLIDE_DATASET_STATUS = SPECT_RADIONUCLIDE_FROZEN_STATUS

SPECT_FROZEN_RADIONUCLIDE_DATASET_ID = "spect-radionuclide-physics-tc99m-source-model"
SPECT_FROZEN_RADIONUCLIDE_DATASET_REVISION = "2026-08-23-step20-1"
SPECT_FROZEN_RADIONUCLIDE_RECORDS_SHA256 = "2346bc89c2edc201dec6a849adc7149ca74ed82ce9823be962bb994bfe9ed172"


class SpectRadionuclideDataError(ValueError):
    """Raised when a SPECT radionuclide dataset is invalid."""


@dataclass(frozen=True)
class SpectRadionuclideRecord:
    code: str
    display_name: str
    half_life_h: float
    dose_rate_constant_uSv_h_per_MBq_at_1m: float
    radiation_type: str
    tvl_key: str
    half_life_provenance: str
    dose_rate_provenance: str


@dataclass(frozen=True)
class SpectRadionuclideDatasetMetadata:
    dataset_id: str
    revision: str
    description: str
    approval_status: str
    records_sha256: str


@dataclass(frozen=True)
class LoadedSpectRadionuclideDataset:
    metadata: SpectRadionuclideDatasetMetadata
    records: Mapping[str, SpectRadionuclideRecord]
    source_path: Path


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SpectRadionuclideDataError(f"{field} must not be blank.")
    return text


def records_sha256(payload: dict) -> str:
    canonical = json.dumps(
        payload.get("records"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def load_spect_radionuclide_dataset(
    path: str | Path,
    *,
    require_frozen: bool = False,
) -> LoadedSpectRadionuclideDataset:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpectRadionuclideDataError(
            f"Unable to load SPECT radionuclide dataset {source}."
        ) from exc

    if not isinstance(payload, dict):
        raise SpectRadionuclideDataError("SPECT radionuclide dataset root must be an object.")
    metadata_raw = payload.get("metadata")
    records_raw = payload.get("records")
    if not isinstance(metadata_raw, dict) or not isinstance(records_raw, list):
        raise SpectRadionuclideDataError(
            "SPECT radionuclide dataset requires metadata and records."
        )

    status = _text(metadata_raw.get("approval_status"), "metadata.approval_status")
    if status not in {
        SPECT_RADIONUCLIDE_DEVELOPMENT_STATUS,
        SPECT_RADIONUCLIDE_FROZEN_STATUS,
    }:
        raise SpectRadionuclideDataError(
            "SPECT radionuclide dataset approval_status must be "
            "development_nonproduction or physics_approved_frozen_nonproduction."
        )

    digest = records_sha256(payload)
    expected_digest = str(metadata_raw.get("records_sha256") or "").strip()
    if expected_digest and expected_digest != digest:
        raise SpectRadionuclideDataError(
            "SPECT radionuclide record digest does not match metadata."
        )
    if status == SPECT_RADIONUCLIDE_FROZEN_STATUS:
        approved_digest = _text(
            metadata_raw.get("approved_records_sha256"),
            "metadata.approved_records_sha256",
        )
        if approved_digest != digest:
            raise SpectRadionuclideDataError(
                "Frozen SPECT radionuclide record digest does not match approval metadata."
            )

    metadata = SpectRadionuclideDatasetMetadata(
        dataset_id=_text(metadata_raw.get("dataset_id"), "metadata.dataset_id"),
        revision=_text(metadata_raw.get("revision"), "metadata.revision"),
        description=_text(metadata_raw.get("description"), "metadata.description"),
        approval_status=status,
        records_sha256=digest,
    )

    records: dict[str, SpectRadionuclideRecord] = {}
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise SpectRadionuclideDataError(f"records[{index}] must be an object.")
        code = _text(raw.get("code"), f"records[{index}].code")
        if code in records:
            raise SpectRadionuclideDataError(f"Duplicate SPECT radionuclide code {code!r}.")
        try:
            half_life_h = float(raw.get("half_life_h"))
            constant = float(raw.get("dose_rate_constant_uSv_h_per_MBq_at_1m"))
        except (TypeError, ValueError) as exc:
            raise SpectRadionuclideDataError(
                f"records[{index}] contains a non-numeric physics value."
            ) from exc
        if not isfinite(half_life_h) or half_life_h <= 0.0:
            raise SpectRadionuclideDataError(f"Invalid half_life_h for {code}.")
        if not isfinite(constant) or constant <= 0.0:
            raise SpectRadionuclideDataError(
                f"Invalid dose_rate_constant_uSv_h_per_MBq_at_1m for {code}."
            )
        records[code] = SpectRadionuclideRecord(
            code=code,
            display_name=_text(raw.get("display_name"), f"records[{index}].display_name"),
            half_life_h=half_life_h,
            dose_rate_constant_uSv_h_per_MBq_at_1m=constant,
            radiation_type=_text(raw.get("radiation_type"), f"records[{index}].radiation_type"),
            tvl_key=_text(raw.get("tvl_key"), f"records[{index}].tvl_key"),
            half_life_provenance=_text(
                raw.get("half_life_provenance"), f"records[{index}].half_life_provenance"
            ),
            dose_rate_provenance=_text(
                raw.get("dose_rate_provenance"), f"records[{index}].dose_rate_provenance"
            ),
        )
    if not records:
        raise SpectRadionuclideDataError("SPECT radionuclide dataset must contain a record.")

    dataset = LoadedSpectRadionuclideDataset(metadata, records, source.resolve())
    if require_frozen:
        if metadata.approval_status != SPECT_RADIONUCLIDE_FROZEN_STATUS:
            raise SpectRadionuclideDataError(
                "SPECT radionuclide dataset is not physics-approved and frozen."
            )
        if metadata.dataset_id != SPECT_FROZEN_RADIONUCLIDE_DATASET_ID:
            raise SpectRadionuclideDataError(
                "SPECT radionuclide dataset ID is not the frozen Step 20 dataset."
            )
        if metadata.revision != SPECT_FROZEN_RADIONUCLIDE_DATASET_REVISION:
            raise SpectRadionuclideDataError(
                "SPECT radionuclide dataset revision is not the frozen Step 20 revision."
            )
        if metadata.records_sha256 != SPECT_FROZEN_RADIONUCLIDE_RECORDS_SHA256:
            raise SpectRadionuclideDataError(
                "SPECT radionuclide records do not match the frozen Step 20 digest."
            )
    return dataset


def load_frozen_spect_radionuclide_dataset(
    path: str | Path,
) -> LoadedSpectRadionuclideDataset:
    """Load only the exact Step 20 physics-approved/frozen Tc-99m dataset."""

    return load_spect_radionuclide_dataset(path, require_frozen=True)
