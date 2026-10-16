from __future__ import annotations

"""
Regression tests for CT ksec workflow.

These tests deliberately avoid Tkinter. They lock down the safety-critical model
and service behaviour that previously regressed:

1. Database ksec scanner -> PASS/database
2. NULL ksec scanner -> FAIL/manual override required
3. NULL ksec scanner + manual override -> REVIEW/manual override
4. Conservative/default ksec wording must not be treated as database truth
5. Project-level sources remain the source of truth conceptually

Run from project root:

    pytest tests/test_ct_ksec_workflow.py
"""

from dataclasses import dataclass
from typing import Any

import pytest

from services.ksec_status import resolve_ksec_status
from services.ct_scanner_service import CTScannerService
from services.ct_scanner_resolution import CTScannerResolutionService


@dataclass
class DummySource:
    source_type: str
    params: dict[str, Any]


class DummyScatterEngine:
    """Small stand-in for CTScatterEngine used by CTScannerService tests."""

    def __init__(self, scanners: dict[str, dict[str, Any]]):
        self.scanners = scanners

    def list_scanners(self) -> list[str]:
        return list(self.scanners.keys())

    def get_scanner(self, family_key: str) -> dict[str, Any]:
        return self.scanners[family_key]

    def resolve_scanner_family(self, label: str) -> str:
        text = str(label or "").strip().lower()

        if "brilliance" in text:
            return "PHILIPS_BRILLIANCE_64"

        if "apex" in text:
            return "GE_REVOLUTION_APEX_FAMILY"

        raise KeyError(label)


@pytest.fixture()
def raw_ct_database() -> dict[str, Any]:
    return {
        "scanner_families": {
            "GE_REVOLUTION_APEX_FAMILY": {
                "vendor": "GE",
                "short_name": "Revolution Apex / Apex Elite",
                "description": "GE Revolution Apex / Apex Elite diagnostic CT family.",
                "ct_scanner_metadata": "ct_standalone_diagnostic",
                "worst_case_ksec_mGy_per_100mAs_at_1m": 0.0457,
                "profiles": {
                    "body": {},
                },
            },
            "PHILIPS_BRILLIANCE_64": {
                "vendor": "Philips",
                "short_name": "Brilliance 64",
                "description": "Philips Brilliance 64 diagnostic CT.",
                "ct_scanner_metadata": "ct_standalone_diagnostic",
                "worst_case_ksec_mGy_per_100mAs_at_1m": None,
                "profiles": {
                    "body": {},
                },
            },
            "GE_NMCT_LOW_DOSE": {
                "vendor": "GE",
                "short_name": "NM/CT 670/870",
                "description": "GE hybrid low-dose CT component.",
                "ct_scanner_metadata": "hybrid_ct_component_attenuation_correction",
                "worst_case_ksec_mGy_per_100mAs_at_1m": 0.001,
                "profiles": {
                    "body": {},
                },
            },
        }
    }


@pytest.fixture()
def ct_service(raw_ct_database: dict[str, Any]) -> CTScannerService:
    engine = DummyScatterEngine(raw_ct_database["scanner_families"])
    return CTScannerService(raw_database=raw_ct_database, engine=engine)


def test_ct_scanner_service_is_compatibility_facade_for_canonical_resolver(ct_service: CTScannerService):
    """Legacy service must delegate scanner resolution to the canonical implementation."""
    assert isinstance(ct_service, CTScannerResolutionService)
    assert ct_service.engine is ct_service.ct_scatter_engine


def test_ct_scanner_service_configure_updates_canonical_engine(raw_ct_database: dict[str, Any]):
    first_engine = DummyScatterEngine(raw_ct_database["scanner_families"])
    service = CTScannerService(raw_database=raw_ct_database, engine=first_engine)

    replacement_engine = DummyScatterEngine(raw_ct_database["scanner_families"])
    service.configure(engine=replacement_engine)

    assert service.engine is replacement_engine
    assert service.ct_scatter_engine is replacement_engine
    assert service.family_values("ct_scatter") == [
        "GE_REVOLUTION_APEX_FAMILY",
        "PHILIPS_BRILLIANCE_64",
    ]


def test_ct_scanner_service_filters_standalone_ct_only(ct_service: CTScannerService):
    values = ct_service.family_values("ct_scatter")

    assert "GE_REVOLUTION_APEX_FAMILY" in values
    assert "PHILIPS_BRILLIANCE_64" in values
    assert "GE_NMCT_LOW_DOSE" not in values


def test_ct_scanner_service_filters_hybrid_ct_only(ct_service: CTScannerService):
    values = ct_service.family_values("spect_ct_secondary_scatter")

    assert "GE_NMCT_LOW_DOSE" in values
    assert "GE_REVOLUTION_APEX_FAMILY" not in values
    assert "PHILIPS_BRILLIANCE_64" not in values


