from pathlib import Path
import pytest
from tools.xray_opening_ui_crash import (
    CASES, INVARIANT, assert_parent_barrier_design_immutability, run_case, write_pdf_report,
)
from tools.xray_ui_state_stress import _reset_to_new_gxr, wall_snapshot

REPORT_PATH=Path("tests/reports/XR21E2_GXR_OPENING_ONLY_IMMUTABILITY_REPORT.pdf")
_RESULTS=[]

@pytest.fixture(scope="module")
def xr21e2_app_and_report():
    from app import ShieldingDesktopApp
    app=ShieldingDesktopApp(); app.withdraw(); _RESULTS.clear()
    try: yield app
    finally:
        app.destroy()
        write_pdf_report(_RESULTS, REPORT_PATH)

def test_xr21e2_matrix_has_96_unique_opening_only_cases():
    assert len(CASES)==96
    assert len({c.name for c in CASES})==96

@pytest.mark.gxr_opening_crash
@pytest.mark.parametrize("case", CASES, ids=lambda c:c.name)
def test_xr21e2_opening_only_parent_barrier_design_immutability(xr21e2_app_and_report, case):
    try: run_case(xr21e2_app_and_report, case)
    except Exception as exc:
        detail=f"{type(exc).__name__}: {exc}"; _RESULTS.append((case.name,"FAIL",detail)); pytest.fail(detail,pytrace=True)
    else: _RESULTS.append((case.name,"PASS",""))

def test_xr21e2_detector_rejects_exact_pb_to_concrete_leak():
    """Prove the invariant catches the observed N-wall Pb -> Concrete/150 leak."""
    from app import ShieldingDesktopApp
    app=ShieldingDesktopApp(); app.withdraw()
    try:
        _reset_to_new_gxr(app); room=app.project.rooms[0]; baseline=wall_snapshot(room)
        north=next(b for b in room.barriers if b.name == "N wall")
        north.material="Concrete"; north.thickness_mm=150.0
        with pytest.raises(AssertionError, match=INVARIANT):
            assert_parent_barrier_design_immutability(app, baseline, CASES[0].name, "injected-N-wall-leak")
    finally: app.destroy()
