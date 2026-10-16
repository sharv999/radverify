from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

CTShieldingDatabase = None  # type: ignore
CT_DB_AVAILABLE = False

def conservative_default_ksec(kvp: int) -> float:
    defaults = {100: 4.0e-4, 120: 5.0e-4, 140: 6.0e-4}
    return defaults.get(int(kvp), 6.0e-4)

try:
    from DEV.OLD_ct_shielding_database_v2 import (
        CTShieldingDatabase as _CTDB_V2,
        conservative_default_ksec as _conservative_default_ksec_v2,
    )
    CTShieldingDatabase = _CTDB_V2  # type: ignore
    conservative_default_ksec = _conservative_default_ksec_v2  # type: ignore
    CT_DB_AVAILABLE = True
except Exception:
    try:
        from ct_shielding_database import (
            CTShieldingDatabase as _CTDB_V1,
            conservative_default_ksec as _conservative_default_ksec_v1,
        )
        CTShieldingDatabase = _CTDB_V1  # type: ignore
        conservative_default_ksec = _conservative_default_ksec_v1  # type: ignore
        CT_DB_AVAILABLE = True
    except Exception:
        pass

from models.shielding_models import Source, Barrier, Room, Project, DEFAULT_TVL_LIBRARY_MM_PB
from modalities.registry import (
    ct_scatter_dose_source_types,
    source_calculation_blocked_reason,
    source_contribution_group,
    source_default_tvl_key,
    source_dose_model_for_type,
    source_types_with_contribution_group,
    source_types_with_ncrp_solver_mode,
    xray_primary_source_types,
)

# Default area presets
AREA_PRESETS = {
    "Office": {"occupancy_factor": 1.0, "design_goal_uSv_per_week": 10.0},
    "Control Room": {"occupancy_factor": 1.0, "design_goal_uSv_per_week": 50.0},
    "Waiting Area": {"occupancy_factor": 0.5, "design_goal_uSv_per_week": 10.0},
    "Corridor": {"occupancy_factor": 0.2, "design_goal_uSv_per_week": 10.0},
    "Toilet": {"occupancy_factor": 0.05, "design_goal_uSv_per_week": 10.0},
    "Store": {"occupancy_factor": 0.05, "design_goal_uSv_per_week": 10.0},
    "Outdoor Area": {"occupancy_factor": 0.025, "design_goal_uSv_per_week": 10.0},
    "Controlled Area": {"occupancy_factor": 1.0, "design_goal_uSv_per_week": 50.0},
    "Clinical Area": {"occupancy_factor": 1.0, "design_goal_uSv_per_week": 10.0},
}


# Built-in source presets
CT_SCATTER_PRESETS = {
    "ct_low_dose": {
        "scatter_rate_uSv_h_at_1m": 1000.0,
        "beam_on_time_min_per_scan": 0.5,
        "scans_per_week": 60,
        "ksec_mGy_per_100mAs_at_1m": 0.0026,
        "workload_mAs_per_scan": 630,
        "tvl_key": "xray_140kvp",
    },
    "ct_routine_body": {
        "scatter_rate_uSv_h_at_1m": 1500.0,
        "beam_on_time_min_per_scan": 0.5,
        "scans_per_week": 100,
        "ksec_mGy_per_100mAs_at_1m": 0.0030,
        "workload_mAs_per_scan": 800,
        "tvl_key": "xray_140kvp",
    },
    "ct_cardiac": {
        "scatter_rate_uSv_h_at_1m": 1800.0,
        "beam_on_time_min_per_scan": 0.75,
        "scans_per_week": 80,
        "ksec_mGy_per_100mAs_at_1m": 0.0032,
        "workload_mAs_per_scan": 1000,
        "tvl_key": "xray_140kvp",
    },
}

XRAY_PRESETS = {
    "general_room": {
        "scatter_rate_uSv_h_at_1m": 500.0,
        "beam_on_time_s_per_exposure": 0.2,
        "exposures_per_exam": 2.0,
        "exams_per_week": 100,
        "tvl_key": "xray_120kvp",
    },
    "fluoroscopy_room": {
        "scatter_rate_uSv_h_at_1m": 2000.0,
        "beam_on_time_min_per_exam": 5.0,
        "exams_per_week": 40,
        "tvl_key": "xray_120kvp",
    },
    "mobile_c_arm": {
        "scatter_rate_uSv_h_at_1m": 1500.0,
        "beam_on_time_min_per_exam": 10.0,
        "exams_per_week": 20,
        "tvl_key": "xray_120kvp",
    },
}

XRAY_NCRP_SIMPLIFIED_PRESETS = {
    # NCRP Report No. 147 simplified general-radiography workload model.
    # Kerma values are per patient at 1 m and are converted to uSv-equivalent
    # numerically for the existing engine dose bookkeeping (1 mGy -> 1000 uSv).
    # The qualified pathway is barrier-specific: chest-bucky primary,
    # floor/other primary, and secondary (scatter + leakage).
    "general_radiography": {
        "default_kvp": 120,
        "primary_bucky_mGy_per_patient_at_1m": 2.3,
        "primary_floor_mGy_per_patient_at_1m": 5.2,
        "secondary_mGy_per_patient_at_1m": 0.034,
        "default_use_factor_primary_bucky_wall": 1.0,
        "default_use_factor_primary_floor": 0.89,
        "qualified": True,
        "note": "NCRP 147 simplified general-radiography barrier-specific workload model.",
    },
    # Retained in the UI for compatibility, but deliberately fail-closed until
    # an NCRP-qualified workload distribution is assigned and tested.
    "chest_room": {
        "default_kvp": 120,
        "qualified": False,
        "note": "Not yet qualified for NCRP 147 production calculation.",
    },
    "trauma_emergency": {
        "default_kvp": 120,
        "qualified": False,
        "note": "Not yet qualified for NCRP 147 production calculation.",
    },
}


DEFAULT_PATIENT_DOSE_CONSTANT_USV_H_PER_MBQ_AT_1M = {
    "Tc99m": 0.0206,
    "I131": 0.074,
    "F18": 0.092,
    "Ga68": 0.085,
}


SOLVER_MODE_MU = "mu"
SOLVER_MODE_NCRP = "ncrp"
SOLVER_MODE_AUTO = "auto"

SOLVER_MODE_OPTIONS = [
    SOLVER_MODE_AUTO,
    SOLVER_MODE_MU,
    SOLVER_MODE_NCRP,
]

CT_SCATTER_SOURCE_TYPES = tuple(ct_scatter_dose_source_types(production_only=False))
XRAY_PRIMARY_SOURCE_TYPES = tuple(xray_primary_source_types(production_only=False))
NCRP_CT_SECONDARY_SOURCE_TYPES = tuple(source_types_with_ncrp_solver_mode("ncrp_ct_secondary", production_only=False))

DEFAULT_NM_TCM99M_SOURCE_FACTORS = {
    "RMPS": 0.0206,
    "RBONE": 0.0125,
}

BUILDUP_COEFF = {
    "Pb": {
        "120 kVp": 0.05,
        "140 kVp": 0.05,
        "140 keV": 0.08,
        "511 keV": 0.15,
    },
    "Concrete": {
        "120 kVp": 0.10,
        "140 kVp": 0.10,
        "140 keV": 0.15,
        "511 keV": 0.30,
    },
    "Pb glass": {
        "120 kVp": 0.08,
        "140 kVp": 0.08,
        "140 keV": 0.12,
        "511 keV": 0.20,
    }
}



