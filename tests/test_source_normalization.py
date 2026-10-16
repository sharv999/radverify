from __future__ import annotations

"""
Regression tests for source parameter normalisation.

These tests lock down a safety-critical rule:

    normalize_source_params() must not silently wipe CT scanner identity,
    NULL-ksec state, manual ksec override fields, or audit trail fields.

Run from project root:

    python -m pytest tests/test_source_normalization.py
"""

from typing import Any

import pytest

from engine.normalization import normalize_source_params


CT_TYPES = [
    "ct_scatter",
    "spect_ct_secondary_scatter",
]


@pytest.mark.parametrize("source_type", CT_TYPES)
def test_ct_normalization_preserves_manual_ksec_override_and_audit_fields(source_type: str):
    params: dict[str, Any] = {
        "preset": "ct_low_dose",
        "scanner_vendor": "Philips",
        "scanner_model": "Philips Brilliance 64",
        "scanner_family": "PHILIPS_BRILLIANCE_64",
        "scanner_phantom": "body",
        "scanner_kvp": "140",
        "scanner_source": "NULL ksec — manual override required",
        "scanner_debug": "Philips | Philips Brilliance 64 | PHILIPS_BRILLIANCE_64 | NULL ksec",
        "scans_per_week": "60",
        "workload_mAs_per_scan": "630",
        "ksec_mGy_per_100mAs_at_1m": "0.015",
        "manual_ksec_override": "1",
        "manual_ksec_entered_by": "Test Physicist",
        "manual_ksec_reason": "Vendor manual extract",
        "manual_ksec_reference": "Philips document XYZ page 12",
        "manual_ksec_source_reference": "Philips document XYZ page 12",
        "manual_ksec_last_updated": "2026-05-21 10:30",
    }

    normalized = normalize_source_params(source_type, params)

    assert normalized["scanner_vendor"] == "Philips"
    assert normalized["scanner_model"] == "Philips Brilliance 64"
    assert normalized["scanner_family"] == "PHILIPS_BRILLIANCE_64"
    assert normalized["scanner_phantom"] == "body"
    assert str(normalized["scanner_kvp"]) == "140"

    assert str(normalized["ksec_mGy_per_100mAs_at_1m"]) in {"0.015", "0.0150"}
    assert str(normalized["manual_ksec_override"]) == "1"
    assert normalized["manual_ksec_entered_by"] == "Test Physicist"
    assert normalized["manual_ksec_reason"] == "Vendor manual extract"
    assert normalized["manual_ksec_reference"] == "Philips document XYZ page 12"
    assert normalized["manual_ksec_source_reference"] == "Philips document XYZ page 12"
    assert normalized["manual_ksec_last_updated"] == "2026-05-21 10:30"


@pytest.mark.parametrize("source_type", CT_TYPES)
def test_ct_normalization_preserves_null_ksec_as_missing_not_default(source_type: str):
    params: dict[str, Any] = {
        "scanner_vendor": "Philips",
        "scanner_model": "Philips Brilliance 64",
        "scanner_family": "PHILIPS_BRILLIANCE_64",
        "scanner_phantom": "body",
        "scanner_kvp": "140",
        "scanner_source": "NULL ksec — manual override required",
        "scans_per_week": "60",
        "workload_mAs_per_scan": "630",
        "ksec_mGy_per_100mAs_at_1m": "",
        "manual_ksec_override": "0",
    }

    normalized = normalize_source_params(source_type, params)

    assert normalized["scanner_family"] == "PHILIPS_BRILLIANCE_64"
    assert normalized["manual_ksec_override"] in {"0", 0, False, ""}
    assert normalized.get("ksec_mGy_per_100mAs_at_1m", "") in {"", None}

    # The old conservative fallback was 0.06. Normalisation must not reintroduce it.
    assert normalized.get("ksec_mGy_per_100mAs_at_1m") != 0.06
    assert normalized.get("ksec_mGy_per_100mAs_at_1m") != "0.06"


@pytest.mark.parametrize("source_type", CT_TYPES)
def test_ct_normalization_preserves_workload_fields(source_type: str):
    params: dict[str, Any] = {
        "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
        "scans_per_week": "123",
        "workload_mAs_per_scan": "456",
        "ksec_mGy_per_100mAs_at_1m": "0.0457",
    }

    normalized = normalize_source_params(source_type, params)

    assert float(normalized["scans_per_week"]) == pytest.approx(123)
    assert float(normalized["workload_mAs_per_scan"]) == pytest.approx(456)
    assert float(normalized["ksec_mGy_per_100mAs_at_1m"]) == pytest.approx(0.0457)


@pytest.mark.parametrize("source_type", CT_TYPES)
def test_ct_normalization_adds_expected_defaults_without_overwriting_existing_identity(source_type: str):
    params: dict[str, Any] = {
        "scanner_vendor": "GE",
        "scanner_model": "GE Revolution Apex / Apex Elite",
        "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
        "scanner_phantom": "body",
        "scans_per_week": "80",
        "workload_mAs_per_scan": "700",
        "ksec_mGy_per_100mAs_at_1m": "0.0457",
    }

    normalized = normalize_source_params(source_type, params)

    assert normalized["scanner_vendor"] == "GE"
    assert normalized["scanner_model"] == "GE Revolution Apex / Apex Elite"
    assert normalized["scanner_family"] == "GE_REVOLUTION_APEX_FAMILY"
    assert normalized["scanner_phantom"] == "body"

    # Normalisation may add defaults such as preset/tvl_key, but should not
    # delete the core CT fields needed by ksec workflow.
    for key in (
        "scans_per_week",
        "workload_mAs_per_scan",
        "ksec_mGy_per_100mAs_at_1m",
    ):
        assert key in normalized


def test_nm_patient_normalization_does_not_gain_ct_manual_override_fields():
    params = {
        "radionuclide": "Tc99m",
        "NMPS_R": "20",
        "NMPS_S": "20",
    }

    normalized = normalize_source_params("nm_patient", params)

    assert normalized["radionuclide"] == "Tc99m"
    assert "manual_ksec_override" not in normalized
    assert "manual_ksec_reason" not in normalized
    assert "ksec_mGy_per_100mAs_at_1m" not in normalized


def test_xray_primary_normalization_does_not_gain_ct_manual_override_fields():
    params = {
        "xray_method": "manual",
        "workload_uSv_per_week_at_1m": "100000",
        "use_factor": "0.25",
    }

    normalized = normalize_source_params("xray_primary", params)

    assert normalized["xray_method"] == "manual"
    assert "manual_ksec_override" not in normalized
    assert "manual_ksec_reason" not in normalized
    assert "ksec_mGy_per_100mAs_at_1m" not in normalized
