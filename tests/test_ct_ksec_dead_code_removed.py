from pathlib import Path


def test_app_no_longer_contains_ct_ksec_compatibility_wrappers():
    app_text = Path("app.py").read_text(encoding="utf-8")

    forbidden = [
        "def _json_worst_case_ksec_per_100mAs",
        "def _ct_source_ksec_per_100mAs(",
        "def _ct_source_ksec_per_100mAs_from_db",
        "def _scanner_db_csv_candidates",
        "def _load_scanner_db",
        "def _ct_csv_default_path",
        "def _update_ct_ksec_from_database",
        "conservative_default_ksec",
        "CTShieldingDatabase",
        "CT_DB_AVAILABLE",
    ]

    for token in forbidden:
        assert token not in app_text, token


def test_ct_plugin_uses_central_ct_ksec_resolver():
    app_text = Path("app.py").read_text(encoding="utf-8")
    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")

    assert "central_ct_ksec_resolver" in ct_text
    assert "central_ct_ksec_resolver" not in app_text