DEFAULT_TVL_LIBRARY_MM_PB: Dict[str, float] = {
    "xray_80kvp": 0.20,
    "xray_100kvp": 0.30,
    "xray_120kvp": 0.40,
    "xray_140kvp": 0.50,
    "tc99m_140kev": 0.90,
    "i131_364kev": 2.50,
    "f18_511kev": 5.00,
    "ga68_511kev": 5.00,
}

COMMERCIAL_LEAD_MM: List[float] = [0.0, 0.13, 0.25, 0.40, 0.50, 0.80, 1.00, 1.50, 2.00, 3.00, 5.00, 8.00, 10.00]

def round_up_to_commercial(mm: float) -> float:
    standards = [0.44, 0.88, 1.32, 1.76, 2.20, 2.64, 3.08, 3.52, 5.28, 7.04]
    for s in standards:
        if mm <= s:
            return s
    return standards[-1]


LEAD_MM_TO_KG_M2_TABLE: List[Tuple[float, float]] = [
    (0.44, 5.0),
    (0.88, 10.0),
    (1.32, 15.0),
    (1.76, 20.0),
    (2.20, 25.0),
    (2.64, 30.0),
    (3.08, 35.0),
    (3.52, 40.0),
    (5.28, 60.0),
    (7.04, 80.0),
    (10.56, 120.0),
    (14.08, 160.0),
    (17.60, 200.0),
    (20.0, 227.0),
    (30.0, 341.0),
    (50.0, 568.0),
]

EFFECTIVE_ENERGY_KEV = {
    "120 kVp": 60,
    "140 kVp": 70,
}

CT_SECONDARY_FIT_PARAMS = {
    "120 kVp": {
        "Pb": {"alpha": 2.246, "beta": 5.730, "gamma": 0.547},
        "Concrete": {"alpha": 3.830e-2, "beta": 1.420e-2, "gamma": 0.658},
    },
    "140 kVp": {
        "Pb": {"alpha": 2.009, "beta": 3.990, "gamma": 0.342},
        "Concrete": {"alpha": 3.360e-2, "beta": 1.220e-2, "gamma": 0.519},
    },
}

XRAY_NCRP147_ARCHER_PARAMS = {
    # NCRP Report No. 147, Table B.1: primary transmission fits for the
    # barrier-specific general-radiography workload distributions.
    "primary_bucky_wall": {
        "Pb": {"alpha": 2.264, "beta": 13.08, "gamma": 0.5600},
        "Concrete": {"alpha": 3.552e-2, "beta": 1.177e-1, "gamma": 0.6007},
    },
    "primary_floor": {
        "Pb": {"alpha": 2.651, "beta": 16.56, "gamma": 0.4585},
        "Concrete": {"alpha": 3.994e-2, "beta": 1.448e-1, "gamma": 0.4231},
    },
    # NCRP Report No. 147, Table C.1: secondary transmission fit for the
    # Rad Room (all barriers) workload distribution used for scatter+leakage.
    "secondary_wall": {
        "Pb": {"alpha": 2.298, "beta": 17.38, "gamma": 0.6193},
        "Concrete": {"alpha": 3.610e-2, "beta": 1.433e-1, "gamma": 0.5600},
    },
}


def _archer_required_thickness_mm(B_target: float, params: Dict[str, float]) -> float:
    """Invert the NCRP/Archer broad-beam transmission equation."""
    B = float(B_target)
    if B >= 1.0:
        return 0.0
    if B <= 0.0:
        raise ValueError("Required transmission B must be greater than zero.")
    alpha = float(params["alpha"])
    beta = float(params["beta"])
    gamma = float(params["gamma"])
    if alpha <= 0.0 or gamma <= 0.0:
        raise ValueError("Archer alpha and gamma must be positive.")
    return (1.0 / (alpha * gamma)) * math.log(
        ((B ** (-gamma)) + (beta / alpha)) / (1.0 + (beta / alpha))
    )


def _archer_transmission_from_thickness(thickness_mm: float, params: Dict[str, float]) -> float:
    """Forward NCRP/Archer broad-beam transmission equation."""
    x = max(0.0, float(thickness_mm))
    alpha = float(params["alpha"])
    beta = float(params["beta"])
    gamma = float(params["gamma"])
    if alpha <= 0.0 or gamma <= 0.0:
        raise ValueError("Archer alpha and gamma must be positive.")
    bracket = math.exp(alpha * gamma * x) * (1.0 + beta / alpha) - beta / alpha
    return min(max(bracket ** (-1.0 / gamma), 0.0), 1.0)


def xray_ncrp147_archer_params(barrier_role: str, material: str) -> Dict[str, float]:
    """Return qualified General Radiography NCRP 147 Archer coefficients.

    XR-02 intentionally qualifies Pb and concrete only. Other materials remain
    fail-closed until their NCRP 147 datasets receive separate KAT coverage.
    """
    role = str(barrier_role or "").strip().lower()
    material_text = str(material or "").strip()
    if material_text.startswith("Concrete"):
        family = "Concrete"
    elif material_text == "Pb" or material_text.startswith("Pb "):
        family = "Pb"
    else:
        family = material_text
    if role not in XRAY_NCRP147_ARCHER_PARAMS:
        raise ValueError(f"X-ray barrier role {barrier_role!r} is not qualified for NCRP 147 Archer transmission.")
    params = XRAY_NCRP147_ARCHER_PARAMS[role].get(family)
    if params is None:
        raise ValueError(f"X-ray material {material!r} is not yet qualified for NCRP 147 Archer transmission.")
    return dict(params)


def required_xray_ncrp147_thickness_mm(B_target: float, barrier_role: str, material: str) -> float:
    return _archer_required_thickness_mm(B_target, xray_ncrp147_archer_params(barrier_role, material))


def xray_ncrp147_transmission_from_thickness(thickness_mm: float, barrier_role: str, material: str) -> float:
    return _archer_transmission_from_thickness(
        thickness_mm, xray_ncrp147_archer_params(barrier_role, material)
    )


PRIMARY_TVL = {
    "120 kVp": {
        "Pb": {"TVL1_mm": 1.2, "TVLe_mm": 1.0},
        "Concrete": {"TVL1_mm": 60.0, "TVLe_mm": 55.0},
    },
    "140 kVp": {
        "Pb": {"TVL1_mm": 1.4, "TVLe_mm": 1.2},
        "Concrete": {"TVL1_mm": 70.0, "TVLe_mm": 60.0},
    },
}



# Buildup factor
def buildup_factor(material: str, energy: str, mu: float, thickness_mm: float) -> float:
    a = BUILDUP_COEFF.get(material, {}).get(energy, 0.1)
    mfp = mu * (thickness_mm / 10.0)  # mm → cm

    # Step 4: cap buildup to prevent runaway values
    return min(math.exp(a * mfp), 50.0)


def required_ct_secondary_thickness_mm(B_target: float, material: str, energy_label: str) -> float:
    """
    NCRP 147-style CT secondary broad-beam fit:

        x = 1 / (alpha * gamma) * ln( (B^(-gamma) + beta/alpha) / (1 + beta/alpha) )

    Parameters are material- and kVp-specific. Thickness output is in mm.
    """
    params = CT_SECONDARY_FIT_PARAMS.get(str(energy_label), {}).get(str(material))
    if not params:
        return 0.0
    if B_target >= 1.0:
        return 0.0
    alpha = float(params["alpha"])
    beta = float(params["beta"])
    gamma = float(params["gamma"])
    if alpha <= 0 or gamma <= 0:
        return 0.0
    term_num = (B_target ** (-gamma)) + (beta / alpha)
    term_den = 1.0 + (beta / alpha)
    if term_num <= 0 or term_den <= 0:
        return 0.0
    return (1.0 / (alpha * gamma)) * math.log(term_num / term_den)


