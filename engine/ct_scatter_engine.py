from __future__ import annotations

"""Vendor-calibrated CT scatter engine.

This module supports both:
- legacy databases using a top-level ``scanners`` mapping
- ingestion-pipeline databases using ``scanner_families`` + ``aliases`` + ``sources``

Design goals:
- safe defaults
- explicit provenance fields
- backward compatibility with older app builds
- deterministic fallback behaviour for incomplete vendor tables
"""

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any, Dict, Iterable, Mapping, Optional


DEFAULT_DB_PATH = Path(__file__).with_name("ct_scatter_master_database.json")

KNOWN_FALLBACK_PEAKS_UGY = {
    "GE_REVOLUTION_APEX_ELITE": 166.10,
}


class ScatterEngineError(RuntimeError):
    """Raised when a scatter lookup cannot be completed safely."""


@dataclass(frozen=True)
class ScatterResult:
    scanner_key: str
    resolved_scanner_key: str
    plane: str
    x_m: Optional[float]
    y_m: Optional[float]
    z_m: float
    phantom: str
    scatter_uGy: float
    scatter_unit_basis: str
    workload_mAs: float
    kVp: float
    scaling_factor: float
    method: str
    notes: str = ""


class CTScatterEngine:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Scatter database not found: {self.db_path}")

        with self.db_path.open("r", encoding="utf-8") as fh:
            self.db = json.load(fh)

        # New ingestion-pipeline structure
        if "scanner_families" in self.db:
            self.scanners: Dict[str, Mapping[str, Any]] = self.db["scanner_families"]
            self.aliases: Dict[str, str] = dict(self.db.get("aliases", {}))
            self.sources: list[Mapping[str, Any]] = list(self.db.get("sources", []))
        else:
            # Backward compatibility
            self.scanners = self.db.get("scanners", {})
            self.aliases = {}
            self.sources = list(self.db.get("sources", []))

        if not isinstance(self.scanners, dict) or not self.scanners:
            raise ScatterEngineError("No scanners found in scatter database.")

    def list_scanners(self) -> list[str]:
        """Return canonical keys plus any aliases for UI friendliness."""
        return sorted(set(list(self.scanners.keys()) + list(self.aliases.keys())))

    def list_families(self) -> list[str]:
        return sorted(self.scanners.keys())

    def resolve_scanner_family(self, key: str) -> str:
        return self.aliases.get(key, key)

    def get_scanner(self, scanner_key: str) -> Mapping[str, Any]:
        resolved = self.resolve_scanner_family(scanner_key)
        try:
            return self.scanners[resolved]
        except KeyError as exc:
            raise ScatterEngineError(f"Unknown scanner key: {scanner_key}") from exc

    def get_scanner_metadata(self, scanner_key: str) -> dict:
        resolved = self.resolve_scanner_family(scanner_key)
        scanner = self.get_scanner(resolved)
        geometry = scanner.get("geometry", {}) or {}
        return {
            "requested_key": scanner_key,
            "resolved_key": resolved,
            "vendor": scanner.get("vendor"),
            "family": scanner.get("family"),
            "models": scanner.get("models", []),
            "modality": scanner.get("modality_class", scanner.get("modality")),
            "data_type": geometry.get("data_type"),
            "scatter_unit": scanner.get("scatter_unit"),
        }

    def estimate_scatter(
        self,
        scanner_key: str,
        *,
        plane: str,
        phantom: str,
        z_m: float,
        lateral_m: float = 0.0,
        mAs: float = 100.0,
        kVp: float = 140.0,
        collimation_key: str | None = None,
        aperture_key: str | None = None,
        protocol_name: str | None = None,
    ) -> ScatterResult:
        resolved_key = self.resolve_scanner_family(scanner_key)
        scanner = self.get_scanner(resolved_key)
        scatter_unit = scanner.get("scatter_unit", "uGy_per_scan")

        geometry = scanner.get("geometry", {}) or {}
        data_type = str(geometry.get("data_type", "")).strip()

        if data_type in {"sparse_matrix_with_interpolation", "matrix", "sparse_matrix"}:
            base, method = self._estimate_from_matrix_geometry(
                scanner,
                plane=plane,
                lateral_m=lateral_m,
                z_m=z_m,
            )
        elif data_type == "protocol_matrix":
            protocol_name = protocol_name or self._default_protocol_name(scanner)
            base, method = self._estimate_from_protocol_matrix(
                scanner,
                protocol_name=protocol_name,
                plane=plane,
                lateral_m=lateral_m,
                z_m=z_m,
            )
            protocol_meta = self._get_protocol(scanner, protocol_name)
            if protocol_meta.get("mAs_per_scan") not in (None, ""):
                mAs = float(protocol_meta["mAs_per_scan"])
            if protocol_meta.get("kVp") not in (None, ""):
                kVp = float(protocol_meta["kVp"])
        elif data_type in {"sparse_iso_contours", "contour_family"}:
            base, method = self._estimate_from_sparse_contours(
                scanner,
                phantom=phantom,
                plane=plane,
                lateral_m=lateral_m,
                z_m=z_m,
            )
        elif data_type.endswith("pending_digitisation"):
            raise ScatterEngineError(
                f"Scanner '{resolved_key}' has vendor metadata loaded but digitisation is still pending."
            )
        elif data_type == "metadata_only_pending_digitisation":
            raise ScatterEngineError(
                f"Scanner '{resolved_key}' has vendor metadata loaded but digitisation is still pending."
            )
        else:
            raise ScatterEngineError(f"Unsupported geometry data_type: {data_type!r}")

        scaling_factor = self._compute_scaling_factor(
            scanner,
            mAs=mAs,
            kVp=kVp,
            collimation_key=collimation_key,
            aperture_key=aperture_key,
            include_mAs_scaling=(data_type != "protocol_matrix"),
        )

        return ScatterResult(
            scanner_key=scanner_key,
            resolved_scanner_key=resolved_key,
            plane=plane,
            x_m=lateral_m if plane == "horizontal" else None,
            y_m=lateral_m if plane == "vertical" else None,
            z_m=z_m,
            phantom=phantom,
            scatter_uGy=base * scaling_factor,
            scatter_unit_basis=scatter_unit,
            workload_mAs=mAs,
            kVp=kVp,
            scaling_factor=scaling_factor,
            method=method,
            notes=self._build_notes(scanner, data_type),
        )

    def estimate_weekly_kerma_uGy(
        self,
        scanner_key: str,
        *,
        plane: str,
        phantom: str,
        z_m: float,
        lateral_m: float = 0.0,
        scans_per_week: float = 1.0,
        mAs_per_scan: float = 100.0,
        kVp: float = 140.0,
        collimation_key: str | None = None,
        aperture_key: str | None = None,
    ) -> float:
        point = self.estimate_scatter(
            scanner_key,
            plane=plane,
            phantom=phantom,
            z_m=z_m,
            lateral_m=lateral_m,
            mAs=mAs_per_scan,
            kVp=kVp,
            collimation_key=collimation_key,
            aperture_key=aperture_key,
        )
        return point.scatter_uGy * scans_per_week

    def estimate_barrier_incident_uGy_per_week(
        self,
        scanner_key: str,
        *,
        plane: str,
        phantom: str,
        barrier_distance_m: float,
        offset_m: float = 0.0,
        scans_per_week: float = 1.0,
        mAs_per_scan: float = 100.0,
        kVp: float = 140.0,
        use_factor: float = 1.0,
        occupancy_factor: float = 1.0,
        collimation_key: str | None = None,
        aperture_key: str | None = None,
    ) -> float:
        weekly = self.estimate_weekly_kerma_uGy(
            scanner_key,
            plane=plane,
            phantom=phantom,
            z_m=barrier_distance_m,
            lateral_m=offset_m,
            scans_per_week=scans_per_week,
            mAs_per_scan=mAs_per_scan,
            kVp=kVp,
            collimation_key=collimation_key,
            aperture_key=aperture_key,
        )
        return weekly * use_factor * occupancy_factor

    def _build_notes(self, scanner: Mapping[str, Any], data_type: str) -> str:
        if data_type in {"matrix", "sparse_matrix_with_interpolation", "sparse_matrix", "protocol_matrix"}:
            return (
                "Vendor matrix-style geometry used where available; interpolation is applied in-plane "
                "and conservative inverse-square fallback is used outside the measured grid or when the "
                "current family still has empty matrix cells."
            )
        if data_type in {"sparse_iso_contours", "contour_family"}:
            return (
                "Vendor contour-family geometry with conservative anisotropic fallback because the source "
                "provides sparse contour levels rather than a dense matrix."
            )
        return ""

    def _compute_scaling_factor(
        self,
        scanner: Mapping[str, Any],
        *,
        mAs: float,
        kVp: float,
        collimation_key: str | None,
        aperture_key: str | None,
        include_mAs_scaling: bool = True,
    ) -> float:
        normalisation = scanner.get("normalisation", {}) or {}
        ref_mAs = float(normalisation.get("mAs_reference", 100.0))
        factor = (float(mAs) / ref_mAs if ref_mAs else 1.0) if include_mAs_scaling else 1.0

        kVp_factors = {
            float(k): float(v) for k, v in (normalisation.get("kVp_factors", {}) or {}).items()
        }
        if kVp_factors:
            factor *= self._piecewise_linear_lookup(kVp_factors, float(kVp))

        coll_factors = normalisation.get("collimation_factors", {}) or {}
        if collimation_key and collimation_key in coll_factors:
            factor *= float(coll_factors[collimation_key])

        ap_factors = normalisation.get("aperture_factors", {}) or {}
        if aperture_key and aperture_key in ap_factors:
            factor *= float(ap_factors[aperture_key])

        return factor

    def _estimate_from_matrix_geometry(
        self,
        scanner: Mapping[str, Any],
        *,
        plane: str,
        lateral_m: float,
        z_m: float,
    ) -> tuple[float, str]:
        geometry = scanner.get("geometry", {}) or {}
        profiles = scanner.get("profiles", {}) or {}

        # Legacy structure support
        legacy_data_type = geometry.get("data_type")
        if plane in profiles and legacy_data_type == "sparse_matrix_with_interpolation":
            profile = profiles[plane]
            row_key_name = "x_rows" if plane == "horizontal" else "y_rows"
            row_map = profile[row_key_name]
            points = []
            for lateral_key, z_map in row_map.items():
                lat = float(lateral_key)
                for z_key, val in z_map.items():
                    points.append((lat, float(z_key), float(val)))
            return self._estimate_from_point_cloud(points, lateral_m=lateral_m, z_m=z_m)

        # New ingestion structure
        plane_data = (geometry.get("planes", {}) or {}).get(plane)
        if not plane_data:
            raise ScatterEngineError(f"Plane '{plane}' not available for scanner")

        lateral_axis_key = "x_axis_m" if plane == "horizontal" else "y_axis_m"
        lateral_axis = list(plane_data.get(lateral_axis_key, []) or [])
        z_axis = list(plane_data.get("z_axis_m", []) or [])
        values = list(plane_data.get("values", []) or [])

        points = self._matrix_to_points(lateral_axis, z_axis, values)
        if points:
            return self._estimate_from_point_cloud(points, lateral_m=lateral_m, z_m=z_m)

        # Empty matrix currently present in intake example; use conservative fallback.
        fallback = self._fallback_from_scanner_peak(scanner, lateral_m=lateral_m, z_m=z_m, plane=plane)
        return fallback, "matrix_geometry_empty_fallback"

    def _estimate_from_point_cloud(
        self,
        points: Iterable[tuple[float, float, float]],
        *,
        lateral_m: float,
        z_m: float,
    ) -> tuple[float, str]:
        points = list(points)
        if not points:
            raise ScatterEngineError("No matrix points available for interpolation.")

        exact = self._exact_point_lookup(points, lateral_m, z_m)
        if exact is not None:
            return exact, "vendor_exact_table_lookup"

        value = self._idw_interpolate(points, lateral_m, z_m)
        if value is not None:
            return value, "vendor_matrix_idw"

        fallback = self._inverse_square_extrapolation(points, lateral_m, z_m)
        return fallback, "inverse_square_extrapolation"

    def _estimate_from_sparse_contours(
        self,
        scanner: Mapping[str, Any],
        *,
        phantom: str,
        plane: str,
        lateral_m: float,
        z_m: float,
    ) -> tuple[float, str]:
        profiles = scanner.get("profiles", {}) or {}
        if phantom in profiles:
            profile = profiles[phantom]
            iso_levels = sorted(float(v) for v in profile["iso_levels_uGy_per_scan"])
            peak = float(profile["peak_uGy_per_scan"])
        else:
            contour_key = f"{phantom}_{plane}_100mA"
            if contour_key not in profiles:
                fallback_keys = [k for k in profiles.keys() if phantom in str(k)]
                raise ScatterEngineError(
                    f"Phantom '{phantom}' not available. Valid profile keys: {sorted(profiles) if profiles else fallback_keys}"
                )
            profile = profiles[contour_key]
            iso_levels = sorted(float(v) for v in profile.get("contour_levels_uGy_per_scan", []))
            if not iso_levels:
                raise ScatterEngineError(f"No contour levels found for profile '{contour_key}'")
            peak = max(iso_levels)

        radius = max(math.hypot(lateral_m, z_m), 0.25)

        # Conservative profile chosen to preserve the documented peak and contour family.
        # Plane is currently retained for API symmetry and future digitised maps.
        biases = scanner.get("fallback_profile", {}) or {}
        bias = 1.0
        if abs(lateral_m) > abs(z_m):
            bias *= float(biases.get("left_right_bias", 1.0))
        if z_m < 0:
            bias *= float(biases.get("table_side_bias", 1.0))
        if z_m >= 0:
            bias *= float(biases.get("gantry_side_bias", 1.0))
        if plane == "vertical":
            bias *= float(biases.get("front_back_bias", 1.0))

        value = peak * bias / (1.0 + (radius / 0.6) ** 2)
        value = min(value, peak)

        if value < iso_levels[0]:
            return value, "vendor_contour_family_fallback_below_outer_iso"
        return value, "vendor_contour_family_fallback"

    def _fallback_from_scanner_peak(
        self,
        scanner: Mapping[str, Any],
        *,
        lateral_m: float,
        z_m: float,
        plane: str,
    ) -> float:
        peak = self._extract_peak_scatter(scanner)
        if peak <= 0:
            raise ScatterEngineError("Could not infer a fallback peak value from scanner data.")

        radius = max(math.hypot(lateral_m, z_m), 0.25)
        biases = scanner.get("fallback_profile", {}) or {}
        bias = 1.0
        if abs(lateral_m) > abs(z_m):
            bias *= float(biases.get("left_right_bias", 1.0))
        if z_m < 0:
            bias *= float(biases.get("table_side_bias", 1.0))
        if z_m >= 0:
            bias *= float(biases.get("gantry_side_bias", 1.0))
        if plane == "vertical":
            bias *= float(biases.get("front_back_bias", 1.0))

        return min(peak, peak * bias / ((radius / 0.5) ** 2))

    def _extract_peak_scatter(self, scanner: Mapping[str, Any]) -> float:
        peaks = []

        profiles = scanner.get("profiles", {}) or {}
        for profile in profiles.values():
            if isinstance(profile, Mapping) and "peak_uGy_per_scan" in profile:
                try:
                    peaks.append(float(profile["peak_uGy_per_scan"]))
                except Exception:
                    pass

        geometry = scanner.get("geometry", {}) or {}
        planes = geometry.get("planes", {}) or {}
        for plane_data in planes.values():
            values = plane_data.get("values", []) or []
            for row in values:
                if isinstance(row, list):
                    for val in row:
                        if val not in (None, "", "ISO", "Table"):
                            try:
                                peaks.append(float(val))
                            except Exception:
                                pass

        if peaks:
            return max(peaks)

        # Last-resort support for families whose matrix geometry schema is present
        # but whose numeric table cells have not yet been populated.
        resolved_family = self.resolve_scanner_family(str(scanner.get('family', '') or ''))
        if resolved_family in KNOWN_FALLBACK_PEAKS_UGY:
            return float(KNOWN_FALLBACK_PEAKS_UGY[resolved_family])

        # Also try canonical scanner keys by direct match against family / model labels.
        family_label = str(scanner.get('family', '') or '')
        for key, peak in KNOWN_FALLBACK_PEAKS_UGY.items():
            if key == family_label or family_label.endswith(key):
                return float(peak)

        return 0.0

    @staticmethod
    def _matrix_to_points(
        lateral_axis: list[Any],
        z_axis: list[Any],
        values: list[Any],
    ) -> list[tuple[float, float, float]]:
        points: list[tuple[float, float, float]] = []
        if not lateral_axis or not z_axis or not values:
            return points

        for i, lat in enumerate(lateral_axis):
            if i >= len(values) or not isinstance(values[i], list):
                continue
            row = values[i]
            for j, z in enumerate(z_axis):
                if j >= len(row):
                    continue
                val = row[j]
                if val in (None, "", "ISO", "Table"):
                    continue
                try:
                    points.append((float(lat), float(z), float(val)))
                except Exception:
                    continue
        return points

    @staticmethod
    def _exact_point_lookup(
        points: Iterable[tuple[float, float, float]],
        lateral_m: float,
        z_m: float,
    ) -> Optional[float]:
        for lat, z, val in points:
            if abs(lat - lateral_m) < 1e-9 and abs(z - z_m) < 1e-9:
                return val
        return None

    @staticmethod
    def _idw_interpolate(
        points: Iterable[tuple[float, float, float]],
        lateral_m: float,
        z_m: float,
        power: float = 2.0,
    ) -> Optional[float]:
        weighted = 0.0
        total_w = 0.0
        count = 0
        for lat, z, val in points:
            dist = math.hypot(lat - lateral_m, z - z_m)
            if dist < 1e-12:
                return val
            if dist > 1.5:
                continue
            w = 1.0 / (dist ** power)
            weighted += w * val
            total_w += w
            count += 1
        if count < 2 or total_w <= 0:
            return None
        return weighted / total_w

    @staticmethod
    def _inverse_square_extrapolation(
        points: Iterable[tuple[float, float, float]],
        lateral_m: float,
        z_m: float,
    ) -> float:
        peak = max(val for _, _, val in points)
        radius = max(math.hypot(lateral_m, z_m), 0.25)
        return peak / ((radius / 0.5) ** 2)

    @staticmethod
    def _piecewise_linear_lookup(mapping: Mapping[float, float], x: float) -> float:
        xs = sorted(mapping)
        if x <= xs[0]:
            return mapping[xs[0]]
        if x >= xs[-1]:
            return mapping[xs[-1]]
        for lo, hi in zip(xs, xs[1:]):
            if lo <= x <= hi:
                y0 = mapping[lo]
                y1 = mapping[hi]
                if hi == lo:
                    return y0
                frac = (x - lo) / (hi - lo)
                return y0 + frac * (y1 - y0)
        return mapping[xs[-1]]


def load_default_engine() -> CTScatterEngine:
    return CTScatterEngine(DEFAULT_DB_PATH)


if __name__ == "__main__":
    engine = load_default_engine()
    print("Available scanners / aliases:")
    for key in engine.list_scanners():
        print(f" - {key}")

    demo = engine.estimate_scatter(
        "NM/CT 870 CZT",
        plane="horizontal",
        phantom="body",
        lateral_m=0.0,
        z_m=0.5,
        mAs=100,
        kVp=140,
    )
    print("\nDemo lookup:")
    print(demo)
