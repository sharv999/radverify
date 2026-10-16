"""Opt-in XR-21F Control Wall-only UI regression."""
from pathlib import Path
import pytest
from tools.xray_control_wall_ui_crash import CASES, run_case, write_pdf_report

REPORT = Path('tests/reports/XR21F_GXR_CONTROL_WALL_IMMUTABILITY_REPORT.pdf')
_RESULTS = []

@pytest.fixture(scope='module')
def control_wall_app():
    from app import ShieldingDesktopApp
    app = ShieldingDesktopApp()
    app.withdraw()
    _RESULTS.clear()
    try:
        yield app
    finally:
        app.destroy()
        write_pdf_report(_RESULTS, REPORT)

def test_xr21f_case_matrix():
    assert len(CASES) == 54
    assert len({case.name for case in CASES}) == 54
    assert any(case.baseline == 'north_pb_glass' for case in CASES)

@pytest.mark.gxr_control_wall_crash
@pytest.mark.parametrize('case', CASES, ids=lambda case: case.name)
def test_xr21f_control_wall_preserves_parent_barrier_design(control_wall_app, case):
    try:
        run_case(control_wall_app, case)
    except Exception as exc:
        detail = f'{type(exc).__name__}: {exc}'
        _RESULTS.append((case.name, 'FAIL', detail))
        pytest.fail(detail, pytrace=True)
    else:
        _RESULTS.append((case.name, 'PASS', ''))