def primary_barrier_transmission(P_uSv_per_week: float,
                                 W_uSv_per_week_at_1m: float,
                                 U: float,
                                 T: float,
                                 distance_m: float) -> float:
    """
    NCRP-style primary barrier transmission factor:
        B = P * d^2 / (W * U * T)
    where W is expressed as weekly primary dose-equivalent at 1 m.
    """
    if W_uSv_per_week_at_1m <= 0 or U <= 0 or T <= 0 or distance_m <= 0:
        return 1.0
    return (P_uSv_per_week * (distance_m ** 2)) / (W_uSv_per_week_at_1m * U * T)


def primary_transmission_from_thickness(thickness_mm: float,
                                      material: str,
                                      energy_label: str) -> float:
    """
    Forward broad-beam transmission from thickness using TVL1/TVLe.

    This is the inverse of required_primary_thickness_from_tvl().
    """
    family, _ = parse_material_option(material)
    params = PRIMARY_TVL.get(str(energy_label), {}).get(family)
    if not params:
        return 1.0

    tvl1 = float(params["TVL1_mm"])
    tvle = float(params["TVLe_mm"])
    x = max(0.0, float(thickness_mm))

    if tvl1 <= 0 or tvle <= 0:
        return 1.0

    if x <= tvl1:
        return 10 ** (-(x / tvl1))

    return 10 ** (-(1.0 + ((x - tvl1) / tvle)))


def required_primary_thickness_from_tvl(B_target: float,
                                        material: str,
                                        energy_label: str) -> float:
    """
    Primary barrier thickness using true TVL interpolation.

    This uses the standard NCRP broad-beam two-TVL model:
      - TVL1 for the first tenth-value layer
      - TVLe for all subsequent decade reductions

    For a required transmission B:
        n = -log10(B)

    then:
        x = n * TVL1                      for n <= 1
        x = TVL1 + (n - 1) * TVLe         for n > 1

    This preserves fractional-decade interpolation exactly, rather than
    rounding to whole TVLs.
    """
    if B_target >= 1.0:
        return 0.0

    family, _ = parse_material_option(material)
    params = PRIMARY_TVL.get(str(energy_label), {}).get(family)
    if not params:
        return 0.0

    tvl1 = float(params["TVL1_mm"])
    tvle = float(params["TVLe_mm"])

    if tvl1 <= 0 or tvle <= 0 or B_target <= 0:
        return 0.0

    n_tvl = -math.log10(B_target)

    first_decade = min(n_tvl, 1.0)
    remaining_decades = max(0.0, n_tvl - 1.0)

    thickness_mm = (first_decade * tvl1) + (remaining_decades * tvle)
    return thickness_mm


def required_thickness_with_buildup(B_target: float, mu: float, material: str, energy: str) -> float:
    """
    Solve: B_target = buildup(x) * exp(-mu x)

    using simple iterative search (robust + fast for UI)
    """

    if mu <= 0:
        return 0.0

    if B_target >= 1.0:
        return 0.0

    x_mm = 0.0
    step = 0.5  # mm resolution

    for _ in range(2000):  # up to 1000 mm
        buildup = buildup_factor(material, energy, mu, x_mm)
        transmission = buildup * math.exp(-mu * (x_mm / 10.0))

        if transmission <= B_target:
            return x_mm

        x_mm += step

    return x_mm  # fallback


def actual_transmission_from_thickness_with_buildup(
    thickness_mm: float,
    mu_cm_inv: float,
    material: str,
    energy_label: str,
) -> float:
    """
    Forward broad-beam transmission for the actual installed thickness using
    the same mu + buildup pathway as required_thickness_with_buildup().
    """
    if mu_cm_inv <= 0:
        return 1.0

    x_mm = max(0.0, float(thickness_mm))
    buildup = buildup_factor(material, energy_label, mu_cm_inv, x_mm)
    transmission = buildup * math.exp(-mu_cm_inv * (x_mm / 10.0))
    return min(max(transmission, 0.0), 1.0)


def actual_ct_secondary_transmission_from_thickness(
    thickness_mm: float,
    material: str,
    energy_label: str,
) -> float:
    """
    Forward NCRP-147-style CT secondary broad-beam transmission using the same
    fit family already used for required_ct_secondary_thickness_mm().

    Inverse of:
        x = 1 / (alpha * gamma) * ln( (B^(-gamma) + beta/alpha) / (1 + beta/alpha) )

    Rearranged to:
        B = [ exp(alpha * gamma * x) * (1 + beta/alpha) - beta/alpha ]^(-1/gamma)
    """
    params = CT_SECONDARY_FIT_PARAMS.get(str(energy_label), {}).get(str(material))
    if not params:
        return 1.0

    alpha = float(params["alpha"])
    beta = float(params["beta"])
    gamma = float(params["gamma"])
    x_mm = max(0.0, float(thickness_mm))

    if alpha <= 0 or gamma <= 0:
        return 1.0

    bracket = math.exp(alpha * gamma * x_mm) * (1.0 + (beta / alpha)) - (beta / alpha)
    if bracket <= 0:
        return 1.0

    B = bracket ** (-1.0 / gamma)
    return min(max(B, 0.0), 1.0)


def lead_mm_to_kg_m2(thickness_mm: float) -> float:
    if thickness_mm <= 0:
        return 0.0
    for mm, kg_m2 in LEAD_MM_TO_KG_M2_TABLE:
        if abs(thickness_mm - mm) < 1e-9:
            return kg_m2
    return round(thickness_mm * 11.34, 1)


MATERIAL_OPTIONS = [
    "Pb 0.44 mm (5 kg/m2)",
    "Pb 0.88 mm (10 kg/m2)",
    "Pb 1.32 mm (15 kg/m2)",
    "Pb 1.76 mm (20 kg/m2)",
    "Pb 2.20 mm (25 kg/m2)",
    "Pb 2.64 mm (30 kg/m2)",
    "Pb 3.08 mm (35 kg/m2)",
    "Pb 3.52 mm (40 kg/m2)",
    "Pb 5.28 mm (60 kg/m2)",
    "Pb 7.04 mm (80 kg/m2)",
    "Pb glass 2.20 mm",
    "Concrete 150 mm",
    "Concrete 190 mm",
]

ENERGY_OPTIONS = ["120 kVp", "140 kVp", "140 keV", "511 keV"]

MATERIAL_LAC_BY_ENERGY: Dict[str, Dict[str, float]] = {
    "Pb": {
        "120 kVp": 65.0,
        "140 kVp": 50.0,
        "140 keV": 22.9,
        "511 keV": 1.64,
    },
    "Concrete": {
        "120 kVp": 0.45,
        "140 kVp": 0.38,
        "140 keV": 0.339,
        "511 keV": 0.21,
    },
    "Pb glass": {
        "120 kVp": 25.0,
        "140 kVp": 18.0,
        "140 keV": 6.7,
        "511 keV": 0.623,
    },
}

def _qualified_xray_ncrp_preset(exam_room_type: str) -> Dict[str, Any]:
    preset = XRAY_NCRP_SIMPLIFIED_PRESETS.get(exam_room_type)
    if not preset or not bool(preset.get("qualified", False)):
        raise ValueError(
            f"X-ray NCRP simplified room type '{exam_room_type}' is not yet qualified; "
            "calculation remains fail-closed."
        )
    return preset


