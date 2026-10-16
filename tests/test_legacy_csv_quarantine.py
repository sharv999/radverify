from __future__ import annotations

"""
Regression tests for legacy CSV ksec quarantine.

These tests protect against reintroducing the old CSV/conservative-default CT
ksec path. They avoid importing the full Tkinter app where possible, but include
small test doubles that mirror the intended behaviour of the quarantined hooks.

Run from project root:

    python -m pytest tests/test_legacy_csv_quarantine.py
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from services.ksec_status import resolve_ksec_status


@dataclass
class DummyVar:
    value: str = ""

    def get(self) -> str:
        return self.value

    def set(self, value: Any) -> None:
        self.value = str(value)


@dataclass
class DummySource:
    source_type: str
    params: dict[str, Any] = field(default_factory=dict)


class LegacyCsvQuarantineHarness:
    """
    Small test double for the app's quarantined legacy CSV hooks.

    This intentionally mirrors the safety contract:

        - _load_scanner_db() does not load CSV data
        - _ct_source_ksec_per_100mAs_from_db() raises
        - _update_ct_ksec_from_database() does not write ksec
        - _refresh_ct_model_list() clears/does not populate legacy CSV models
    """

    def __init__(self):
        self.ct_vars = {
            "ksec_mGy_per_100mAs_at_1m": DummyVar(""),
            "manual_ksec_override": DummyVar("0"),
            "scanner_source": DummyVar(""),
        }
        self.ct_db_match_status_var = DummyVar("")
        self.ct_ksec_source_var = DummyVar("")
        self.ct_ksec_note_var = DummyVar("")

    def _load_scanner_db(self, filename: str | None = None):
        label = filename or "legacy scanner CSV"
        return None, (
            f"Legacy CSV ksec database quarantined: {label}; "
            "JSON scanner database is authoritative"
        )

    def _ct_source_ksec_per_100mAs_from_db(
        self,
        vendor: str,
        model: str,
        kvp: int,
        source_type: str | None = None,
    ):
        raise ValueError(
            "Legacy CSV ksec lookup is quarantined. "
            "Use ct_scatter_master_database.json or enter a documented manual ksec override."
        )

    def _update_ct_ksec_from_database(self, _event=None):
        for attr, value in (
            (
                "ct_db_match_status_var",
                "Legacy CSV ksec database quarantined; use JSON scanner database or manual override",
            ),
            ("ct_ksec_source_var", "legacy CSV quarantined"),
            ("ct_ksec_note_var", ""),
        ):
            getattr(self, attr).set(value)
        return

    def _refresh_ct_model_list(self, _event=None):
        return


def test_legacy_csv_loader_returns_none_and_quarantine_message():
    app = LegacyCsvQuarantineHarness()

    db, message = app._load_scanner_db("ct_scanner_ksec_database.csv")

    assert db is None
    assert "quarantined" in message.lower()
    assert "JSON scanner database is authoritative" in message


def test_legacy_spect_ct_csv_loader_returns_none_and_quarantine_message():
    app = LegacyCsvQuarantineHarness()

    db, message = app._load_scanner_db("spect_ct_scanner_ksec_database.csv")

    assert db is None
    assert "quarantined" in message.lower()
    assert "spect_ct_scanner_ksec_database.csv" in message


def test_legacy_csv_ksec_lookup_raises_instead_of_returning_default():
    app = LegacyCsvQuarantineHarness()

    with pytest.raises(ValueError, match="Legacy CSV ksec lookup is quarantined"):
        app._ct_source_ksec_per_100mAs_from_db(
            vendor="Philips",
            model="Brilliance 64",
            kvp=140,
            source_type="ct_scatter",
        )


def test_legacy_csv_update_hook_does_not_write_ksec_or_manual_override():
    app = LegacyCsvQuarantineHarness()
    app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set("")
    app.ct_vars["manual_ksec_override"].set("0")

    app._update_ct_ksec_from_database()

    assert app.ct_vars["ksec_mGy_per_100mAs_at_1m"].get() == ""
    assert app.ct_vars["manual_ksec_override"].get() == "0"
    assert "quarantined" in app.ct_db_match_status_var.get().lower()
    assert app.ct_ksec_source_var.get() == "legacy CSV quarantined"


def test_legacy_csv_update_hook_does_not_overwrite_existing_manual_override():
    app = LegacyCsvQuarantineHarness()
    app.ct_vars["ksec_mGy_per_100mAs_at_1m"].set("0.015")
    app.ct_vars["manual_ksec_override"].set("1")
    app.ct_vars["scanner_source"].set("Manual override entered in Sources tab")

    app._update_ct_ksec_from_database()

    assert app.ct_vars["ksec_mGy_per_100mAs_at_1m"].get() == "0.015"
    assert app.ct_vars["manual_ksec_override"].get() == "1"
    assert app.ct_vars["scanner_source"].get() == "Manual override entered in Sources tab"


def test_quarantined_csv_path_cannot_create_database_status_for_null_scanner():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "Legacy CSV ksec database quarantined; use JSON scanner database or manual override",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override_required"
    assert status["status"] == "FAIL"
    assert status["ksec"] is None


def test_conservative_default_006_is_not_accepted_when_field_is_blank():
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
    assert status["basis_label"] != "Database"


def test_conservative_default_006_requires_manual_flag_to_be_used():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "0.06",
            "manual_ksec_override": "1",
            "manual_ksec_reason": "Deliberate physicist-approved override",
            "scanner_source": "Manual override entered in Sources tab",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "manual_override"
    assert status["status"] == "REVIEW"
    assert status["ksec"] == pytest.approx(0.06)
    assert status["basis_label"] == "Manual override"


def test_positive_ksec_without_manual_flag_is_database_only_when_json_source_text_is_used():
    src = DummySource(
        source_type="ct_scatter",
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "ksec_mGy_per_100mAs_at_1m": "0.0457",
            "manual_ksec_override": "0",
            "scanner_source": "JSON worst-case Ksec lookup (GE_REVOLUTION_APEX_FAMILY)",
        },
    )

    status = resolve_ksec_status(src)

    assert status["basis"] == "database"
    assert status["status"] == "PASS"
    assert "JSON" in status["source_text"]
