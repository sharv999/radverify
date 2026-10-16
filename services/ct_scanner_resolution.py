from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from engine.ct_scatter_engine import CTScatterEngine, ScatterEngineError
except Exception:  # pragma: no cover - keeps the service importable in tests without the engine package.
    CTScatterEngine = None  # type: ignore[assignment]

    class ScatterEngineError(Exception):
        pass




@dataclass(frozen=True)
class CTScannerResolutionContext:
    ct_scatter_engine: Any = None
    raw_database: Dict[str, Any] | None = None
    engine_status_message: str = "CT scatter engine unavailable"


def _json_candidates(base_dir: Path | None = None) -> list[Path]:
    root = base_dir or Path.cwd()
    return [
        root / "data" / "ct" / "ct_scatter_master_database.json",
        root / "ct_scatter_master_database.json",
    ]


def load_ct_scanner_resolution_context(base_dir: Path | None = None) -> CTScannerResolutionContext:
    """Load CT scatter engine and raw JSON needed by the central scanner/Ksec resolver."""
    raw_database: Dict[str, Any] = {}

    for candidate in _json_candidates(base_dir):
        if not candidate.exists():
            continue
        try:
            raw_database = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            raw_database = {}

        if CTScatterEngine is None:
            return CTScannerResolutionContext(
                ct_scatter_engine=None,
                raw_database=raw_database,
                engine_status_message="CT scatter engine unavailable",
            )

        try:
            engine = CTScatterEngine(candidate)
            family_count = len((raw_database.get("scanner_families", {}) or {}) if isinstance(raw_database, dict) else {})
            if family_count <= 0:
                try:
                    family_count = len(engine.list_scanners())
                except Exception:
                    family_count = 0
            return CTScannerResolutionContext(
                ct_scatter_engine=engine,
                raw_database=raw_database,
                engine_status_message=f"{family_count} CT scatter families loaded (scanner_families metadata-derived)",
            )
        except Exception as exc:
            return CTScannerResolutionContext(
                ct_scatter_engine=None,
                raw_database=raw_database,
                engine_status_message=f"CT scatter engine unavailable: {exc}",
            )

    if CTScatterEngine is not None:
        try:
            engine = CTScatterEngine()
            return CTScannerResolutionContext(
                ct_scatter_engine=engine,
                raw_database=raw_database,
                engine_status_message=f"{len(engine.list_scanners())} CT scatter families loaded",
            )
        except Exception as exc:
            return CTScannerResolutionContext(
                ct_scatter_engine=None,
                raw_database=raw_database,
                engine_status_message=f"CT scatter engine unavailable: {exc}",
            )

    return CTScannerResolutionContext(raw_database=raw_database)


def scanner_resolution_service_from_context(context: CTScannerResolutionContext) -> "CTScannerResolutionService":
    return CTScannerResolutionService(
        ct_scatter_engine=context.ct_scatter_engine,
        raw_database=context.raw_database or {},
        engine_status_message=context.engine_status_message,
    )

@dataclass(frozen=True)
class CTKsecResolution:
    ksec_mGy_per_100mAs_at_1m: Optional[float]
    scanner_source: str
    requires_manual_override: bool = False
    error_message: str = ""
    ksec_energy_kvp: Optional[int] = None

    @property
    def has_database_ksec(self) -> bool:
        return self.ksec_mGy_per_100mAs_at_1m is not None and not self.requires_manual_override






@dataclass(frozen=True)
class CTFamilySelectionResolution:
    scanner_family: str
    scanner_phantom: str
    display_text: str

@dataclass(frozen=True)
class CTSourceSelectionResolution:
    scanner_family: str
    phantom: str
    ksec_mGy_per_100mAs_at_1m: Optional[float]
    scanner_source: str
    scanner_debug: str
    requires_manual_override: bool = False
    error_message: str = ""
    ksec_energy_kvp: Optional[int] = None

@dataclass(frozen=True)
class LegacyCTKsecResolution:
    ksec_mGy_per_100mAs_at_1m: float
    scanner_source: str
    status_message: str
    matched: bool = False
    source_note: str = ""

