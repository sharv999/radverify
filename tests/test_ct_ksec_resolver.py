from services.ct_ksec_resolver import resolve_database_ct_ksec


class FakeEngine:
    def __init__(self, scanners):
        self.scanners = scanners

    def get_scanner(self, family):
        if family not in self.scanners:
            raise KeyError(family)
        return self.scanners[family]


def test_resolve_database_ct_ksec_success_with_energy_basis():
    engine = FakeEngine({
        "GE_APEX": {
            "worst_case_ksec_mGy_per_100mAs_at_1m": 0.0457,
            "ksec_energy_kvp": 140,
        }
    })

    result = resolve_database_ct_ksec(
        ct_scatter_engine=engine,
        scanner_family="GE_APEX",
        vendor="GE",
        model="Revolution Apex",
        kvp=120,
    )

    assert result.has_database_ksec
    assert not result.requires_manual_override
    assert result.ksec_mGy_per_100mAs_at_1m == 0.0457
    assert result.ksec_energy_kvp == 140
    assert "GE / Revolution Apex" in result.scanner_source
    assert "@ 140 kVp" in result.scanner_source


def test_resolve_database_ct_ksec_falls_back_to_selected_kvp_for_energy_only():
    engine = FakeEngine({
        "CANON": {
            "worst_case_ksec_mGy_per_100mAs_at_1m": "0.03",
        }
    })

    result = resolve_database_ct_ksec(
        ct_scatter_engine=engine,
        scanner_family="CANON",
        vendor="Canon",
        model="Aquilion",
        kvp=140,
    )

    assert result.has_database_ksec
    assert result.ksec_energy_kvp == 140


def test_resolve_database_ct_ksec_null_requires_manual_override():
    engine = FakeEngine({
        "PHILIPS_NULL": {
            "worst_case_ksec_mGy_per_100mAs_at_1m": None,
            "ksec_energy_kvp": 140,
        }
    })

    result = resolve_database_ct_ksec(
        ct_scatter_engine=engine,
        scanner_family="PHILIPS_NULL",
        vendor="Philips",
        model="Brilliance 64",
        kvp=140,
    )

    assert result.requires_manual_override
    assert not result.has_database_ksec
    assert result.ksec_mGy_per_100mAs_at_1m is None
    assert result.ksec_energy_kvp == 140
    assert "manual override required" in result.scanner_source


def test_resolve_database_ct_ksec_missing_family_requires_manual_override():
    result = resolve_database_ct_ksec(
        ct_scatter_engine=FakeEngine({}),
        scanner_family="UNKNOWN",
        vendor="",
        model="",
        kvp=140,
    )

    assert result.requires_manual_override
    assert result.ksec_mGy_per_100mAs_at_1m is None


def test_resolve_database_ct_ksec_no_engine_requires_manual_override():
    result = resolve_database_ct_ksec(
        ct_scatter_engine=None,
        scanner_family="GE_APEX",
        vendor="GE",
        model="Revolution Apex",
        kvp=140,
    )

    assert result.requires_manual_override
    assert result.ksec_mGy_per_100mAs_at_1m is None