def compute_xray_ncrp_simplified_source_summary(params: Dict[str, Any]) -> Dict[str, Any]:
    exam_room_type = str(params.get("exam_room_type", "general_radiography")).strip() or "general_radiography"
    exams_per_week = float(params.get("exams_per_week", 0.0) or 0.0)
    tube_potential_kvp = int(float(params.get("tube_potential_kvp", 120) or 120))
    preset = _qualified_xray_ncrp_preset(exam_room_type)

    bucky = exams_per_week * float(preset["primary_bucky_mGy_per_patient_at_1m"]) * 1000.0
    floor = exams_per_week * float(preset["primary_floor_mGy_per_patient_at_1m"]) * 1000.0
    secondary = exams_per_week * float(preset["secondary_mGy_per_patient_at_1m"]) * 1000.0

    return {
        "exam_room_type": exam_room_type,
        "exams_per_week": exams_per_week,
        "tube_potential_kvp": tube_potential_kvp,
        # Compatibility preview only. Actual calculation is barrier-specific.
        "derived_workload_uSv_per_week_at_1m": floor,
        "derived_use_factor_default": float(preset["default_use_factor_primary_floor"]),
        "primary_bucky_workload_uSv_per_week_at_1m": bucky,
        "primary_floor_workload_uSv_per_week_at_1m": floor,
        "secondary_workload_uSv_per_week_at_1m": secondary,
        "note": str(preset["note"]),
    }


def get_xray_barrier_role_defaults(exam_room_type: str, barrier_role: str) -> Dict[str, Any]:
    preset = _qualified_xray_ncrp_preset(exam_room_type)
    if barrier_role == "primary_bucky_wall":
        return {"is_primary": True, "use_factor": float(preset["default_use_factor_primary_bucky_wall"]), "role_note": "Primary bucky wall"}
    if barrier_role == "primary_floor":
        return {"is_primary": True, "use_factor": float(preset["default_use_factor_primary_floor"]), "role_note": "Primary floor"}
    return {"is_primary": False, "use_factor": 1.0, "role_note": barrier_role or "secondary_wall"}


def get_xray_primary_workload_and_use_factor(source: Source, barrier: Barrier) -> Dict[str, Any]:
    params = getattr(source, "params", {}) or {}
    method = str(params.get("xray_method", "manual")).strip() or "manual"
    barrier_role = str(getattr(barrier, "barrier_role", "secondary_wall")).strip() or "secondary_wall"

    if method == "ncrp_simplified":
        summary = compute_xray_ncrp_simplified_source_summary(params)
        role_defaults = get_xray_barrier_role_defaults(summary["exam_room_type"], barrier_role)
        workload_key = {
            "primary_bucky_wall": "primary_bucky_workload_uSv_per_week_at_1m",
            "primary_floor": "primary_floor_workload_uSv_per_week_at_1m",
        }.get(barrier_role, "secondary_workload_uSv_per_week_at_1m")
        return {
            "method": "ncrp_simplified",
            "is_primary": bool(role_defaults["is_primary"]),
            "workload_uSv_per_week_at_1m": float(summary[workload_key]),
            "use_factor": float(role_defaults["use_factor"]),
            "exam_room_type": summary["exam_room_type"],
            "barrier_role": barrier_role,
            "note": f"{summary['note']} | {role_defaults['role_note']}",
        }

    return {
        "method": "manual",
        "is_primary": barrier_role in {"primary_bucky_wall", "primary_floor"},
        "workload_uSv_per_week_at_1m": float(params.get("workload_uSv_per_week_at_1m", 0.0) or 0.0),
        "use_factor": float(params.get("use_factor", 0.25) or 0.25),
        "exam_room_type": "",
        "barrier_role": barrier_role,
        "note": "Manual X-ray workload mode",
    }


def parse_material_option(material_option: str) -> tuple[str, float]:
    text = str(material_option).strip()
    if text in ("Pb", "Concrete", "Pb glass"):
        defaults = {"Pb": 0.88, "Concrete": 150.0, "Pb glass": 2.20}
        return text, defaults[text]
    if text.startswith("Pb glass"):
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*mm', text)
        return "Pb glass", float(m.group(1)) if m else 2.20
    if text.startswith("Concrete"):
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*mm', text)
        return "Concrete", float(m.group(1)) if m else 150.0
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*mm', text)
    if text.startswith("Pb") and m:
        return "Pb", float(m.group(1))
    return "Pb", 0.88



def normalize_ct_ksec_mGy_per_100mAs(raw_ksec: Any, kvp: int = 140) -> float:
    """
    Canonical CT Ksec unit used by the physics engine:
        mGy / 100 mAs at 1 m radial distance

    IMPORTANT: this function deliberately does *not* infer scatter-rate,
    beam-time, matrix, contour, or legacy direction-specific values. CT
    secondary workload is consumed only as Ksec.

    Blank/invalid values fall back to the conservative default Ksec.
    """
    default_ksec = float(conservative_default_ksec(kvp))

    if raw_ksec in (None, ""):
        return default_ksec

    try:
        value = float(raw_ksec)
    except Exception:
        return default_ksec

    if value <= 0:
        return default_ksec

    # Treat the supplied value as already canonical mGy / 100 mAs at 1 m.
    # Do not auto-scale small values: several validated scanner records are
    # legitimately in the 0.001-0.01 mGy/100mAs range.
    return value


def _ct_ksec_from_params(params: Dict[str, Any], kvp: int) -> Tuple[float, str]:
    """
    Resolve canonical CT Ksec from source params only.

    For scanner-database workflows, a selected scanner with blank/NULL ksec is
    not allowed to fall back to a preset or conservative default. That condition
    must be resolved by entering a documented manual override.
    """
    explicit_keys = (
        "ksec_mGy_per_100mAs_at_1m",
        "worst_case_ksec_mGy_per_100mAs_at_1m",
        "ct_ksec_mGy_per_100mAs_at_1m",
    )

    scanner_family = str(params.get("scanner_family", "") or "").strip()
    use_scanner_db = str(params.get("use_scanner_db", "1") or "1").strip() == "1"
    manual_override = str(params.get("manual_ksec_override", "0") or "0").strip() == "1"

    for key in explicit_keys:
        if key in params and params.get(key) not in (None, "", "NULL", "null", "None"):
            ksec = normalize_ct_ksec_mGy_per_100mAs(params.get(key), kvp)
            if ksec > 0:
                return ksec, key

    if scanner_family and use_scanner_db and not manual_override:
        raise ValueError(
            "CT scanner ksec is NULL/missing. Enter a manual ksec override "
            f"or select a scanner with database ksec before calculating ({scanner_family})."
        )

    preset_name = str(params.get("preset", "") or "")
    if preset_name in CT_SCATTER_PRESETS:
        preset = CT_SCATTER_PRESETS[preset_name]
        if "ksec_mGy_per_100mAs_at_1m" in preset:
            return normalize_ct_ksec_mGy_per_100mAs(
                preset.get("ksec_mGy_per_100mAs_at_1m"), kvp
            ), f"preset:{preset_name}.ksec_mGy_per_100mAs_at_1m"

    return normalize_ct_ksec_mGy_per_100mAs(None, kvp), "conservative_default_ksec"


def compute_ct_weekly_dose_uSv_at_1m_from_ksec(
    ksec_mGy_per_100mAs_at_1m: float,
    workload_mAs_per_scan: float,
    scans_per_week: float,
) -> float:
    """
    CT / SPECT-CT secondary scatter weekly unshielded dose at 1 m.

    Ksec is canonicalized as mGy / 100 mAs at 1 m, so:
        weekly_mGy = Ksec * (mAs/scan / 100) * scans/week
        weekly_uSv = weekly_mGy * 1000
    """
    ksec = max(0.0, float(ksec_mGy_per_100mAs_at_1m))
    workload = max(0.0, float(workload_mAs_per_scan))
    scans = max(0.0, float(scans_per_week))
    weekly_mGy = ksec * (workload / 100.0) * scans
    return weekly_mGy * 1000.0


