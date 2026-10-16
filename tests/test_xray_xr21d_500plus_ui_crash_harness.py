from pathlib import Path

import pytest

from tools.xray_ui_state_stress_crash import (
    CASES, ORDERS, BUCKY_WALLS, DOOR_WALLS, CONTROL_ROTATIONS, SELECTION_CHURN,
    format_summary, run_case, write_pdf_report,
)

REPORT_PATH = Path("tests/reports/XR21D1_GXR_UI_STRESS_PASS_FAIL_REPORT.pdf")
_RESULTS = []


@pytest.fixture(scope="module")
def xr21d1_app_and_report():
    """One real Tk app for all 600 cases; always emit the local PASS/FAIL PDF."""
    from app import ShieldingDesktopApp

    app = ShieldingDesktopApp()
    app.withdraw()
    _RESULTS.clear()
    try:
        yield app
    finally:
        app.destroy()
        write_pdf_report(
            _RESULTS,
            REPORT_PATH,
            title="XR-21D1 General X-ray UI State-Isolation Crash Test",
        )


def test_xr21d1_matrix_has_600_unique_ui_combinations():
    assert len(CASES) == 600
    assert len({c.name for c in CASES}) == 600
    assert len(ORDERS) == 6
    assert BUCKY_WALLS == tuple("NESW")
    assert DOOR_WALLS == tuple("NESW")
    assert CONTROL_ROTATIONS == (0, 1, 2)
    assert SELECTION_CHURN == ("NW", "WN")
    assert sum(c.save_reopen for c in CASES) == 24


def test_xr21d1_pdf_report_writer_has_explicit_pass_fail_per_case(tmp_path):
    results = [("case_pass", "PASS", ""), ("case_fail", "FAIL", "sentinel")]
    out = write_pdf_report(results, tmp_path / "xr21d1.pdf", title="XR-21D1 test")
    assert out.exists() and out.stat().st_size > 1000
    assert "TOTAL=2 PASS=1 FAIL=1" == format_summary(results).split(": ", 1)[1]


@pytest.mark.gxr_crash
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_xr21d1_gxr_ui_state_isolation_case(xr21d1_app_and_report, case):
    """Each crash scenario is a separately visible pytest case."""
    try:
        run_case(xr21d1_app_and_report, case)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        _RESULTS.append((case.name, "FAIL", detail))
        pytest.fail(detail, pytrace=True)
    else:
        _RESULTS.append((case.name, "PASS", ""))
