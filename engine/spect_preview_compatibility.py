"""SPECT preview physics provenance/compatibility boundary.

Step 15 records the exact development datasets and headless SPECT model
contract versions used by a dedicated ``.spectpreview.json`` snapshot.  This
module remains outside normal project serialization and production dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

from engine.spect_attenuation_data import load_spect_tc99m_attenuation_dataset
from engine.spect_barrier_calculation import (
    SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION,
    SPECT_PRACTICAL_DATASET_PATH,
)
from engine.spect_barrier_schedule import SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION
from engine.spect_practical_transmission import load_spect_tc99m_practical_dataset
from modalities.spect import (
    SPECT_PHYSICS_CONTRACT_VERSION,
    SPECT_RADIONUCLIDE_DATASET_METADATA,
    SPECT_RADIONUCLIDE_DATASET_PATH,
)

_ROOT = Path(__file__).resolve().parents[1]
SPECT_ATTENUATION_DATASET_PATH = _ROOT / "data" / "spect" / "spect_tc99m_attenuation_development.json"
SPECT_PREVIEW_COMPATIBILITY_CONTRACT_VERSION = 1


class SpectPreviewCompatibilityError(ValueError):
    """Raised when preview physics provenance is malformed or incompatible."""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_spect_preview_physics_compatibility() -> dict[str, Any]:
    attenuation = load_spect_tc99m_attenuation_dataset(SPECT_ATTENUATION_DATASET_PATH)
    practical = load_spect_tc99m_practical_dataset(SPECT_PRACTICAL_DATASET_PATH)
    source = SPECT_RADIONUCLIDE_DATASET_METADATA
    return {
        "contract_version": SPECT_PREVIEW_COMPATIBILITY_CONTRACT_VERSION,
        "radionuclide_dataset": {
            "dataset_id": source.dataset_id,
            "revision": source.revision,
            "approval_status": source.approval_status,
            "file_sha256": _file_sha256(SPECT_RADIONUCLIDE_DATASET_PATH),
        },
        "attenuation_dataset": {
            "dataset_id": attenuation.metadata.dataset_id,
            "revision": attenuation.metadata.revision,
            "approval_status": attenuation.metadata.approval_status,
            "model_scope": attenuation.metadata.model_scope,
            "contract_version": attenuation.metadata.contract_version,
            "records_sha256": attenuation.metadata.records_sha256,
        },
        "practical_transmission_dataset": {
            "dataset_id": practical.metadata.dataset_id,
            "revision": practical.metadata.revision,
            "approval_status": practical.metadata.approval_status,
            "model_scope": practical.metadata.model_scope,
            "contract_version": practical.metadata.contract_version,
            "records_sha256": practical.metadata.records_sha256,
        },
        "model_contracts": {
            "spect_physics_contract_version": SPECT_PHYSICS_CONTRACT_VERSION,
            "practical_barrier_adapter_contract_version": SPECT_PRACTICAL_BARRIER_ADAPTER_CONTRACT_VERSION,
            "barrier_schedule_contract_version": SPECT_BARRIER_SCHEDULE_CONTRACT_VERSION,
        },
    }


def validate_spect_preview_physics_compatibility(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SpectPreviewCompatibilityError("SPECT preview physics_compatibility must be an object.")
    supplied = dict(value)
    expected = current_spect_preview_physics_compatibility()
    if supplied != expected:
        raise SpectPreviewCompatibilityError(
            "SPECT preview physics compatibility check failed: the snapshot was created "
            "against a different SPECT dataset or model revision."
        )
    return expected