class CTScannerResolutionService:
    """
    Service boundary for CT scanner-family routing and database Ksec resolution.

    The Tk app should treat this as the source of truth for:
    - source_type -> allowed ct_scanner_metadata buckets
    - scanner family list/defaults
    - vendor/model/display-name -> JSON scanner family
    - JSON worst-case Ksec lookup and NULL-Ksec blocking
    """

    def __init__(
        self,
        *,
        ct_scatter_engine: Any = None,
        raw_database: Optional[Dict[str, Any]] = None,
        engine_status_message: str = "CT scatter engine unavailable",
    ) -> None:
        self.ct_scatter_engine = ct_scatter_engine
        self.raw_database = raw_database or {}
        self.engine_status_message = engine_status_message

    def allowed_metadata_for_source_type(self, source_type: str | None = None) -> set[str]:
        stype = str(source_type or "").strip() or "ct_scatter"

        if stype == "spect_ct_secondary_scatter":
            return {
                "hybrid_ct_component_attenuation_correction",
                "hybrid_ct_component_diagnostic",
            }

        if stype == "ct_scatter":
            return {"ct_standalone_diagnostic"}

        return set()

    def all_family_keys(self) -> list[str]:
        raw = self.raw_database or {}
        if isinstance(raw, dict):
            families = raw.get("scanner_families", {}) or {}
            if isinstance(families, dict) and families:
                return list(families.keys())

        if self.ct_scatter_engine is None:
            return []

        try:
            return list(self.ct_scatter_engine.list_scanners())
        except Exception:
            return []

    def raw_family(self, family_key: str) -> Dict[str, Any]:
        raw = self.raw_database or {}
        if not isinstance(raw, dict):
            return {}

        families = raw.get("scanner_families", {}) or {}
        if not isinstance(families, dict):
            return {}

        family_key = str(family_key or "").strip()
        family = families.get(family_key, {}) or {}

        # Resolve inherited metadata while preserving child fields.
        seen = set()
        merged: Dict[str, Any] = {}
        current = family
        while isinstance(current, dict) and current:
            merged = {**current, **merged}
            parent_key = str(current.get("inherits", "") or "").strip()
            if not parent_key or parent_key in seen:
                break
            seen.add(parent_key)
            current = families.get(parent_key, {}) or {}

        return merged or (family if isinstance(family, dict) else {})

    def family_values(self, source_type: str | None = None) -> list[str]:
        allowed_metadata = self.allowed_metadata_for_source_type(source_type)
        if not allowed_metadata:
            return []

        values = []
        for key in self.all_family_keys():
            try:
                meta = self.raw_family(key)
                if not meta and self.ct_scatter_engine is not None:
                    meta = self.ct_scatter_engine.get_scanner(key) or {}
            except Exception:
                meta = {}

            scanner_metadata = str(meta.get("ct_scanner_metadata", "")).strip()
            if scanner_metadata in allowed_metadata:
                values.append(key)

        return sorted(dict.fromkeys(values))

    def default_family_for_source_type(self, source_type: str) -> str:
        families = self.family_values(source_type)
        if families:
            if source_type == "spect_ct_secondary_scatter" and "GE_NMCT_LOW_DOSE" in families:
                return "GE_NMCT_LOW_DOSE"
            if source_type == "ct_scatter" and "GE_REVOLUTION_APEX_FAMILY" in families:
                return "GE_REVOLUTION_APEX_FAMILY"
            return families[0]
        return ""

    def family_requires_digitisation(self, scanner_family: str) -> bool:
        if not scanner_family or self.ct_scatter_engine is None:
            return False
        try:
            scanner = self.ct_scatter_engine.get_scanner(scanner_family)
            dtype = str(scanner.get("geometry", {}).get("data_type", "")).strip()
            return dtype.endswith("pending_digitisation") or dtype == "metadata_only_pending_digitisation"
        except Exception:
            return False

    def json_worst_case_ksec_per_100mAs(self, scanner_family: str, kvp: int) -> tuple[float | None, str]:
        scanner_family = str(scanner_family or "").strip()
        if not scanner_family or self.ct_scatter_engine is None:
            return None, ""

        try:
            scanner = self.ct_scatter_engine.get_scanner(scanner_family)
        except Exception:
            return None, ""

        raw = scanner.get("worst_case_ksec_mGy_per_100mAs_at_1m", None)
        if raw in (None, ""):
            return None, ""

        try:
            value = float(raw)
        except Exception:
            return None, ""

        return value, f"JSON worst-case Ksec lookup ({scanner_family})"

    def default_phantom(self, scanner_family: str) -> str:
        if not scanner_family or self.ct_scatter_engine is None:
            return "body"
        try:
            scanner = self.ct_scatter_engine.get_scanner(scanner_family)
            profiles = scanner.get("profiles", {})
            if "body" in profiles:
                return "body"
            if profiles:
                keys = list(profiles.keys())
                if any(str(k).startswith("body_") for k in keys):
                    return "body"
                if any(str(k).startswith("head_") for k in keys):
                    return "head"
                return next(iter(profiles.keys()))
        except Exception:
            pass
        return "body"

    def canonical_vendor_label(self, vendor: str) -> str:
        v = (vendor or "").strip().lower()

        if "siemens" in v:
            return "Siemens"
        if "ge" in v:
            return "GE"
        if "canon" in v:
            return "Canon"
        if "philips" in v:
            return "Philips"

        return vendor.strip()

    def friendly_model_name(self, family_key: str) -> str:
        family_key = str(family_key or "").strip()
        if not family_key:
            return ""

        try:
            family = self.raw_family(family_key)

            vendor_raw = str(family.get("vendor", "") or "").strip()
            vendor = self.canonical_vendor_label(vendor_raw)

            short = str(family.get("short_name", "") or "").strip()
            if short:
                return f"{vendor} {short}".strip()

            desc = str(family.get("description", "") or "").strip()

            if desc:
                desc = desc.replace(" diagnostic CT.", "")
                desc = desc.replace(" CT component.", "")
                desc = desc.replace(" low-dose CT component.", "")
                desc = desc.replace(" diagnostic CT family.", "")
                desc = desc.replace(
                    " Placeholder pending vendor scatter/RAD protection data.", ""
                )

                desc = desc.split(".")[0].strip()

                return f"{vendor} {desc}".strip()

        except Exception:
            pass

        return family_key

    def metadata_for_family(self, family_key: str) -> str:
        family_key = str(family_key or "").strip()
        if not family_key:
            return ""

        try:
            scanner = self.raw_family(family_key)
            metadata = str(scanner.get("ct_scanner_metadata", "")).strip()
            if metadata:
                return metadata
        except Exception:
            pass

        if self.ct_scatter_engine is None:
            return ""
        try:
            scanner = self.ct_scatter_engine.get_scanner(family_key) or {}
            return str(scanner.get("ct_scanner_metadata", "")).strip()
        except Exception:
            return ""

    def model_values_for_source_type(self, source_type: str, vendor: str = "") -> list[str]:
        values = []

        for family_key in self.family_values(source_type):
            try:
                values.append(self.friendly_model_name(family_key))
            except Exception:
                continue

        return sorted(dict.fromkeys(values))

    def vendor_values_for_source_type(self, source_type: str) -> list[str]:
        vendors = set()

        for family_key in self.family_values(source_type):
            try:
                family = self.raw_family(family_key)
                vendor = self.canonical_vendor_label(family.get("vendor", ""))
                if vendor:
                    vendors.add(vendor)
            except Exception:
                pass

        return sorted(vendors)

    def display_to_family_map(self, source_type: str) -> dict[str, str]:
        mapping = {}

        for family_key in self.family_values(source_type):
            display = self.friendly_model_name(family_key)
            if display:
                mapping[display] = family_key

            mapping[family_key] = family_key

        return mapping

    def family_from_display(self, source_type: str, display_value: str) -> str:
        display_value = str(display_value or "").strip()
        if not display_value:
            return ""

        mapping = self.display_to_family_map(source_type)
        if display_value in mapping:
            return mapping[display_value]

        return self.resolve_family_from_vendor_model(
            source_type=source_type,
            vendor="",
            model=display_value,
            current_family="",
        )

    def resolve_family_from_vendor_model(self, source_type: str, vendor: str, model: str, current_family: str = "") -> str:
        vendor = str(vendor or "").strip()
        model = str(model or "").strip()
        source_type = str(source_type or "").strip() or "ct_scatter"
        current_family = str(current_family or "").strip()

        if self.ct_scatter_engine is None:
            return ""

        try:
            candidates = set(self.family_values(source_type))
        except Exception:
            candidates = set()

        def allowed(family_key: str) -> str:
            family_key = str(family_key or "").strip()
            return family_key if family_key in candidates else ""

        def norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()

        model_n = norm(model)
        vendor_n = norm(vendor)

        explicit_model_to_family = {
            # GE hybrid CT components
            "nm ct 670 870": "GE_NMCT_LOW_DOSE",
            "ge nm ct 670 870": "GE_NMCT_LOW_DOSE",
            "discovery nm ct 670": "GE_NMCT_LOW_DOSE",
            "discovery nm ct 870": "GE_NMCT_LOW_DOSE",
            "nm ct 670 870 czt": "GE_NMCT_LOW_DOSE_CZT",
            "ge nm ct 670 870 czt": "GE_NMCT_LOW_DOSE_CZT",
            "discovery nm ct 670 czt": "GE_NMCT_LOW_DOSE_CZT",
            "discovery nm ct 870 czt": "GE_NMCT_LOW_DOSE_CZT",
            "nm ct 850 860": "GE_NMCT_850_860",
            "ge nm ct 850 860": "GE_NMCT_850_860",
            "nm ct 850": "GE_NMCT_850_860",
            "nm ct 860": "GE_NMCT_850_860",

            # Siemens hybrid CT components
            "symbia t2": "SIEMENS_SYMBIA_T2",
            "symbia t6": "SIEMENS_SYMBIA_T6",
            "symbia t16": "SIEMENS_SYMBIA_T16",
            "symbia intevo excel": "SIEMENS_SYMBIA_INTEVO_EXCEL",
            "symbia intevo 2": "SIEMENS_SYMBIA_INTEVO_2",
            "symbia intevo 6": "SIEMENS_SYMBIA_INTEVO_6",
            "symbia intevo 16": "SIEMENS_SYMBIA_INTEVO_16",
            "symbia intevo bold": "SIEMENS_SYMBIA_INTEVO_BOLD",
            "symbia pro specta q3": "SIEMENS_SYMBIA_PROSPECTA_Q3",
            "symbia prospecta q3": "SIEMENS_SYMBIA_PROSPECTA_Q3",
            "symbia pro specta x3": "SIEMENS_SYMBIA_PROSPECTA_X3",
            "symbia prospecta x3": "SIEMENS_SYMBIA_PROSPECTA_X3",
            "symbia pro specta x7": "SIEMENS_SYMBIA_PROSPECTA_X7",
            "symbia prospecta x7": "SIEMENS_SYMBIA_PROSPECTA_X7",

            # Standalone diagnostic CT
            "revolution apex": "GE_REVOLUTION_APEX_FAMILY",
            "revolution apex elite": "GE_REVOLUTION_APEX_FAMILY",
            "discovery rt": "GE_DISCOVERY_RT",
            "discovery ct590rt": "GE_DISCOVERY_CT590RT",
            "discovery ct 590 rt": "GE_DISCOVERY_CT590RT",
            "optima ct580": "GE_OPTIMA_CT580",
            "optima ct 580": "GE_OPTIMA_CT580",
            "revolution evo": "GE_REVOLUTION_EVO",
            "revolution ct": "GE_REVOLUTION_CT_FAMILY",
            "ge revolution ct": "GE_REVOLUTION_CT_FAMILY",
        }

        family = explicit_model_to_family.get(model_n, "")
        resolved = allowed(family)
        if resolved:
            return resolved

        for key in [model, f"{vendor} {model}".strip(), f"{vendor}_{model}".strip()]:
            if not key:
                continue
            try:
                resolved = allowed(self.ct_scatter_engine.resolve_scanner_family(key))
                if resolved:
                    return resolved
            except Exception:
                pass

        if source_type == "spect_ct_secondary_scatter":
            if "ge" in vendor_n or "healthcare" in vendor_n:
                if "850" in model_n or "860" in model_n:
                    resolved = allowed("GE_NMCT_850_860")
                    if resolved:
                        return resolved
                if "czt" in model_n and ("670" in model_n or "870" in model_n):
                    resolved = allowed("GE_NMCT_LOW_DOSE_CZT")
                    if resolved:
                        return resolved
                if "670" in model_n or "870" in model_n:
                    resolved = allowed("GE_NMCT_LOW_DOSE")
                    if resolved:
                        return resolved

            if "siemens" in vendor_n:
                siemens_ordered = [
                    ("SIEMENS_SYMBIA_INTEVO_BOLD", ["intevo bold"]),
                    ("SIEMENS_SYMBIA_INTEVO_EXCEL", ["intevo excel", "excel"]),
                    ("SIEMENS_SYMBIA_INTEVO_16", ["intevo 16"]),
                    ("SIEMENS_SYMBIA_INTEVO_6", ["intevo 6"]),
                    ("SIEMENS_SYMBIA_INTEVO_2", ["intevo 2"]),
                    ("SIEMENS_SYMBIA_PROSPECTA_Q3", ["pro specta q3", "prospecta q3"]),
                    ("SIEMENS_SYMBIA_PROSPECTA_X3", ["pro specta x3", "prospecta x3"]),
                    ("SIEMENS_SYMBIA_PROSPECTA_X7", ["pro specta x7", "prospecta x7"]),
                    ("SIEMENS_SYMBIA_T16", ["symbia t16", "t16"]),
                    ("SIEMENS_SYMBIA_T6", ["symbia t6", "t6"]),
                    ("SIEMENS_SYMBIA_T2", ["symbia t2", "t2"]),
                ]
                for family_key, labels in siemens_ordered:
                    if any(label in model_n for label in labels):
                        resolved = allowed(family_key)
                        if resolved:
                            return resolved
        else:
            if "ge" in vendor_n or "healthcare" in vendor_n:
                ge_ct_ordered = [
                    ("GE_REVOLUTION_APEX_FAMILY", ["apex elite", "apex"]),
                    ("GE_DISCOVERY_CT590RT", ["ct590rt", "ct 590 rt", "590"]),
                    ("GE_DISCOVERY_RT", ["discovery rt"]),
                    ("GE_OPTIMA_CT580", ["optima ct580", "optima ct 580", "580"]),
                    ("GE_REVOLUTION_EVO", ["revolution evo", "evo"]),
                    ("GE_REVOLUTION_CT_FAMILY", ["revolution ct"]),
                ]
                for family_key, labels in ge_ct_ordered:
                    if any(label in model_n for label in labels):
                        resolved = allowed(family_key)
                        if resolved:
                            return resolved

        resolved = allowed(current_family)
        if resolved:
            return resolved

        return self.default_family_for_source_type(source_type)


    def legacy_csv_ksec_per_100mAs(
        self,
        *,
        db: Any,
        vendor: str,
        model: str,
        kvp: int,
        conservative_default_fn: Any = None,
    ) -> LegacyCTKsecResolution:
        if db and vendor and model:
            try:
                rec = db.lookup(model=model, vendor=vendor, fuzzy=True)
                source_label = rec.source or "database"
                return LegacyCTKsecResolution(
                    ksec_mGy_per_100mAs_at_1m=float(rec.ksec_for_kvp(kvp) * 100.0),
                    scanner_source=f"{rec.vendor} / {rec.model} ({source_label})",
                    status_message=f"Matched: {rec.vendor} / {rec.model}",
                    matched=True,
                    source_note=rec.source_note or "",
                )
            except Exception:
                pass

        if conservative_default_fn is None:
            raise ValueError("No CT scanner match and no conservative default function was provided")

        fallback = float(conservative_default_fn(kvp) * 100.0)
        status = "No match; using conservative default" if db is not None else "No CT DB available; using conservative default"
        return LegacyCTKsecResolution(
            ksec_mGy_per_100mAs_at_1m=fallback,
            scanner_source="conservative default",
            status_message=status,
            matched=False,
            source_note="",
        )

    def engine_scatter_point_to_ksec_per_100mAs(self, scanner_family: str, kvp: int, phantom: str = "body") -> tuple[float, str]:
        if not scanner_family:
            raise ScatterEngineError("No CT scatter family selected")
        if self.ct_scatter_engine is None:
            raise ScatterEngineError(self.engine_status_message)
        if self.family_requires_digitisation(scanner_family):
            raise ScatterEngineError(f"{scanner_family} is loaded but contour digitisation is still pending")

        scanner = self.ct_scatter_engine.get_scanner(scanner_family)
        geometry_type = str(scanner.get("geometry", {}).get("data_type", "")).strip()

        evaluations = []
        for plane, lateral_m, z_m in (
            ("horizontal", 0.0, 1.0),
            ("vertical", 1.0, 0.0),
        ):
            try:
                result = self.ct_scatter_engine.estimate_scatter(
                    scanner_family,
                    plane=plane,
                    phantom=phantom,
                    z_m=z_m,
                    lateral_m=lateral_m,
                    mAs=100.0,
                    kVp=float(kvp),
                )
                ksec_per_100mAs = float(result.scatter_uGy) / 1000.0
                evaluations.append((ksec_per_100mAs, plane, result.method))
            except Exception:
                continue

        if not evaluations:
            raise ScatterEngineError(f"No scatter estimate available for {scanner_family}")

        worst_ksec, worst_plane, worst_method = max(evaluations, key=lambda x: x[0])
        source_text = f"Vendor scatter engine {scanner_family} worst-case @1m ({geometry_type}; {worst_plane}; {worst_method})"
        return worst_ksec, source_text

    def source_ksec_per_100mAs(self, source_type: str, scanner_family: str, vendor: str, model: str, kvp: int, phantom: str = "body") -> tuple[float, str]:
        scanner_family = str(scanner_family or "").strip()

        if scanner_family:
            value, source_text = self.json_worst_case_ksec_per_100mAs(scanner_family, kvp)
            if value is not None:
                return float(value), f"{vendor} / {model} -> {source_text}"

            raise ValueError(
                "Selected scanner has NULL ksec in ct_scatter_master_database.json; "
                f"manual ksec override is required for {scanner_family}."
            )

        raise ValueError("No JSON scatter scanner family selected; ksec cannot be resolved.")



    def resolve_family_selection(
        self,
        *,
        source_type: str,
        vendor: str,
        model: str,
        current_family: str = "",
    ) -> CTFamilySelectionResolution:
        family = self.resolve_family_from_vendor_model(
            source_type=source_type,
            vendor=vendor,
            model=model,
            current_family=current_family,
        )
        return CTFamilySelectionResolution(
            scanner_family=family,
            scanner_phantom=self.default_phantom(family) if family else "",
            display_text=family or "No resolved scatter dataset",
        )

    def repaired_family_params_for_source_type(self, params: Dict[str, Any], source_type: str) -> Dict[str, str]:
        family = str((params or {}).get("scanner_family", "") or "").strip()
        metadata = self.metadata_for_family(family) if family else ""
        if metadata in self.allowed_metadata_for_source_type(source_type):
            return {"scanner_family": family, "scanner_phantom": str((params or {}).get("scanner_phantom", "") or "").strip()}

        default_family = self.default_family_for_source_type(source_type)
        return {"scanner_family": default_family, "scanner_phantom": self.default_phantom(default_family)}

    def resolve_source_ksec_selection(
        self,
        *,
        source_type: str,
        vendor: str,
        model: str,
        kvp: int,
    ) -> CTSourceSelectionResolution:
        """Resolve scanner family, phantom and Ksec for the active CT source selector.

        This is the central resolver used by the Tk app. It intentionally returns
        UI-ready status/debug strings so app.py does not duplicate scanner/Ksec
        fallback or NULL-Ksec wording.
        """
        source_type = str(source_type or "ct_scatter").strip() or "ct_scatter"
        vendor = str(vendor or "").strip()
        model = str(model or "").strip()
        scanner_family = self.family_from_display(source_type, model)
        phantom = self.default_phantom(scanner_family)

        try:
            ksec, source_text = self.source_ksec_per_100mAs(
                source_type=source_type,
                scanner_family=scanner_family,
                vendor=vendor,
                model=model,
                kvp=kvp,
                phantom=phantom,
            )
            return CTSourceSelectionResolution(
                scanner_family=scanner_family,
                phantom=phantom,
                ksec_mGy_per_100mAs_at_1m=float(ksec),
                scanner_source=source_text,
                scanner_debug=f"{vendor} | {model} | {scanner_family}",
                requires_manual_override=False,
                error_message="",
                ksec_energy_kvp=kvp,
            )
        except Exception as exc:
            return CTSourceSelectionResolution(
                scanner_family=scanner_family,
                phantom=phantom,
                ksec_mGy_per_100mAs_at_1m=None,
                scanner_source=f"NULL ksec — manual override required ({exc})",
                scanner_debug=f"{vendor} | {model} | {scanner_family} | NULL ksec",
                requires_manual_override=True,
                error_message=str(exc),
                ksec_energy_kvp=kvp,
            )

    def resolve_database_ct_ksec(self, scanner_family: str, vendor: str, model: str, kvp: int) -> CTKsecResolution:
        scanner_family = str(scanner_family or "").strip()
        energy_kvp: Optional[int] = int(kvp) if kvp is not None else None

        try:
            if scanner_family and self.ct_scatter_engine is not None:
                try:
                    scanner = self.ct_scatter_engine.get_scanner(scanner_family) or {}
                except Exception:
                    scanner = {}
                raw_energy = scanner.get("ksec_energy_kvp") if isinstance(scanner, dict) else None
                if raw_energy not in (None, ""):
                    try:
                        energy_kvp = int(float(raw_energy))
                    except Exception:
                        energy_kvp = int(kvp) if kvp is not None else None

            ksec, source_text = self.source_ksec_per_100mAs(
                source_type="ct_scatter",
                scanner_family=scanner_family,
                vendor=vendor,
                model=model,
                kvp=kvp,
                phantom=self.default_phantom(scanner_family),
            )
            if energy_kvp is not None and "kVp" not in source_text:
                source_text = f"{source_text} @ {energy_kvp} kVp"
            return CTKsecResolution(
                ksec_mGy_per_100mAs_at_1m=float(ksec),
                scanner_source=source_text,
                requires_manual_override=False,
                error_message="",
                ksec_energy_kvp=energy_kvp,
            )
        except Exception as exc:
            return CTKsecResolution(
                ksec_mGy_per_100mAs_at_1m=None,
                scanner_source=f"NULL ksec — manual override required ({exc})",
                requires_manual_override=True,
                error_message=str(exc),
                ksec_energy_kvp=energy_kvp,
            )