def required_transmission_factor_from_weekly_dose(
    design_goal_uSv_per_week: float,
    occupancy_factor: float,
    unshielded_weekly_dose_uSv: float,
) -> float:
    """
    Required broad-beam transmission for secondary/patient barriers:
        B = P / (T * D_unshielded)
    """
    P = float(design_goal_uSv_per_week)
    T = float(occupancy_factor)
    D = float(unshielded_weekly_dose_uSv)
    if P <= 0 or T <= 0 or D <= 0:
        return 1.0
    return P / (T * D)


def transmitted_weekly_dose_uSv(
    unshielded_weekly_dose_uSv: float,
    occupancy_factor: float,
    transmission_factor_B: float,
    use_factor: float = 1.0,
) -> float:
    D = max(0.0, float(unshielded_weekly_dose_uSv))
    T = max(0.0, float(occupancy_factor))
    U = max(0.0, float(use_factor))
    B = min(max(float(transmission_factor_B), 0.0), 1.0)
    return D * T * U * B


def dominant_contribution_name(contributions: List[Tuple[str, float, str]]) -> str:
    if not contributions:
        return ""
    try:
        return max(contributions, key=lambda x: float(x[1]))[0]
    except Exception:
        return contributions[0][0]

def get_barrier_material_family(barrier: Barrier) -> str:
    raw = str(getattr(barrier, "material", "") or "").strip()
    if raw in {"Pb", "Concrete", "Pb glass"}:
        return raw
    family, _ = parse_material_option(str(getattr(barrier, "material_legacy", "") or raw))
    return family


def get_barrier_actual_thickness_mm(barrier: Barrier) -> float:
    try:
        value = float(getattr(barrier, "thickness_mm", 0.0) or 0.0)
        if value > 0:
            return value
    except Exception:
        pass
    _, thickness = parse_material_option(str(getattr(barrier, "material_legacy", "") or getattr(barrier, "material", "")))
    return float(thickness)

#def material_linear_attenuation_coefficient_cm_inv(material_option: str, energy_label: str) -> float:
#    material_family, _ = parse_material_option(material_option)
#    return MATERIAL_LAC_BY_ENERGY.get(material_family, {}).get(str(energy_label), 0.0)

def material_linear_attenuation_coefficient_cm_inv(material_option: str, energy_label: str) -> float:
    material_family, _ = parse_material_option(material_option)

    if energy_label in ("120 kVp", "140 kVp"):
        # map to closest available data (100 keV or 140 keV)
        if energy_label == "120 kVp":
            ref = "120 kVp"
        else:
            ref = "140 kVp"
        return MATERIAL_LAC_BY_ENERGY.get(material_family, {}).get(ref, 0.0)

    return MATERIAL_LAC_BY_ENERGY.get(material_family, {}).get(str(energy_label), 0.0)


def _manual_source_weekly_dose_at_1m(params: Dict[str, Any]) -> float:
    return float(params["dose_rate_uSv_h_at_1m"]) * float(params["hours_per_week"])


def _ct_scatter_weekly_dose_at_1m(params: Dict[str, Any]) -> Tuple[float, str]:
    """
    CT / SPECT-CT secondary scatter workload pathway.

    The physics engine consumes CT scatter only via canonical Ksec
    (mGy / 100 mAs at 1 m) plus workload mAs/scan and scans/week. It does
    not use scatter_rate_uSv_h_at_1m, beam-on time, contour data, matrix
    profile values, or scanner DB geometry in the calculation.
    """
    kvp_raw = params.get("scanner_kvp", params.get("kvp", 140))
    try:
        kvp = int(float(kvp_raw))
    except Exception:
        kvp = 140

    preset_name = str(params.get("preset", "") or "")
    if preset_name in CT_SCATTER_PRESETS:
        merged = dict(CT_SCATTER_PRESETS[preset_name])
        merged.update(params)  # explicit source params override preset values
        params = merged

    ksec, _ksec_source = _ct_ksec_from_params(params, kvp)
    workload = float(params.get("workload_mAs_per_scan", 0.0) or 0.0)
    scans_per_week = float(params.get("scans_per_week", 0.0) or 0.0)

    weekly_uSv = compute_ct_weekly_dose_uSv_at_1m_from_ksec(
        ksec,
        workload,
        scans_per_week,
    )
    return weekly_uSv, str(params.get("tvl_key", "xray_140kvp"))


def _general_xray_weekly_dose_at_1m(params: Dict[str, Any]) -> Tuple[float, str]:
    preset_name = params.get("preset", "")
    if preset_name in XRAY_PRESETS:
        merged = dict(XRAY_PRESETS[preset_name])
        merged.update(params)
        params = merged
    scatter_rate = float(params["scatter_rate_uSv_h_at_1m"])
    exams_per_week = float(params["exams_per_week"])
    if "beam_on_time_min_per_exam" in params:
        beam_time_h_per_exam = float(params["beam_on_time_min_per_exam"]) / 60.0
    else:
        beam_time_h_per_exam = (float(params.get("beam_on_time_s_per_exposure", 0.2)) * float(params.get("exposures_per_exam", 1.0))) / 3600.0
    return scatter_rate * beam_time_h_per_exam * exams_per_week, str(params.get("tvl_key", "xray_120kvp"))


def _nm_patient_weekly_dose_at_1m(params: Dict[str, Any], patient_constants: Dict[str, float]) -> float:
    if all(k in params for k in ("NMPS_R", "NMPS_S", "NBONE", "AMPS_R", "AMPS_S", "ABONE", "tMPS_R", "tMPS_S", "tBONE")):
        temp_source = Source(name="NM", source_type="nm_patient", radiation_type="tc99m_140kev", params=params)
        return compute_nm_source_summary(temp_source)["dscint_uSv_per_week_at_1m"]

    if "dscint_mSv_per_week_at_1m" in params:
        return float(params["dscint_mSv_per_week_at_1m"]) * 1000.0

    radionuclide = str(params["radionuclide"])
    constant = float(patient_constants[radionuclide])
    injected_activity_mbq = float(params["injected_activity_mbq"])
    patients_per_week = float(params["patients_per_week"])
    source_hours_per_patient = float(params.get("source_hours_per_patient", 1.0))
    retention_factor = float(params.get("retention_factor", 1.0))
    dose_rate_at_1m = constant * injected_activity_mbq * retention_factor
    return dose_rate_at_1m * source_hours_per_patient * patients_per_week





def compute_source_weekly_dose_at_1m(source: Source, patient_constants: Dict[str, float]) -> Tuple[float, str]:
    blocked_reason = source_calculation_blocked_reason(source.source_type)
    if blocked_reason:
        raise ValueError(blocked_reason)
    dose_model = source_dose_model_for_type(source.source_type)
    if source.source_type == "manual":
        return _manual_source_weekly_dose_at_1m(source.params), source.radiation_type
    if dose_model == "xray_primary":
        method = str(source.params.get("xray_method", "manual")).strip() or "manual"
        if method == "ncrp_simplified":
            summary = compute_xray_ncrp_simplified_source_summary(source.params)
            return float(summary["derived_workload_uSv_per_week_at_1m"]), source.radiation_type
        return float(source.params.get("workload_uSv_per_week_at_1m", 0.0)), source.radiation_type
    if dose_model == "ct_ksec_weekly_dose":
        return _ct_scatter_weekly_dose_at_1m(source.params)
    if source.source_type == "general_xray":
        return _general_xray_weekly_dose_at_1m(source.params)
    if source.source_type == "nm_workload":
        return float(source.params.get("dscint_mSv_per_week_at_1m", 0.0)) * 1000.0, source.radiation_type
    if source.source_type == "nm_patient":
        return _nm_patient_weekly_dose_at_1m(source.params, patient_constants), source.radiation_type
    raise ValueError(f"Unsupported source_type '{source.source_type}'")


