"""Frozen output contract for the non-production single-source PET preview.

This module owns the displayed calculation summary, assumptions, provenance,
barrier-schedule fields, and deterministic calculation reasoning.  It is a
presentation contract only and is intentionally outside production Results,
project serialization, calculation dispatch, and reports.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


PET_PREVIEW_OUTPUT_CONTRACT_VERSION = 4
PET_PREVIEW_OUTPUT_BASELINE = "pet-single-source-output-v4-activity-retention"
PET_RADIONUCLIDE_DATA_PROVENANCE = (
    "Versioned PET radionuclide dataset with per-field source references, "
    "derivations, record digest, review status, and approval metadata."
)

PET_DISPLAYED_ASSUMPTIONS = (
    "One PET patient/source position is modelled per selected room.",
    "All exposure periods occur at that same PET position.",
    "Physical decay before each exposure period is determined from its absolute start time after administration.",
    "Physical decay is integrated exactly over each exposure period.",
    "Each exposure period may apply an explicit activity-retention factor after biological removal such as voiding.",
    "The patient is represented as an isotropic point source referenced at 1 m.",
    "Dose at each barrier is scaled by inverse square using the PET-specific position.",
    "Occupancy is applied after geometric distance scaling.",
    "Required shielding uses the approved 511 keV broad-beam TVL1/TVLe dataset.",
    "The CT component of PET/CT remains assessed separately through the CT modality.",
    "This preview is non-production and is excluded from saved projects and reports.",
)

PET_OUTPUT_SCHEDULE_COLUMNS = (
    ("name", "Barrier", 150),
    ("material", "Material", 165),
    ("distance", "Distance (m)", 85),
    ("occupancy", "Occupancy T", 85),
    ("goal", "Design goal (µSv/week)", 135),
    ("tvls", "Required TVLs", 95),
    ("required", "Required (mm)", 100),
    ("provided", "Provided (mm)", 100),
    ("transmitted", "Transmitted dose (µSv/week)", 160),
    ("status", "Status", 100),
    ("reasoning", "Calculation reasoning", 430),
)


def _fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return "not assessed"
    return f"{float(value):.{digits}g}"


def build_barrier_reasoning(row: Mapping[str, Any]) -> str:
    """Return deterministic user-facing reasoning for one barrier row."""

    distance = _fmt(row["distance_m"])
    dose_at_barrier = _fmt(row["unshielded_weekly_dose_uSv_at_barrier"])
    occupancy = _fmt(row["occupancy_factor"])
    occupied = _fmt(row["occupied_unshielded_weekly_dose_uSv"])
    goal = _fmt(row["design_goal_uSv_per_week"])
    transmission = _fmt(row["required_transmission"])
    tvls = _fmt(row["required_tvl_count"])
    required = _fmt(row["required_thickness_mm"])
    provided = _fmt(row.get("provided_thickness_mm"))
    transmitted = _fmt(row.get("transmitted_weekly_dose_uSv"))
    status = str(row["compliance_status"])
    return (
        f"1 m workload scaled to {distance} m by inverse square = {dose_at_barrier} µSv/week; "
        f"occupancy T={occupancy} gives {occupied} µSv/week; goal {goal} µSv/week requires "
        f"transmission {transmission}, {tvls} TVLs and {required} mm. Provided {provided} mm "
        f"gives {transmitted} µSv/week: {status}."
    )


def build_pet_preview_output_contract(
    *,
    source: Any,
    physics_result: Any,
    barrier_rows: Sequence[Mapping[str, Any]],
    replay_verified: bool,
) -> dict[str, Any]:
    """Build the frozen calculation-summary and schedule output payload."""

    radionuclide = source.radionuclide_spec
    from modalities.pet import PET_RADIONUCLIDE_DATASET_METADATA
    radionuclide_dataset = PET_RADIONUCLIDE_DATASET_METADATA
    rows = tuple(dict(row, calculation_reasoning=build_barrier_reasoning(row)) for row in barrier_rows)
    datasets = []
    seen = set()
    for row in rows:
        identity = (
            row["dataset_id"], row["dataset_revision"], row["approved_by"], row["approved_date"]
        )
        if identity not in seen:
            seen.add(identity)
            datasets.append({
                "dataset_id": row["dataset_id"],
                "dataset_revision": row["dataset_revision"],
                "approved_by": row["approved_by"],
                "approved_date": row["approved_date"],
            })

    return {
        "output_contract_version": PET_PREVIEW_OUTPUT_CONTRACT_VERSION,
        "output_baseline": PET_PREVIEW_OUTPUT_BASELINE,
        "production_eligible": False,
        "single_source_per_room": True,
        "replay_verified": bool(replay_verified),
        "calculation_basis": physics_result.calculation_basis,
        "weekly_dose_uSv_at_1m": physics_result.weekly_dose_uSv_at_1m,
        "displayed_assumptions": PET_DISPLAYED_ASSUMPTIONS,
        "radionuclide_data": {
            "code": radionuclide.code,
            "display_name": radionuclide.display_name,
            "half_life_h": radionuclide.half_life_h,
            "dose_rate_constant_uSv_h_per_MBq_at_1m": radionuclide.dose_rate_constant_uSv_h_per_MBq_at_1m,
            "radiation_type": radionuclide.radiation_type,
            "dataset_id": radionuclide_dataset.dataset_id,
            "dataset_revision": radionuclide_dataset.revision,
            "dataset_approval_status": radionuclide_dataset.approval_status,
            "dataset_reviewed_by": radionuclide_dataset.reviewed_by,
            "dataset_reviewed_date": radionuclide_dataset.reviewed_date,
            "dataset_approved_by": radionuclide_dataset.approved_by,
            "dataset_approved_date": radionuclide_dataset.approved_date,
            "dataset_records_sha256": radionuclide_dataset.records_sha256,
            "half_life_provenance": {
                "source_title": radionuclide.half_life_provenance.source_title,
                "source_organisation": radionuclide.half_life_provenance.source_organisation,
                "source_value": radionuclide.half_life_provenance.source_value,
                "reference_id": radionuclide.half_life_provenance.reference_id,
                "accessed_date": radionuclide.half_life_provenance.accessed_date,
                "derivation": radionuclide.half_life_provenance.derivation,
            },
            "dose_rate_provenance": {
                "source_title": radionuclide.dose_rate_provenance.source_title,
                "source_organisation": radionuclide.dose_rate_provenance.source_organisation,
                "source_value": radionuclide.dose_rate_provenance.source_value,
                "reference_id": radionuclide.dose_rate_provenance.reference_id,
                "accessed_date": radionuclide.dose_rate_provenance.accessed_date,
                "derivation": radionuclide.dose_rate_provenance.derivation,
            },
        },
        "attenuation_datasets": tuple(datasets),
        "rows": rows,
    }


def format_pet_calculation_summary(output: Mapping[str, Any]) -> str:
    """Format the frozen multi-line summary displayed in the PET preview tab."""

    radionuclide = output["radionuclide_data"]
    datasets = output["attenuation_datasets"]
    dataset_text = "; ".join(
        f"{item['dataset_id']} rev {item['dataset_revision']} "
        f"(approved by {item['approved_by']} on {item['approved_date']})"
        for item in datasets
    ) or "No attenuation dataset resolved"
    assumptions = "\n".join(f"• {item}" for item in output["displayed_assumptions"])
    return (
        f"{radionuclide['display_name']} weekly unshielded dose at 1 m: "
        f"{output['weekly_dose_uSv_at_1m']:.6g} µSv/week\n"
        f"Calculation basis: {output['calculation_basis']}\n"
        f"Radionuclide data: half-life {radionuclide['half_life_h']:.6g} h; dose-rate constant "
        f"{radionuclide['dose_rate_constant_uSv_h_per_MBq_at_1m']:.6g} µSv·h⁻¹·MBq⁻¹ at 1 m.\n"
        f"Radionuclide dataset: {radionuclide['dataset_id']} rev {radionuclide['dataset_revision']} "
        f"({radionuclide['dataset_approval_status']}; SHA-256 {radionuclide['dataset_records_sha256']}).\n"
        f"Half-life provenance: {radionuclide['half_life_provenance']['source_title']} — "
        f"{radionuclide['half_life_provenance']['source_value']}; "
        f"{radionuclide['half_life_provenance']['derivation']}.\n"
        f"Dose-rate provenance: {radionuclide['dose_rate_provenance']['source_title']} — "
        f"{radionuclide['dose_rate_provenance']['source_value']}; "
        f"{radionuclide['dose_rate_provenance']['derivation']}.\n"
        f"Attenuation dataset provenance: {dataset_text}\n"
        f"Replay verified: {'yes' if output['replay_verified'] else 'no'}\n"
        f"Displayed assumptions:\n{assumptions}\n"
        "Preview only: no project save or report output is enabled."
    )