def test_ct_scanner_service_display_mapping_resolves_philips_brilliance(ct_service: CTScannerService):
    mapping = ct_service.display_to_family_map("ct_scatter")

    assert mapping["Philips Brilliance 64"] == "PHILIPS_BRILLIANCE_64"
    assert ct_service.family_from_display("ct_scatter", "Philips Brilliance 64") == "PHILIPS_BRILLIANCE_64"


def test_ct_scanner_service_json_worst_case_ksec_database_value(ct_service: CTScannerService):
    value, source_text = ct_service.json_worst_case_ksec_per_100mAs(
        "GE_REVOLUTION_APEX_FAMILY",
        140,
    )

    assert value == pytest.approx(0.0457)
    assert "JSON worst-case Ksec lookup" in source_text
    assert "GE_REVOLUTION_APEX_FAMILY" in source_text


def test_ct_scanner_service_json_null_ksec_returns_none(ct_service: CTScannerService):
    value, source_text = ct_service.json_worst_case_ksec_per_100mAs(
        "PHILIPS_BRILLIANCE_64",
        140,
    )

    assert value is None
    assert source_text == ""


def test_ksec_status_database_value_passes():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "manual_ksec_override": "0",
            "scanner_source": "GE / GE Revolution Apex / Apex Elite -> JSON worst-case Ksec lookup (GE_REVOLUTION_APEX_FAMILY)",
        },
    )

    status = resolve_ksec_status(src)

    assert status["is_ct_scatter"] is True
    assert status["basis"] == "database"
    assert status["status"] == "PASS"
    assert status["severity"] == "info"
    assert status["ksec"] == pytest.approx(0.0457)
    assert status["audit_complete"] is True
    assert status["manual_override"] is False


@pytest.mark.parametrize("missing_value", ["", None, "NULL", "null", "None", 0, -1])
def test_ksec_status_null_or_invalid_value_fails(missing_value):
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": missing_value,
            "manual_ksec_override": "0",
            "scanner_source": "NULL ksec — manual override required",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override_required"
    assert status["status"] == "FAIL"
    assert status["severity"] == "critical"
    assert status["ksec"] is None
    assert status["audit_complete"] is False
    assert "manual override" in status["message"].lower()


def test_ksec_status_manual_override_with_audit_is_review():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "manual_ksec_override": "1",
            "manual_ksec_entered_by": "Test Physicist",
            "manual_ksec_reason": "Vendor manual extract",
            "manual_ksec_source_reference": "Philips document XYZ, page 12",
            "manual_ksec_last_updated": "2026-05-21 10:30",
            "scanner_source": "NULL ksec — manual override required",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override"
    assert status["basis_label"] == "Manual override"
    assert status["status"] == "REVIEW"
    assert status["severity"] == "warning"
    assert status["ksec"] == pytest.approx(0.015)
    assert status["audit_complete"] is True
    assert status["manual_override"] is True
    assert status["manual_ksec_entered_by"] == "Test Physicist"
    assert status["manual_ksec_reason"] == "Vendor manual extract"
    assert status["manual_ksec_source_reference"] == "Philips document XYZ, page 12"


def test_ksec_status_manual_override_without_audit_is_review_but_incomplete():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "manual_ksec_override": "1",
            "manual_ksec_entered_by": "",
            "manual_ksec_reason": "",
            "manual_ksec_source_reference": "",
            "manual_ksec_last_updated": "2026-05-21 10:30",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override"
    assert status["status"] == "REVIEW"
    assert status["severity"] == "warning"
    assert status["audit_complete"] is False
    assert "audit trail is incomplete" in status["limitation"]


def test_ksec_status_does_not_accept_conservative_default_as_database_truth():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "Conservative default 140 kVp",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override_required"
    assert status["status"] == "FAIL"
    assert status["ksec"] is None


def test_non_ct_source_is_not_blocked_by_ksec_status():
    src = DummySource(
        source_type="nm_patient",
        params={
            "radionuclide": "Tc99m",
        },
    )

    status = resolve_ksec_status(src)

    assert status["is_ct_scatter"] is False
    assert status["basis"] == "not_applicable"
    assert status["status"] == "PASS"
    assert status["audit_complete"] is True


def test_project_sources_conceptual_source_of_truth_for_manual_override():
    """
    Lightweight guard for the source-of-truth concept without importing Tk app.

    If a manual override is present on the project-level source object, the
    shared ksec resolver must classify it as manual override regardless of any
    hypothetical stale room cache.
    """
    project_source = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": 0.015,
            "manual_ksec_override": "1",
            "manual_ksec_reason": "Manual test override",
        },
    )

    stale_room_cache_source = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
        },
    )

    project_status = resolve_ksec_status(project_source)
    stale_status = resolve_ksec_status(stale_room_cache_source)

    assert project_status["basis"] == "manual_override"
    assert project_status["status"] == "REVIEW"

    assert stale_status["basis"] == "manual_override_required"
    assert stale_status["status"] == "FAIL"