def ct_vendor_values_for_source_type(context: CTScannerResolutionContext, source_type: str) -> list[str]:
    return scanner_resolution_service_from_context(context).vendor_values_for_source_type(source_type)


def ct_model_values_for_source_type(context: CTScannerResolutionContext, source_type: str, vendor: str = "") -> list[str]:
    return scanner_resolution_service_from_context(context).model_values_for_source_type(source_type, vendor)


def resolve_family_selection(
    context: CTScannerResolutionContext,
    *,
    source_type: str,
    vendor: str,
    model: str,
    current_family: str = "",
) -> CTFamilySelectionResolution:
    return scanner_resolution_service_from_context(context).resolve_family_selection(
        source_type=source_type,
        vendor=vendor,
        model=model,
        current_family=current_family,
    )


def repair_ct_family_params_for_source_type(
    context: CTScannerResolutionContext,
    params: Dict[str, Any],
    source_type: str,
) -> Dict[str, str]:
    return scanner_resolution_service_from_context(context).repaired_family_params_for_source_type(params, source_type)


def central_ct_ksec_resolver(
    context: CTScannerResolutionContext,
    *,
    source_type: str,
    vendor: str,
    model: str,
    kvp: int,
) -> CTSourceKsecSelection:
    """Central CT scanner/ksec resolver used by app.py.

    This is the service-level boundary for UI selector state: app.py supplies
    form values and receives a fully resolved family/phantom/ksec result.
    """
    return resolve_ct_source_ksec_selection(
        context,
        source_type=source_type,
        vendor=vendor,
        model=model,
        kvp=kvp,
    )


