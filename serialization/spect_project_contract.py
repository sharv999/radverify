"""Versioned non-production SPECT Step 1 snapshot contract."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from engine.isotropic_barrier_solver import IsotropicBarrierSolverResult, TvlAttenuationInput
from modalities.spect import (
    SPECT_BARRIER_ADAPTER_CONTRACT_VERSION,
    SPECT_PHYSICS_CONTRACT_VERSION,
    SPECT_SOURCE_TYPE,
    SpectBarrierCalculationResult,
    SpectPhysicsResult,
    SpectSourceDomain,
)

SPECT_PROJECT_SERIALIZATION_SCHEMA = "radshield_spect_project_domain_v1"
SPECT_PROJECT_SERIALIZATION_VERSION = 1


class SpectProjectSerializationError(ValueError):
    pass


@dataclass(frozen=True)
class SpectBarrierSnapshot:
    result: SpectBarrierCalculationResult
    attenuation: TvlAttenuationInput


@dataclass(frozen=True)
class SpectProjectDomainSnapshot:
    source: SpectSourceDomain
    physics_result: SpectPhysicsResult
    barrier_results: tuple[SpectBarrierSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, SpectSourceDomain):
            raise SpectProjectSerializationError("source must be a SpectSourceDomain.")
        if not isinstance(self.physics_result, SpectPhysicsResult):
            raise SpectProjectSerializationError("physics_result must be a SpectPhysicsResult.")
        if self.physics_result.radionuclide != self.source.radionuclide_spec.code:
            raise SpectProjectSerializationError("physics_result radionuclide must match source.")
        for item in self.barrier_results:
            if not isinstance(item, SpectBarrierSnapshot):
                raise SpectProjectSerializationError("barrier_results must contain SpectBarrierSnapshot values.")
            solved = item.result.solver_result
            if solved.source_type != SPECT_SOURCE_TYPE:
                raise SpectProjectSerializationError("SPECT barrier source_type mismatch.")
            if solved.tvl_key != item.attenuation.tvl_key:
                raise SpectProjectSerializationError("SPECT barrier attenuation tvl_key mismatch.")


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpectProjectSerializationError(f"{name} must be numeric.") from exc
    if not isfinite(number):
        raise SpectProjectSerializationError(f"{name} must be finite.")
    return number


def _text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SpectProjectSerializationError(f"{name} must not be blank.")
    return text


def spect_project_snapshot_to_dict(snapshot: SpectProjectDomainSnapshot) -> dict[str, Any]:
    if not isinstance(snapshot, SpectProjectDomainSnapshot):
        raise SpectProjectSerializationError("snapshot must be a SpectProjectDomainSnapshot.")
    return {
        "schema": SPECT_PROJECT_SERIALIZATION_SCHEMA,
        "version": SPECT_PROJECT_SERIALIZATION_VERSION,
        "source": {
            "radionuclide": snapshot.source.radionuclide_spec.code,
            "administered_activity_mbq": float(snapshot.source.administered_activity_mbq),
            "patients_per_week": float(snapshot.source.patients_per_week),
            "imaging_duration_h": float(snapshot.source.imaging_duration_h),
        },
        "physics_result": {
            "contract_version": snapshot.physics_result.contract_version,
            "radionuclide": snapshot.physics_result.radionuclide,
            "radiation_type": snapshot.physics_result.radiation_type,
            "tvl_key": snapshot.physics_result.tvl_key,
            "administered_activity_mbq": snapshot.physics_result.administered_activity_mbq,
            "patients_per_week": snapshot.physics_result.patients_per_week,
            "imaging_duration_h": snapshot.physics_result.imaging_duration_h,
            "decay_integrated_hours": snapshot.physics_result.decay_integrated_hours,
            "weekly_dose_uSv_at_1m": snapshot.physics_result.weekly_dose_uSv_at_1m,
            "calculation_basis": snapshot.physics_result.calculation_basis,
        },
        "barrier_results": [
            {
                "adapter_contract_version": item.result.adapter_contract_version,
                "attenuation": {
                    "material_key": item.attenuation.material_key,
                    "tvl_key": item.attenuation.tvl_key,
                    "tvl1_mm": item.attenuation.tvl1_mm,
                    "tvle_mm": item.attenuation.tvle_mm,
                    "attenuation_record_id": item.attenuation.attenuation_record_id,
                    "attenuation_provenance": item.attenuation.attenuation_provenance,
                },
                "solver_result": {
                    field: getattr(item.result.solver_result, field)
                    for field in item.result.solver_result.__dataclass_fields__
                },
            }
            for item in snapshot.barrier_results
        ],
    }


def spect_project_snapshot_from_dict(payload: Mapping[str, Any]) -> SpectProjectDomainSnapshot:
    if not isinstance(payload, Mapping):
        raise SpectProjectSerializationError("SPECT snapshot payload must be a mapping.")
    if payload.get("schema") != SPECT_PROJECT_SERIALIZATION_SCHEMA:
        raise SpectProjectSerializationError("Unsupported SPECT snapshot schema.")
    if payload.get("version") != SPECT_PROJECT_SERIALIZATION_VERSION:
        raise SpectProjectSerializationError("Unsupported SPECT snapshot version.")
    source_raw = payload.get("source")
    physics_raw = payload.get("physics_result")
    barriers_raw = payload.get("barrier_results", ())
    if not isinstance(source_raw, Mapping) or not isinstance(physics_raw, Mapping):
        raise SpectProjectSerializationError("SPECT snapshot source and physics_result must be mappings.")
    if isinstance(barriers_raw, (str, bytes)) or not isinstance(barriers_raw, Sequence):
        raise SpectProjectSerializationError("barrier_results must be a sequence.")

    source = SpectSourceDomain(
        radionuclide=_text(source_raw.get("radionuclide"), "source.radionuclide"),
        administered_activity_mbq=_number(source_raw.get("administered_activity_mbq"), "source.administered_activity_mbq"),
        patients_per_week=_number(source_raw.get("patients_per_week"), "source.patients_per_week"),
        imaging_duration_h=_number(source_raw.get("imaging_duration_h"), "source.imaging_duration_h"),
    )
    contract_version = int(physics_raw.get("contract_version", 0))
    if contract_version != SPECT_PHYSICS_CONTRACT_VERSION:
        raise SpectProjectSerializationError("Unsupported SPECT physics contract version.")
    physics = SpectPhysicsResult(
        contract_version=contract_version,
        radionuclide=_text(physics_raw.get("radionuclide"), "physics_result.radionuclide"),
        radiation_type=_text(physics_raw.get("radiation_type"), "physics_result.radiation_type"),
        tvl_key=_text(physics_raw.get("tvl_key"), "physics_result.tvl_key"),
        administered_activity_mbq=_number(physics_raw.get("administered_activity_mbq"), "physics_result.administered_activity_mbq"),
        patients_per_week=_number(physics_raw.get("patients_per_week"), "physics_result.patients_per_week"),
        imaging_duration_h=_number(physics_raw.get("imaging_duration_h"), "physics_result.imaging_duration_h"),
        decay_integrated_hours=_number(physics_raw.get("decay_integrated_hours"), "physics_result.decay_integrated_hours"),
        weekly_dose_uSv_at_1m=_number(physics_raw.get("weekly_dose_uSv_at_1m"), "physics_result.weekly_dose_uSv_at_1m"),
        calculation_basis=_text(physics_raw.get("calculation_basis"), "physics_result.calculation_basis"),
    )

    barrier_items: list[SpectBarrierSnapshot] = []
    for index, raw in enumerate(barriers_raw):
        if not isinstance(raw, Mapping):
            raise SpectProjectSerializationError(f"barrier_results[{index}] must be a mapping.")
        if int(raw.get("adapter_contract_version", 0)) != SPECT_BARRIER_ADAPTER_CONTRACT_VERSION:
            raise SpectProjectSerializationError("Unsupported SPECT barrier adapter contract version.")
        attenuation_raw = raw.get("attenuation")
        solved_raw = raw.get("solver_result")
        if not isinstance(attenuation_raw, Mapping) or not isinstance(solved_raw, Mapping):
            raise SpectProjectSerializationError("SPECT barrier attenuation and solver_result must be mappings.")
        attenuation = TvlAttenuationInput(
            material_key=_text(attenuation_raw.get("material_key"), "attenuation.material_key"),
            tvl_key=_text(attenuation_raw.get("tvl_key"), "attenuation.tvl_key"),
            tvl1_mm=_number(attenuation_raw.get("tvl1_mm"), "attenuation.tvl1_mm"),
            tvle_mm=_number(attenuation_raw.get("tvle_mm"), "attenuation.tvle_mm"),
            attenuation_record_id=str(attenuation_raw.get("attenuation_record_id") or ""),
            attenuation_provenance=str(attenuation_raw.get("attenuation_provenance") or ""),
        )
        kwargs = dict(solved_raw)
        solved = IsotropicBarrierSolverResult(**kwargs)
        barrier_items.append(
            SpectBarrierSnapshot(
                result=SpectBarrierCalculationResult(
                    adapter_contract_version=SPECT_BARRIER_ADAPTER_CONTRACT_VERSION,
                    solver_result=solved,
                ),
                attenuation=attenuation,
            )
        )
    return SpectProjectDomainSnapshot(source, physics, tuple(barrier_items))