def compute_ct_source_summary(source: Source) -> Dict[str, float]:
    p = source.params
    kvp_raw = p.get("scanner_kvp", p.get("kvp", 140))
    try:
        kvp = int(float(kvp_raw))
    except Exception:
        kvp = 140

    preset_name = str(p.get("preset", "") or "")
    if preset_name in CT_SCATTER_PRESETS:
        merged = dict(CT_SCATTER_PRESETS[preset_name])
        merged.update(p)
        p = merged

    ksec, ksec_source = _ct_ksec_from_params(p, kvp)
    workload = float(p.get("workload_mAs_per_scan", 0.0))
    scans_per_week = float(p.get("scans_per_week", 0.0))
    weekly_uSv = compute_ct_weekly_dose_uSv_at_1m_from_ksec(ksec, workload, scans_per_week)
    k1sec = weekly_uSv / 1000.0
    return {
        "ksec_mGy_per_100mAs_at_1m": ksec,
        "ksec_source": ksec_source,
        "workload_mAs_per_scan": workload,
        "scans_per_week": scans_per_week,
        "weekly_mAs": workload * scans_per_week,
        "weekly_dose_uSv_at_1m": weekly_uSv,
        "k1sec_mGy_per_week": k1sec,
        "total_ct_dose_mGy_per_week_at_1m": k1sec,
    }


def auto_select_tvl_key(source_type: str, params: Dict[str, Any], radiation_type: str = "") -> str:
    """
    Minimal TVL key auto-selection used by the Sources tab.
    """
    registry_default = source_default_tvl_key(source_type)
    if registry_default:
        return registry_default
    if source_type == "general_xray":
        return "xray_120kvp"
    if source_type in ("nm_workload", "nm_patient"):
        radionuclide = str(params.get("radionuclide", "")).strip()
        if radionuclide == "Tc99m":
            return "tc99m_140kev"
        if radionuclide in ("F18", "Ga68"):
            return "f18_511kev"
        return "tc99m_140kev"
    return radiation_type.strip() or "xray_120kvp"


def compute_nm_source_summary(source: Source) -> Dict[str, float]:
    p = source.params
    nmps_r = int(float(p.get("NMPS_R", 20)))
    nmps_s = int(float(p.get("NMPS_S", 20)))
    nbone = int(float(p.get("NBONE", 40)))
    amps_r = int(float(p.get("AMPS_R", 350)))
    amps_s = int(float(p.get("AMPS_S", 1000)))
    abone = int(float(p.get("ABONE", 1000)))
    tmps_r = float(p.get("tMPS_R", 0.33))
    tmps_s = float(p.get("tMPS_S", 0.33))
    tbone = float(p.get("tBONE", 1.0))
    rmps = float(p.get("RMPS", DEFAULT_NM_TCM99M_SOURCE_FACTORS["RMPS"]))
    rbone = float(p.get("RBONE", DEFAULT_NM_TCM99M_SOURCE_FACTORS["RBONE"]))

    dscint_uSv = (
        (amps_r * nmps_r * rmps * tmps_r)
        + (amps_s * nmps_s * rmps * tmps_s)
        + (abone * nbone * rbone * tbone)
    )
    dscint_mSv = dscint_uSv / 1000.0

    return {
        "NMPS_R": nmps_r,
        "NMPS_S": nmps_s,
        "NBONE": nbone,
        "AMPS_R": amps_r,
        "AMPS_S": amps_s,
        "ABONE": abone,
        "tMPS_R": tmps_r,
        "tMPS_S": tmps_s,
        "tBONE": tbone,
        "RMPS": rmps,
        "RBONE": rbone,
        "dscint_uSv_per_week_at_1m": dscint_uSv,
        "dscint_mSv_per_week_at_1m": dscint_mSv,
    }


def compute_room_source_summary(room: Room) -> Dict[str, float]:
    total_ct_mGy_per_week = 0.0
    total_nm_mSv_per_week = 0.0
    for src in room.sources:
        if source_dose_model_for_type(src.source_type) == "ct_ksec_weekly_dose":
            s = compute_ct_source_summary(src)
            total_ct_mGy_per_week += s["total_ct_dose_mGy_per_week_at_1m"]
        elif src.source_type == "nm_workload":
            weekly_uSv, _ = compute_source_weekly_dose_at_1m(src, dict(DEFAULT_PATIENT_DOSE_CONSTANT_USV_H_PER_MBQ_AT_1M))
            total_nm_mSv_per_week += weekly_uSv / 1000.0
        elif src.source_type == "nm_patient":
            s = compute_nm_source_summary(src)
            total_nm_mSv_per_week += s["dscint_mSv_per_week_at_1m"]

    dspect_ct_mSv_per_week = total_nm_mSv_per_week + (total_ct_mGy_per_week / 1000.0)

    return {
        "total_ct_dose_mGy_per_week_at_1m": total_ct_mGy_per_week,
        "total_nm_dscint_mSv_per_week_at_1m": total_nm_mSv_per_week,
        "dspect_ct_mSv_per_week_at_1m": dspect_ct_mSv_per_week,
    }


def compute_unshielded_weekly_dose_at_barrier(room: Room, barrier: Barrier, project: Project) -> Tuple[float, List[Tuple[str, float, str]]]:
    if barrier.distance_m <= 0:
        raise ValueError(f"Barrier '{barrier.name}' has invalid distance_m <= 0")
    total = 0.0
    contributions: List[Tuple[str, float, str]] = []
    for src in room.sources:
        # XR-03 qualified barrier-aware NCRP 147 path; generic X-ray source-dose remains blocked.
        if src.source_type == "xray_primary" and str(src.params.get("xray_method", "")).strip() == "ncrp_simplified":
            xray_ctx = get_xray_primary_workload_and_use_factor(src, barrier)
            weekly_dose_1m = float(xray_ctx["workload_uSv_per_week_at_1m"])
            use_factor = float(xray_ctx["use_factor"]) if xray_ctx["is_primary"] else 1.0
            barrier_dose = weekly_dose_1m * use_factor / (barrier.distance_m ** 2)
            total += barrier_dose
            contributions.append((src.name, barrier_dose, "NCRP 147 General Radiography"))
            continue
        weekly_dose_1m, tvl_key = compute_source_weekly_dose_at_1m(src, project.patient_dose_constants)
        # Distance-corrected
        barrier_dose = weekly_dose_1m / (barrier.distance_m ** 2)
        total += barrier_dose
        contributions.append((src.name, barrier_dose, tvl_key))
    return total, contributions

