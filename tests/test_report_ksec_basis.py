from __future__ import annotations

"""
Regression tests for report-facing CT ksec basis.

These tests protect the formal/report interpretation of CT ksec state. They do
not render a PDF. Instead, they test the shared report-ready status fields that
report generation should consume from services.ksec_status.resolve_ksec_status().

Run from project root:

    python -m pytest tests/test_report_ksec_basis.py
"""

from dataclasses import dataclass
from typing import Any

import pytest

from services.ksec_status import resolve_ksec_status


@dataclass
class DummySource:
    name: str
    source_type: str
    params: dict[str, Any]


def _report_ksec_row(src: DummySource) -> dict[str, Any]:
    """
    Small report-facing adapter.

    Keep this intentionally close to the fields the PDF/report generator should
    display, without importing the full report generator or building a PDF.
    """
    status = resolve_ksec_status(src)

    scanner_label = (
        status.get("scanner_model")
        or status.get("scanner_family")
        or src.params.get("scanner_model")
        or src.params.get("scanner_family")
        or "CT scanner"
    )

    return {
        "source_name": src.name,
        "scanner": scanner_label,
        "basis": status["basis"],
        "basis_label": status["basis_label"],
        "status": status["status"],
        "severity": status["severity"],
        "ksec": status["ksec"],
        "ksec_display": status["ksec_display"],
        "source_text": status["source_text"],
        "limitation": status["limitation"],
        "audit_complete": status["audit_complete"],
        "manual_override": status["manual_override"],
        "manual_ksec_entered_by": status["manual_ksec_entered_by"],
        "manual_ksec_reason": status["manual_ksec_reason"],
        "manual_ksec_source_reference": status["manual_ksec_source_reference"],
        "manual_ksec_last_updated": status["manual_ksec_last_updated"],
    }


def _ge_apex_database_source() -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "ksec_mGy_per_100mAs_at_1m": "0.0457",
            "manual_ksec_override": "0",
            "scanner_source": "GE / GE Revolution Apex / Apex Elite -> JSON worst-case Ksec lookup (GE_REVOLUTION_APEX_FAMILY)",
        },
    )


def _philips_brilliance_null_source() -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "NULL ksec — manual override required",
        },
    )


def _philips_brilliance_manual_source(*, audit_complete: bool = True) -> DummySource:
    return DummySource(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "ksec_mGy_per_100mAs_at_1m": "0.015",
            "manual_ksec_override": "1",
            "manual_ksec_entered_by": "Test Physicist",
            "manual_ksec_reason": "Vendor manual extract" if audit_complete else "",
            "manual_ksec_source_reference": "Philips document XYZ, page 12" if audit_complete else "",
            "manual_ksec_last_updated": "2026-05-21 10:30",
            "scanner_source": "Manual override entered in Sources tab",
        },
    )


def test_report_basis_database_ksec_is_database_pass():
    row = _report_ksec_row(_ge_apex_database_source())

    assert row["scanner"] == "GE Revolution Apex / Apex Elite"
    assert row["basis"] == "database"
    assert row["basis_label"] == "Database"
    assert row["status"] == "PASS"
    assert row["severity"] == "info"
    assert row["ksec"] == pytest.approx(0.0457)
    assert row["ksec_display"] == "0.0457 mGy/100 mAs @ 1 m"
    assert row["audit_complete"] is True
    assert row["manual_override"] is False
    assert row["limitation"] == ""
    assert "JSON worst-case Ksec lookup" in row["source_text"]


def test_report_basis_null_ksec_is_manual_override_required_fail():
    row = _report_ksec_row(_philips_brilliance_null_source())

    assert row["scanner"] == "Philips Brilliance 64"
    assert row["basis"] == "manual_override_required"
    assert row["basis_label"] == "Manual override required"
    assert row["status"] == "FAIL"
    assert row["severity"] == "critical"
    assert row["ksec"] is None
    assert row["ksec_display"] == ""
    assert row["audit_complete"] is False
    assert row["manual_override"] is False
    assert "manual override" in row["limitation"].lower()
    assert "incomplete" in row["limitation"].lower()


def test_report_basis_manual_override_with_audit_is_review_and_includes_audit_fields():
    row = _report_ksec_row(_philips_brilliance_manual_source(audit_complete=True))

    assert row["scanner"] == "Philips Brilliance 64"
    assert row["basis"] == "manual_override"
    assert row["basis_label"] == "Manual override"
    assert row["status"] == "REVIEW"
    assert row["severity"] == "warning"
    assert row["ksec"] == pytest.approx(0.015)
    assert row["ksec_display"] == "0.015 mGy/100 mAs @ 1 m"
    assert row["manual_override"] is True
    assert row["audit_complete"] is True
    assert row["manual_ksec_entered_by"] == "Test Physicist"
    assert row["manual_ksec_reason"] == "Vendor manual extract"
    assert row["manual_ksec_source_reference"] == "Philips document XYZ, page 12"
    assert row["manual_ksec_last_updated"] == "2026-05-21 10:30"
    assert "Manual CT scatter ksec override used" in row["limitation"]


def test_report_basis_manual_override_without_audit_warns_audit_incomplete():
    row = _report_ksec_row(_philips_brilliance_manual_source(audit_complete=False))

    assert row["basis"] == "manual_override"
    assert row["status"] == "REVIEW"
    assert row["severity"] == "warning"
    assert row["manual_override"] is True
    assert row["audit_complete"] is False
    assert "audit trail is incomplete" in row["limitation"]


def test_report_basis_must_not_show_conservative_default_as_database():
    src = DummySource(
        name="Secondary scatter source diagnostic",
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

    row = _report_ksec_row(src)

    assert row["basis"] == "manual_override_required"
    assert row["status"] == "FAIL"
    assert row["ksec"] is None
    assert row["basis_label"] != "Database"
    assert "0.06" not in row["ksec_display"]


def test_report_basis_aliases_are_present_for_report_compatibility():
    status = resolve_ksec_status(_ge_apex_database_source())

    # These aliases are useful for older report/preflight code paths.
    assert status["scanner_source"] == status["source_text"]
    assert status["ksec_source"] == status["source_text"]
    assert status["ksec_confidence"] == status["severity"]


def test_report_non_ct_source_is_pass_not_applicable():
    src = DummySource(
        name="NM Patient",
        source_type="nm_patient",
        params={
            "radionuclide": "Tc99m",
        },
    )

    row = _report_ksec_row(src)

    assert row["basis"] == "not_applicable"
    assert row["basis_label"] == "Not applicable"
    assert row["status"] == "PASS"
    assert row["severity"] == "info"
    assert row["ksec"] is None
    assert row["limitation"] == ""
    assert row["audit_complete"] is True
