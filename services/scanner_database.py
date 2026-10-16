"""
scanner_database.py

Central access layer for CT / SPECT-CT scanner scatter ksec data.

This module is intentionally UI-independent.  It should be imported by tabs,
calculation logic, validators, and report-generation code rather than having
those components read ct_scatter_master_database.json directly.

Expected database structure:
    - scanner_families: dict[family_id, scanner_record]
    - aliases: dict[display_name_or_alias, family_id]
    - sources: list[source_record]
    - ct_scanner_metadata_groups: dict[group_name, list[family_id]]

Primary ksec field:
    worst_case_ksec_mGy_per_100mAs_at_1m

A null ksec is valid and means:
    - the scanner exists in the database
    - ksec is pending / unavailable
    - calculation should require a manual override before final shielding output
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json


KSEC_FIELD = "worst_case_ksec_mGy_per_100mAs_at_1m"
DEFAULT_REFERENCE_DISTANCE_M = 1.0
DEFAULT_MAS_REFERENCE = 100.0


class ScannerDatabaseError(Exception):
    """Base exception for scanner database errors."""


class ScannerNotFoundError(ScannerDatabaseError):
    """Raised when a scanner family ID or alias cannot be resolved."""


class ScannerDatabaseFormatError(ScannerDatabaseError):
    """Raised when the scanner database JSON is structurally invalid."""


@dataclass(frozen=True)
class ScannerSource:
    family_id: str
    document_name: str | None
    reference_type: str | None


@dataclass(frozen=True)
class ScannerRecord:
    family_id: str
    vendor: str
    short_name: str
    modality_class: str
    description: str
    ksec_mGy_per_100mAs_at_1m: float | None
    ksec_definition: str | None
    ksec_source: str | None
    ksec_confidence: str | None
    canonical_scatter_unit: str | None
    ksec_reference_distance_m: float
    mAs_reference: float
    ct_scanner_metadata: str | None
    sources: tuple[ScannerSource, ...]
    raw: dict[str, Any]

    @property
    def has_ksec(self) -> bool:
        return self.ksec_mGy_per_100mAs_at_1m is not None

    @property
    def requires_manual_ksec(self) -> bool:
        return self.ksec_mGy_per_100mAs_at_1m is None

    @property
    def ksec_display(self) -> str:
        if self.ksec_mGy_per_100mAs_at_1m is None:
            return "NULL"
        return f"{self.ksec_mGy_per_100mAs_at_1m:.6g}"

    @property
    def source_document_display(self) -> str:
        docs = [s.document_name for s in self.sources if s.document_name]
        if not docs:
            return "—"
        return "; ".join(dict.fromkeys(docs))

    @property
    def calculation_status(self) -> str:
        if self.has_ksec:
            return "ready"
        return "manual_ksec_required"

    def to_table_row(self) -> dict[str, Any]:
        """Return a flat dict suitable for tables, reports, or CSV export."""
        return {
            "family_id": self.family_id,
            "vendor": self.vendor,
            "short_name": self.short_name,
            "modality_class": self.modality_class,
            "ksec_mGy_per_100mAs_at_1m": self.ksec_mGy_per_100mAs_at_1m,
            "ksec_display": self.ksec_display,
            "ksec_source": self.ksec_source,
            "ksec_confidence": self.ksec_confidence,
            "ksec_definition": self.ksec_definition,
            "reference_distance_m": self.ksec_reference_distance_m,
            "mAs_reference": self.mAs_reference,
            "metadata_group": self.ct_scanner_metadata,
            "source_documents": self.source_document_display,
            "calculation_status": self.calculation_status,
        }


class ScannerDatabase:
    """Read-only access layer for scanner ksec data."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.data = self._load_json(self.database_path)

        self.scanner_families: dict[str, dict[str, Any]] = self._require_dict(
            self.data, "scanner_families"
        )
        self.aliases: dict[str, str] = self._require_dict(self.data, "aliases", allow_empty=True)
        self.sources: list[dict[str, Any]] = self._require_list(self.data, "sources", allow_empty=True)
        self.metadata_groups: dict[str, list[str]] = self._require_dict(
            self.data, "ct_scanner_metadata_groups", allow_empty=True
        )

        self._source_index = self._build_source_index(self.sources)
        self._alias_index = self._build_alias_index(self.aliases)
        self._validate_minimum_structure()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Scanner database not found: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ScannerDatabaseFormatError(
                f"Invalid scanner database JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise ScannerDatabaseFormatError("Scanner database root must be a JSON object.")
        return data

    @staticmethod
    def _require_dict(
        data: dict[str, Any], key: str, *, allow_empty: bool = False
    ) -> dict[str, Any]:
        value = data.get(key)
        if not isinstance(value, dict):
            raise ScannerDatabaseFormatError(f"'{key}' must be a JSON object.")
        if not allow_empty and not value:
            raise ScannerDatabaseFormatError(f"'{key}' must not be empty.")
        return value

    @staticmethod
    def _require_list(
        data: dict[str, Any], key: str, *, allow_empty: bool = False
    ) -> list[dict[str, Any]]:
        value = data.get(key)
        if not isinstance(value, list):
            raise ScannerDatabaseFormatError(f"'{key}' must be a JSON array.")
        if not allow_empty and not value:
            raise ScannerDatabaseFormatError(f"'{key}' must not be empty.")
        return value

    @staticmethod
    def _normalise_lookup_text(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    @classmethod
    def _build_alias_index(cls, aliases: dict[str, str]) -> dict[str, str]:
        index: dict[str, str] = {}
        for alias, family_id in aliases.items():
            if isinstance(alias, str) and isinstance(family_id, str):
                index[cls._normalise_lookup_text(alias)] = family_id
        return index

    @staticmethod
    def _build_source_index(sources: Iterable[dict[str, Any]]) -> dict[str, list[ScannerSource]]:
        index: dict[str, list[ScannerSource]] = {}
        for item in sources:
            family_id = item.get("family_id")
            if not isinstance(family_id, str) or not family_id:
                continue
            source = ScannerSource(
                family_id=family_id,
                document_name=item.get("document_name"),
                reference_type=item.get("reference_type"),
            )
            index.setdefault(family_id, []).append(source)
        return index

    def _validate_minimum_structure(self) -> None:
        required_fields = [
            "vendor",
            "modality_class",
            "description",
            "short_name",
            KSEC_FIELD,
        ]

        for family_id, record in self.scanner_families.items():
            if not isinstance(record, dict):
                raise ScannerDatabaseFormatError(
                    f"Scanner family '{family_id}' must be a JSON object."
                )

            missing = [field for field in required_fields if field not in record]
            if missing:
                raise ScannerDatabaseFormatError(
                    f"Scanner family '{family_id}' is missing required field(s): {', '.join(missing)}"
                )

            ksec = record.get(KSEC_FIELD)
            if ksec is not None and not isinstance(ksec, (int, float)):
                raise ScannerDatabaseFormatError(
                    f"Scanner family '{family_id}' has invalid ksec value: {ksec!r}"
                )

    def resolve_family_id(self, scanner_name_or_family_id: str) -> str:
        """
        Resolve a scanner family ID from either:
            - exact family ID
            - alias
            - short_name
            - case-insensitive / whitespace-normalised equivalent
        """
        if not scanner_name_or_family_id or not scanner_name_or_family_id.strip():
            raise ScannerNotFoundError("Scanner name/family ID is empty.")

        query = scanner_name_or_family_id.strip()

        if query in self.scanner_families:
            return query

        normalised_query = self._normalise_lookup_text(query)

        alias_match = self._alias_index.get(normalised_query)
        if alias_match in self.scanner_families:
            return alias_match
        
        # Common UI display pattern: "Vendor Short Name"
        # Example: "GE Revolution Apex / Apex Elite"
        # Database short_name may be "Revolution Apex / Apex Elite".
        for family_id, record in self.scanner_families.items():
            vendor = str(record.get("vendor", "") or "").strip()
            short_name = str(record.get("short_name", "") or "").strip()

            if vendor and short_name:
                vendor_short = self._normalise_lookup_text(f"{vendor} {short_name}")
                if vendor_short == normalised_query:
                    return family_id

                # GE HealthCare is often displayed as just "GE"
                if vendor.lower() in {"ge healthcare", "ge"}:
                    ge_short = self._normalise_lookup_text(f"GE {short_name}")
                    if ge_short == normalised_query:
                        return family_id

                # Siemens Healthineers is often displayed as just "Siemens"
                if vendor.lower() in {"siemens healthineers", "siemens"}:
                    siemens_short = self._normalise_lookup_text(f"Siemens {short_name}")
                    if siemens_short == normalised_query:
                        return family_id


        for family_id, record in self.scanner_families.items():
            if self._normalise_lookup_text(family_id) == normalised_query:
                return family_id

            short_name = record.get("short_name")
            if isinstance(short_name, str) and self._normalise_lookup_text(short_name) == normalised_query:
                return family_id

            description = record.get("description")
            if isinstance(description, str) and self._normalise_lookup_text(description) == normalised_query:
                return family_id

        raise ScannerNotFoundError(f"Scanner not found: {scanner_name_or_family_id}")

    def get_scanner(self, scanner_name_or_family_id: str) -> ScannerRecord:
        family_id = self.resolve_family_id(scanner_name_or_family_id)
        record = self.scanner_families[family_id]
        normalisation = record.get("normalisation") or {}

        return ScannerRecord(
            family_id=family_id,
            vendor=str(record.get("vendor", "")),
            short_name=str(record.get("short_name", family_id)),
            modality_class=str(record.get("modality_class", "")),
            description=str(record.get("description", "")),
            ksec_mGy_per_100mAs_at_1m=record.get(KSEC_FIELD),
            ksec_definition=record.get("ksec_definition"),
            ksec_source=record.get("ksec_source"),
            ksec_confidence=record.get("ksec_confidence"),
            canonical_scatter_unit=record.get("canonical_scatter_unit"),
            ksec_reference_distance_m=float(
                record.get("ksec_reference_distance_m", DEFAULT_REFERENCE_DISTANCE_M)
            ),
            mAs_reference=float(normalisation.get("mAs_reference", DEFAULT_MAS_REFERENCE)),
            ct_scanner_metadata=record.get("ct_scanner_metadata"),
            sources=tuple(self._source_index.get(family_id, [])),
            raw=record,
        )

    def list_scanners(
        self,
        *,
        include_null_ksec: bool = True,
        vendor: str | None = None,
        modality_class: str | None = None,
        metadata_group: str | None = None,
        sort: bool = True,
    ) -> list[ScannerRecord]:
        scanners: list[ScannerRecord] = []

        for family_id in self.scanner_families:
            scanner = self.get_scanner(family_id)

            if not include_null_ksec and scanner.ksec_mGy_per_100mAs_at_1m is None:
                continue

            if vendor and self._normalise_lookup_text(scanner.vendor) != self._normalise_lookup_text(vendor):
                continue

            if modality_class and scanner.modality_class != modality_class:
                continue

            if metadata_group and scanner.ct_scanner_metadata != metadata_group:
                continue

            scanners.append(scanner)

        if sort:
            scanners.sort(key=lambda s: (s.modality_class, s.vendor, s.short_name))

        return scanners

    def list_table_rows(self, **filters: Any) -> list[dict[str, Any]]:
        return [scanner.to_table_row() for scanner in self.list_scanners(**filters)]

    def list_scanners_by_group(self) -> dict[str, list[ScannerRecord]]:
        grouped: dict[str, list[ScannerRecord]] = {}
        for group_name, family_ids in self.metadata_groups.items():
            group_scanners: list[ScannerRecord] = []
            for family_id in family_ids:
                if family_id in self.scanner_families:
                    group_scanners.append(self.get_scanner(family_id))
            group_scanners.sort(key=lambda s: (s.vendor, s.short_name))
            grouped[group_name] = group_scanners
        return grouped

    def list_vendors(self) -> list[str]:
        vendors = {self.get_scanner(family_id).vendor for family_id in self.scanner_families}
        return sorted(vendors)

    def list_aliases_for_family(self, scanner_name_or_family_id: str) -> list[str]:
        family_id = self.resolve_family_id(scanner_name_or_family_id)
        aliases = [alias for alias, target in self.aliases.items() if target == family_id]
        return sorted(aliases, key=str.casefold)

    def get_ksec(self, scanner_name_or_family_id: str) -> float | None:
        return self.get_scanner(scanner_name_or_family_id).ksec_mGy_per_100mAs_at_1m

    def scanner_requires_manual_ksec(self, scanner_name_or_family_id: str) -> bool:
        return self.get_scanner(scanner_name_or_family_id).requires_manual_ksec

    def get_calculation_ksec(
        self,
        scanner_name_or_family_id: str,
        *,
        manual_override: float | None = None,
    ) -> float:
        """
        Return the ksec to use for calculation.

        Rules:
            - database ksec wins when present
            - manual override is required only when database ksec is null
            - manual override must be positive
        """
        scanner = self.get_scanner(scanner_name_or_family_id)

        if scanner.ksec_mGy_per_100mAs_at_1m is not None:
            return float(scanner.ksec_mGy_per_100mAs_at_1m)

        if manual_override is None:
            raise ValueError(
                f"Scanner '{scanner.short_name}' has NULL ksec. Manual ksec override is required."
            )

        if manual_override <= 0:
            raise ValueError("Manual ksec override must be greater than zero.")

        return float(manual_override)

    def get_report_ksec_basis(
        self,
        scanner_name_or_family_id: str,
        *,
        manual_override: float | None = None,
    ) -> dict[str, Any]:
        """
        Return a report-ready description of the scanner ksec basis.

        This keeps report_generator.py from needing to understand the raw JSON.
        """
        scanner = self.get_scanner(scanner_name_or_family_id)

        if scanner.has_ksec:
            ksec_for_calculation = scanner.ksec_mGy_per_100mAs_at_1m
            basis = "database"
            limitation = None
        else:
            ksec_for_calculation = manual_override
            basis = "manual_override_required" if manual_override is None else "manual_override"
            limitation = (
                "Database ksec is NULL for this scanner. Final shielding calculations require "
                "a documented manual ksec override before issue."
                if manual_override is None
                else "Database ksec was NULL; calculation used a documented manual ksec override."
            )

        return {
            "family_id": scanner.family_id,
            "scanner": scanner.short_name,
            "vendor": scanner.vendor,
            "modality_class": scanner.modality_class,
            "ksec_mGy_per_100mAs_at_1m": ksec_for_calculation,
            "database_ksec_mGy_per_100mAs_at_1m": scanner.ksec_mGy_per_100mAs_at_1m,
            "basis": basis,
            "ksec_definition": scanner.ksec_definition,
            "ksec_source": scanner.ksec_source,
            "ksec_confidence": scanner.ksec_confidence,
            "reference_distance_m": scanner.ksec_reference_distance_m,
            "mAs_reference": scanner.mAs_reference,
            "source_documents": scanner.source_document_display,
            "limitation": limitation,
        }

    def validate_references(self) -> list[str]:
        """
        Return non-fatal database consistency warnings.

        This is deliberately warning-based so development can continue while
        Philips / other vendor source gaps are still being filled.
        """
        warnings: list[str] = []

        for alias, family_id in self.aliases.items():
            if family_id not in self.scanner_families:
                warnings.append(f"Alias '{alias}' points to missing family_id '{family_id}'.")

        for group_name, family_ids in self.metadata_groups.items():
            if not isinstance(family_ids, list):
                warnings.append(f"Metadata group '{group_name}' must contain a list of family IDs.")
                continue
            for family_id in family_ids:
                if family_id not in self.scanner_families:
                    warnings.append(
                        f"Metadata group '{group_name}' includes missing family_id '{family_id}'."
                    )

        source_family_ids = set(self._source_index)
        for family_id in self.scanner_families:
            if family_id not in source_family_ids:
                warnings.append(f"Scanner family '{family_id}' has no source document entry.")

        for family_id in source_family_ids:
            if family_id not in self.scanner_families:
                warnings.append(f"Source entry points to missing family_id '{family_id}'.")

        return warnings


# Convenience functions for simple imports -------------------------------------------------


def load_scanner_database(database_path: str | Path) -> ScannerDatabase:
    return ScannerDatabase(database_path)


def get_scanner_family(database_path: str | Path, scanner_name_or_family_id: str) -> ScannerRecord:
    return ScannerDatabase(database_path).get_scanner(scanner_name_or_family_id)


def resolve_scanner_alias(database_path: str | Path, scanner_name_or_family_id: str) -> str:
    return ScannerDatabase(database_path).resolve_family_id(scanner_name_or_family_id)


def get_ksec_for_scanner(database_path: str | Path, scanner_name_or_family_id: str) -> float | None:
    return ScannerDatabase(database_path).get_ksec(scanner_name_or_family_id)


def scanner_requires_manual_ksec(database_path: str | Path, scanner_name_or_family_id: str) -> bool:
    return ScannerDatabase(database_path).scanner_requires_manual_ksec(scanner_name_or_family_id)


if __name__ == "__main__":
    # Lightweight smoke test / developer preview.
    # Run from project root, adjusting the path if your JSON lives elsewhere:
    #     python scanner_database.py
    db_path = Path(__file__).resolve().parents[1] / "data" / "ct" / "ct_scatter_master_database.json"
    db = ScannerDatabase(db_path)

    rows = db.list_table_rows()
    print(f"Loaded {len(rows)} scanner families from {db_path}")

    null_rows = [row for row in rows if row["ksec_mGy_per_100mAs_at_1m"] is None]
    print(f"Scanners with NULL ksec: {len(null_rows)}")

    for row in null_rows:
        print(f"  - {row['vendor']} | {row['short_name']} | {row['family_id']}")

    warnings = db.validate_references()
    if warnings:
        print("\nValidation warnings:")
        for warning in warnings:
            print(f"  - {warning}")
