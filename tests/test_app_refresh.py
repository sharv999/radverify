from pathlib import Path


def test_app_refresh_module_exists_and_owns_refresh_logic():
    app_text = Path("app.py").read_text(encoding="utf-8")
    refresh_text = Path("services/app_refresh.py").read_text(encoding="utf-8")

    assert "from services.app_refresh import refresh_all" in app_text
    assert "app._sanitize_all_nm_patient_sources()" in refresh_text
    assert "app.render_optimizer_recommendations([])" in refresh_text


def test_app_refresh_all_is_thin_wrapper():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "    def refresh_all(self):\n        from services.app_refresh import refresh_all" in app_text
    assert "self._sanitize_all_nm_patient_sources()" not in app_text