def resolve_ct_source_ksec_selection(
    context: CTScannerResolutionContext,
    *,
    source_type: str,
    vendor: str,
    model: str,
    kvp: int,
) -> CTSourceSelectionResolution:
    return scanner_resolution_service_from_context(context).resolve_source_ksec_selection(
        source_type=source_type,
        vendor=vendor,
        model=model,
        kvp=kvp,
    )


def metadata_for_ct_family(context: CTScannerResolutionContext, family_key: str) -> str:
    return scanner_resolution_service_from_context(context).metadata_for_family(family_key)


def resolve_legacy_csv_ct_ksec(
    *,
    db: Any,
    vendor: str,
    model: str,
    kvp: int,
    conservative_default_fn: Any = None,
) -> LegacyCTKsecResolution:
    """Resolve Ksec from the legacy CSV scanner database."""
    return CTScannerResolutionService().legacy_csv_ksec_per_100mAs(
        db=db,
        vendor=vendor,
        model=model,
        kvp=kvp,
        conservative_default_fn=conservative_default_fn,
    )


def raw_ct_family(context: CTScannerResolutionContext, family_key: str) -> Dict[str, Any]:
    return scanner_resolution_service_from_context(context).raw_family(family_key)


def default_ct_phantom_for_family(context: CTScannerResolutionContext, family_key: str) -> str:
    return scanner_resolution_service_from_context(context).default_phantom(family_key)