def select_solver_mode(
    room: Room,
    barrier: Barrier,
    energy_label: str,
    solver_mode: str = SOLVER_MODE_AUTO,
) -> str:
    family = get_barrier_material_family(barrier)

    barrier_role = str(getattr(barrier, "barrier_role", "secondary_wall") or "secondary_wall").strip()
    is_xray_primary_barrier = barrier_role in {"primary_bucky_wall", "primary_floor"}

    has_primary_source = any(src.source_type in XRAY_PRIMARY_SOURCE_TYPES for src in room.sources)
    has_qualified_xray_source = any(
        src.source_type == "xray_primary" and str(src.params.get("xray_method", "")).strip() == "ncrp_simplified"
        for src in room.sources
    )
    has_ct_source = any(src.source_type in NCRP_CT_SECONDARY_SOURCE_TYPES for src in room.sources)
    ncrp_energy = energy_label in ("120 kVp", "140 kVp")
    ncrp_material = family in ("Pb", "Concrete")
    if solver_mode == SOLVER_MODE_MU:
        return SOLVER_MODE_MU

    if solver_mode == SOLVER_MODE_NCRP:
        if has_qualified_xray_source and barrier_role in XRAY_NCRP147_ARCHER_PARAMS and ncrp_material:
            return "ncrp_xray_147"
        if has_primary_source and is_xray_primary_barrier and ncrp_material and ncrp_energy:
            return "ncrp_primary"
        if has_ct_source and ncrp_material and ncrp_energy:
            return "ncrp_ct_secondary"
        return SOLVER_MODE_MU

    if has_qualified_xray_source and barrier_role in XRAY_NCRP147_ARCHER_PARAMS and ncrp_material:
        return "ncrp_xray_147"
    if has_primary_source and is_xray_primary_barrier and ncrp_material and ncrp_energy:
        return "ncrp_primary"
    if has_ct_source and ncrp_material and ncrp_energy:
        return "ncrp_ct_secondary"
    return SOLVER_MODE_MU

def compute_unshielded_component_doses_at_barrier(
    room: Room,
    barrier: Barrier,
    project: Project,
) -> Dict[str, Any]:
    if barrier.distance_m <= 0:
        raise ValueError(f"Barrier '{barrier.name}' has invalid distance_m <= 0")
    result = {
        "ct_scatter_uSv_wk": 0.0,
        "other_uSv_wk": 0.0,
        "total_uSv_wk": 0.0,
        "contributions": [],
    }
    for src in room.sources:
        weekly_dose_1m, tvl_key = compute_source_weekly_dose_at_1m(src, project.patient_dose_constants)
        barrier_dose = weekly_dose_1m / (barrier.distance_m ** 2)
        if source_dose_model_for_type(src.source_type) == "ct_ksec_weekly_dose":
            result["ct_scatter_uSv_wk"] += barrier_dose
        else:
            result["other_uSv_wk"] += barrier_dose
        result["contributions"].append({
            "source_name": src.name,
            "source_type": src.source_type,
            "weekly_dose_at_barrier_uSv": barrier_dose,
            "tvl_key": tvl_key,
        })
    result["total_uSv_wk"] = result["ct_scatter_uSv_wk"] + result["other_uSv_wk"]
    return result


def compute_ct_required_thickness_mm_for_barrier(
    room: Room,
    barrier: Barrier,
    project: Project,
    ct_energy_label: str,
    solver_mode: str = SOLVER_MODE_AUTO,
) -> Dict[str, Any]:
    P = float(barrier.design_goal_uSv_per_week)
    T = float(barrier.occupancy_factor)
    family = get_barrier_material_family(barrier)
    comp = compute_unshielded_component_doses_at_barrier(room, barrier, project)
    D_ct = comp["ct_scatter_uSv_wk"]
    if D_ct <= 0 or T <= 0:
        return {"ct_unshielded_uSv_wk": D_ct, "ct_B": 1.0, "ct_required_mm": 0.0, "ct_solver_used": None}
    B_ct = required_transmission_factor_from_weekly_dose(P, T, D_ct)
    selected_solver = select_solver_mode(Room(room.name, room.modality, [s for s in room.sources if source_contribution_group(s.source_type) == "ct_scatter"], room.barriers), barrier, ct_energy_label, solver_mode)
    if selected_solver == "ncrp_ct_secondary" and family in ("Pb", "Concrete"):
        required_mm = required_ct_secondary_thickness_mm(B_ct, family, ct_energy_label)
        solver_used = "ncrp_ct_secondary_fit"
    else:
        mu_cm_inv = material_linear_attenuation_coefficient_cm_inv(barrier.material, ct_energy_label)
        required_mm = required_thickness_with_buildup(B_ct, mu_cm_inv, family, ct_energy_label)
        solver_used = f"mu_plus_buildup_{ct_energy_label}"
    return {"ct_unshielded_uSv_wk": D_ct, "ct_B": B_ct, "ct_required_mm": required_mm, "ct_solver_used": solver_used}


def calc_barrier_result(
    room: Room,
    barrier: Barrier,
    project: Project,
    energy_label: str,
    solver_mode: str = SOLVER_MODE_AUTO,
) -> Dict[str, Any]:
    total_unshielded_uSv_week, contributions = compute_unshielded_weekly_dose_at_barrier(room, barrier, project)
    P = float(barrier.design_goal_uSv_per_week)
    T = float(barrier.occupancy_factor)

    family = get_barrier_material_family(barrier)
    existing_thickness_mm = get_barrier_actual_thickness_mm(barrier)
    mu_cm_inv = material_linear_attenuation_coefficient_cm_inv(barrier.material, energy_label)

    # Current supported physics:
    # - CT secondary
    # - X-ray primary
    # - Generic buildup / attenuation

    selected_solver = select_solver_mode(room, barrier, energy_label, solver_mode)
    B = 1.0
    actual_B = 1.0
    transmitted_dose_uSv_per_week = 0.0

    if selected_solver == "ncrp_xray_147":
        xray_src = next(src for src in room.sources if src.source_type == "xray_primary" and str(src.params.get("xray_method", "")).strip() == "ncrp_simplified")
        xray_ctx = get_xray_primary_workload_and_use_factor(xray_src, barrier)
        barrier_role = str(xray_ctx["barrier_role"])
        B = required_transmission_factor_from_weekly_dose(P, T, total_unshielded_uSv_week)
        required_material_mm = required_xray_ncrp147_thickness_mm(B, barrier_role, family)
        solver_used = f"ncrp147_archer_{barrier_role}"
        actual_B = xray_ncrp147_transmission_from_thickness(existing_thickness_mm, barrier_role, family)
        transmitted_dose_uSv_per_week = transmitted_weekly_dose_uSv(total_unshielded_uSv_week, T, actual_B)

    elif selected_solver == "ncrp_primary":
        primary_src = next(src for src in room.sources if src.source_type in XRAY_PRIMARY_SOURCE_TYPES)
        xray_ctx = get_xray_primary_workload_and_use_factor(primary_src, barrier)

        W = float(xray_ctx["workload_uSv_per_week_at_1m"])
        U = float(xray_ctx["use_factor"])

        B = primary_barrier_transmission(P, W, U, T, barrier.distance_m)
        required_material_mm = required_primary_thickness_from_tvl(B, barrier.material, energy_label)

        if xray_ctx["method"] == "ncrp_simplified":
            solver_used = f"ncrp_primary_tvl_{xray_ctx['barrier_role']}"
        else:
            solver_used = "ncrp_primary_tvl"

        actual_B = primary_transmission_from_thickness(
            existing_thickness_mm,
            barrier.material,
            energy_label,
        )
        transmitted_dose_uSv_per_week = transmitted_weekly_dose_uSv(
            total_unshielded_uSv_week, T, actual_B, use_factor=U
        )

    elif selected_solver == "ncrp_ct_secondary":
        B = required_transmission_factor_from_weekly_dose(P, T, total_unshielded_uSv_week)
        required_material_mm = required_ct_secondary_thickness_mm(B, family, energy_label)
        solver_used = "ncrp_ct_secondary_fit"

        actual_B = actual_ct_secondary_transmission_from_thickness(
            existing_thickness_mm,
            family,
            energy_label,
        )
        transmitted_dose_uSv_per_week = transmitted_weekly_dose_uSv(
            total_unshielded_uSv_week, T, actual_B
        )

    else:
        B = required_transmission_factor_from_weekly_dose(P, T, total_unshielded_uSv_week)
        required_material_mm = required_thickness_with_buildup(B, mu_cm_inv, family, energy_label)
        solver_used = "mu_plus_buildup"

        actual_B = actual_transmission_from_thickness_with_buildup(
            existing_thickness_mm,
            mu_cm_inv,
            family,
            energy_label,
        )
        transmitted_dose_uSv_per_week = total_unshielded_uSv_week * T * actual_B

    family_norm = str(family or "").strip().lower()
    material_norm = str(getattr(barrier, "material", "") or "").strip().lower()

    is_pb_equivalent = (
        family_norm in ("pb", "lead", "pb glass", "lead glass")
        or "pb glass" in material_norm
        or "lead glass" in material_norm
    )

    is_concrete = (
        family_norm == "concrete"
        or "concrete" in material_norm
    )

    if is_pb_equivalent:
        required_lead_mm = round(required_material_mm, 3)
        required_concrete_mm = "-"
        recommended = round_up_to_commercial(required_material_mm)
    elif is_concrete:
        required_lead_mm = "-"
        required_concrete_mm = round(required_material_mm, 1)
        recommended = "-"
    else:
        required_lead_mm = "-"
        required_concrete_mm = "-"
        recommended = "-"

    # ---------------------------------------------------------
    # Compliance is DOSE-governed, not thickness-governed.
    # PASS    : Tx < 0.8 P
    # REVIEW  : 0.8 P <= Tx < P
    # FAIL    : Tx >= P
    # ---------------------------------------------------------

    review_threshold = 0.8 * P

    if transmitted_dose_uSv_per_week >= P:
        compliance_status = "FAIL"
    elif transmitted_dose_uSv_per_week >= review_threshold:
        compliance_status = "REVIEW"
    else:
        compliance_status = "PASS"

    dose_margin_uSv_per_week = round(
        P - transmitted_dose_uSv_per_week,
        3,
    )

    margin_mm = round(
        existing_thickness_mm - required_material_mm,
        3,
    )

    return {
        "room": room.name,
        "room_modality": room.modality,
        "barrier": barrier.name,
        "adjacent_area": barrier.adjacent_area,
        "distance_m": round(barrier.distance_m, 3),
        "occupancy_factor": round(T, 4),
        "design_goal_uSv_per_week": round(P, 3),
        "unshielded_weekly_dose_uSv": round(total_unshielded_uSv_week, 3),
        "transmitted_dose_uSv_per_week": round(transmitted_dose_uSv_per_week, 3),
        "source_contributions": "; ".join([f"{n}: {d:.2f} uSv/wk" for n, d, _ in contributions]),
        "dominant_source_name": dominant_contribution_name(contributions),
        "barrier_transmission_factor_B": round(B, 6),
        "linear_attenuation_coefficient_cm_inv": mu_cm_inv,
        "required_lead_mm": required_lead_mm,
        "required_concrete_mm": required_concrete_mm,
        "recommended_commercial_lead_mm": recommended,
        "required_thickness_mm": round(required_material_mm, 3),
        "actual_thickness_mm": round(existing_thickness_mm, 3),
        "compliance_status": compliance_status,
        "dose_margin_uSv_per_week": dose_margin_uSv_per_week,
        "margin_mm": margin_mm,
        "notes": barrier.notes,
        "solver_used": solver_used,
    }


