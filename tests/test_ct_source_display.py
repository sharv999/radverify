from services.ct_source_display import build_ct_source_display_state, format_ksec_energy


def test_ct_source_display_database_ksec_energy_basis():
    state = build_ct_source_display_state(
        "ct_scatter",
        {
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "ksec_energy_kvp": 140,
            "scanner_source": "GE / GE Revolution Apex / Apex Elite -> JSON worst-case Ksec lookup",
        },
    )

    assert state.is_ct_scatter
    assert state.basis == "database"
    assert state.ksec_display == "0.0457 mGy/100 mAs @ 1 m"
    assert state.ksec_energy_display == "140 kVp"
    assert state.energy_basis_display == "CT ksec energy basis: 140 kVp"
    assert "GE Revolution Apex" in state.scanner_debug_display


def test_ct_source_display_manual_override():
    state = build_ct_source_display_state(
        "ct_scatter",
        {
            "scanner_model": "Philips Brilliance 64",
            "ksec_mGy_per_100mAs_at_1m": "0.06",
            "ksec_energy_kvp": "140.0",
            "manual_ksec_override": "1",
            "manual_ksec_reason": "Vendor document pending",
        },
    )

    assert state.basis == "manual_override"
    assert state.is_manual_override
    assert state.audit_complete
    assert "manual override" in state.ksec_display
    assert state.ksec_energy_display == "140 kVp"


def test_ct_source_display_null_ksec_requires_manual_override():
    state = build_ct_source_display_state(
        "ct_scatter",
        {
            "scanner_model": "Philips Brilliance 64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "ksec_energy_kvp": "",
            "scanner_kvp": 140,
        },
    )

    assert state.requires_manual_override
    assert "NULL" in state.ksec_display
    assert state.ksec_energy_display == "140 kVp"


def test_format_ksec_energy():
    assert format_ksec_energy("140.0") == "140 kVp"
    assert format_ksec_energy("120 kVp") == "120 kVp"
    assert format_ksec_energy("") == ""