def canonical_ct_vendor_label(context: CTScannerResolutionContext, vendor: str) -> str:
    return scanner_resolution_service_from_context(context).canonical_vendor_label(vendor)


def friendly_ct_model_name(context: CTScannerResolutionContext, family_key: str) -> str:
    return scanner_resolution_service_from_context(context).friendly_model_name(family_key)


def resolve_database_ct_ksec_from_context(
    context: CTScannerResolutionContext,
    *,
    scanner_family: str,
    vendor: str,
    model: str,
    kvp: int,
) -> CTKsecResolution:
    return scanner_resolution_service_from_context(context).resolve_database_ct_ksec(
        scanner_family=scanner_family,
        vendor=vendor,
        model=model,
        kvp=kvp,
    )

def resolve_database_ct_ksec(
    *,
    ct_scatter_engine: Any,
    scanner_family: str,
    vendor: str,
    model: str,
    kvp: int,
    raw_database: Optional[Dict[str, Any]] = None,
    engine_status_message: str = "CT scatter engine unavailable",
) -> CTKsecResolution:
    """Compatibility function for form-sync code that only needs database Ksec resolution."""
    service = CTScannerResolutionService(
        ct_scatter_engine=ct_scatter_engine,
        raw_database=raw_database,
        engine_status_message=engine_status_message,
    )
    return service.resolve_database_ct_ksec(
        scanner_family=scanner_family,
        vendor=vendor,
        model=model,
        kvp=kvp,
    )