# =========================
# Public Physics API
# =========================

def compute_barrier_table(
    project: Project,
    energy_label: str,
    solver_mode: str = SOLVER_MODE_AUTO,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for room in project.rooms:
        for barrier in room.barriers:
            results.append(
                calc_barrier_result(
                    room,
                    barrier,
                    project,
                    energy_label,
                    solver_mode=solver_mode,
                )
            )
    return results


def compute_room_barrier_table(
    project: Project,
    room_name: str,
    energy_label: str,
    solver_mode: str = SOLVER_MODE_AUTO,
) -> List[Dict[str, Any]]:
    """
    DEPRECATED.

    Use barrier_model.build_barrier_set_state(...).live_results() instead.

    Kept temporarily as a compatibility shim during migration. It still calls
    calc_barrier_result(), so CT, SPECT/CT and X-ray modality-specific physics
    are preserved while external callers are moved to BarrierState.
    """
    room = next((r for r in project.rooms if r.name == room_name), None)
    if room is None:
        return []
    return [
        calc_barrier_result(
            room,
            barrier,
            project,
            energy_label,
            solver_mode=solver_mode,
        )
        for barrier in room.barriers
    ]


def compute_project_source_summary(project: Project) -> Dict[str, Any]:
    room_summaries: List[Dict[str, Any]] = []
    total_ct_mGy_per_week = 0.0
    total_nm_mSv_per_week = 0.0
    for room in project.rooms:
        summary = compute_room_source_summary(room)
        room_summaries.append({"room": room.name, **summary})
        total_ct_mGy_per_week += float(summary.get("total_ct_dose_mGy_per_week_at_1m", 0.0))
        total_nm_mSv_per_week += float(summary.get("total_nm_dscint_mSv_per_week_at_1m", 0.0))
    return {
        "rooms": room_summaries,
        "total_ct_dose_mGy_per_week_at_1m": total_ct_mGy_per_week,
        "total_nm_dscint_mSv_per_week_at_1m": total_nm_mSv_per_week,
        "total_combined_mSv_per_week_at_1m": total_nm_mSv_per_week + (total_ct_mGy_per_week / 1000.0),
    }

def default_barriers() -> List[Barrier]:
    names = ["N wall", "E wall", "S wall", "W wall", "Floor", "Ceiling"]
    barriers: List[Barrier] = []
    for name in names:
        adjacent = "Clinical Area" if name in ("Floor", "Ceiling") else "Corridor"
        occupancy = 1.0 if adjacent == "Clinical Area" else 0.2
        material = "Concrete" if name in ("Floor", "Ceiling") else "Pb"
        thickness = 150.0 if name in ("Floor", "Ceiling") else 0.88
        legacy = "Concrete 150 mm" if name in ("Floor", "Ceiling") else "Pb 0.88 mm (10 kg/m2)"
        barriers.append(
            Barrier(
                name=name,
                adjacent_area=adjacent,
                distance_m=2.0,
                occupancy_factor=occupancy,
                design_goal_uSv_per_week=10.0,
                material=material,
                thickness_mm=thickness,
                material_legacy=legacy,
                notes="",
            )
        )
    return barriers

def build_example_project() -> Project:
    return Project(
        project_name="Example Shielding Assessment",
        client="Example Imaging Pty Ltd",
        site="123 Example Street, Sydney NSW",
        assessor="Health Physics Pty Ltd",
        date=datetime.now().strftime("%Y-%m-%d"),
        modality="CT",  # default project label
        notes="Simplified preliminary shielding assessment.",
        rooms=[
            Room(
                name="CT Room 1",
                modality="CT",
                sources=[],  # IMPORTANT: empty → Geometry tab will populate
                barriers=default_barriers(),
            )
        ],
        sources=[],  # IMPORTANT: project-level source of truth
    )


def dispatch_room_persisted_pet_calculation(
    project: Project,
    room_name: str,
):
    """Dispatch persisted PET working state without opening Results/reports.

    This is an explicit project-calculation entry point for the persisted PET
    single-source contract. It is intentionally separate from
    ``calc_barrier_result`` / ``compute_room_barrier_table`` so the existing
    normal Results and report pipelines remain closed to PET.
    """

    from engine.pet_project_dispatch import dispatch_persisted_pet_working_state

    return dispatch_persisted_pet_working_state(project, room_name)
