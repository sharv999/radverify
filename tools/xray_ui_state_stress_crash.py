"""XR-21D deterministic GXR UI crash/stress harness (>=500 combinations).

Runs real Tk Geometry-tab handlers.  The finite matrix exhausts combinations of
feature creation order, Chest Bucky wall, opening wall, Control Wall rotation,
and save/reopen checkpoint.  Continuous numeric UI values are intentionally not
claimed to be exhaustible.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from services.project_io import load_project_from_file, write_project_payload
from services.project_ui_state import apply_loaded_project_to_ui
from tools.xray_ui_state_stress import EXPECTED, WALLS, _act, _reset_to_new_gxr, wall_snapshot

REPORT_PATH = Path("tests/reports/XR21D_GXR_UI_STRESS_PASS_FAIL_REPORT.pdf")
FEATURES = ("door", "bucky", "control")
ORDERS = tuple(permutations(FEATURES))
BUCKY_WALLS = tuple("NESW")
DOOR_WALLS = tuple("NESW")
CONTROL_ROTATIONS = (0, 1, 2)
SELECTION_CHURN = ("NW", "WN")

@dataclass(frozen=True)
class CrashCase:
    name: str
    order: tuple[str, str, str]
    bucky_wall: str
    door_wall: str
    rotations: int
    save_reopen: bool


def build_cases() -> tuple[CrashCase, ...]:
    cases = []
    # 576 normal UI combinations: 6 creation orders x 4 Bucky walls x
    # 4 opening walls x 3 Control Wall rotation states x 2 selection-churn orders.
    for i, (order, bw, dw, rotations, churn) in enumerate(
        product(ORDERS, BUCKY_WALLS, DOOR_WALLS, CONTROL_ROTATIONS, SELECTION_CHURN), 1
    ):
        cases.append(CrashCase(
            name=f"matrix_{i:03d}_{''.join(x[0] for x in order)}_B{bw}_D{dw}_R{rotations}_C{churn}",
            order=order, bucky_wall=bw, door_wall=dw,
            rotations=rotations, save_reopen=False,
        ))
    # 24 additional save/reopen crash cases: every creation order x every Bucky
    # wall, with the door on N and all three feature families already active.
    for order, bw in product(ORDERS, BUCKY_WALLS):
        i = len(cases) + 1
        cases.append(CrashCase(
            name=f"save_{i:03d}_{''.join(x[0] for x in order)}_B{bw}",
            order=order, bucky_wall=bw, door_wall="N", rotations=1, save_reopen=True,
        ))
    return tuple(cases)

CASES = build_cases()  # 600 real UI scenarios: 576 matrix + 24 save/reopen.


def _expected_defaults():
    return {name: EXPECTED for name in WALLS}


def _assert_snapshot(room, expected, case, step):
    actual = wall_snapshot(room)
    if actual != expected:
        raise AssertionError(f"{case}: after {step}: expected {expected}, got {actual}")


def _save_reopen(app, path: Path):
    payload = app.prepare_project_for_save()
    write_project_payload(path, payload)
    restored = load_project_from_file(path)
    apply_loaded_project_to_ui(app, restored, path)
    
    return app.project.rooms[0]


def _feature_action(g, feature: str, case: CrashCase):
    if feature == "door":
        _act(g, "door_add")
        if case.door_wall != "N":
            _act(g, "door_" + case.door_wall.lower())
        _act(g, "door_move")
    elif feature == "bucky":
        _act(g, "bucky_" + case.bucky_wall.lower())
    elif feature == "control":
        _act(g, "control_add")
        for _ in range(case.rotations):
            _act(g, "control_rotate")
    else:
        raise ValueError(feature)


def run_case(app, case: CrashCase):
    _reset_to_new_gxr(app)
    expected = _expected_defaults()
    room = app.project.rooms[0]
    _assert_snapshot(room, expected, case.name, "initial")
    with TemporaryDirectory() as td:
        for index, feature in enumerate(case.order):
            _feature_action(app.geometry_tab, feature, case)
            
            _assert_snapshot(room, expected, case.name, feature)
            # Reopen after the second feature so the resumed UI must survive the
            # final feature and selection churn.  This is deterministic and
            # catches serialization/UI rehydration leakage.
            if case.save_reopen and index == 1:
                room = _save_reopen(app, Path(td) / "xr21d.json")
                _assert_snapshot(room, expected, case.name, "save_reopen")
        churn = ("select_floor", "select_w", "select_n")
        if case.name.endswith("CWN"):
            churn = ("select_floor", "select_n", "select_w")
        for action in churn:
            _act(app.geometry_tab, action); 
            _assert_snapshot(room, expected, case.name, action)


def run_report(cases=CASES):
    from app import ShieldingDesktopApp
    app = ShieldingDesktopApp(); app.withdraw()
    results = []
    try:
        for case in cases:
            try:
                run_case(app, case)
            except Exception as exc:
                results.append((case.name, "FAIL", f"{type(exc).__name__}: {exc}"))
            else:
                results.append((case.name, "PASS", ""))
    finally:
        app.destroy()
    return results


def write_pdf_report(results, path: Path = REPORT_PATH, *, title: str = "XR-21D General X-ray UI State-Isolation Crash Test"):
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(status == "PASS" for _, status, _ in results)
    failed = len(results) - passed
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=6.5, leading=8)
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = [Paragraph(title, styles["Title"]),
             Paragraph(f"TOTAL: {len(results)} &nbsp;&nbsp; PASS: {passed} &nbsp;&nbsp; FAIL: {failed}", styles["Heading2"]),
             Paragraph("Matrix: 576 cases covering all 6 Door/Bucky/Control creation orders x 4 Bucky walls x 4 opening walls x 3 Control Wall rotation states x 2 selection-churn orders, plus 24 save/reopen continuation cases. Each case also performs door movement. Continuous numeric input space is not finite and is not claimed to be exhaustive.", styles["BodyText"]), Spacer(1, 5*mm)]
    rows = [["#", "Status", "Scenario", "Detail"]]
    for i, (name, status, detail) in enumerate(results, 1):
        rows.append([str(i), status, Paragraph(name, small), Paragraph(detail or "-", small)])
    table = Table(rows, colWidths=[12*mm, 18*mm, 90*mm, 145*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 6.5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(table)
    doc.build(story)
    return path


def format_summary(results):
    passed = sum(s == "PASS" for _, s, _ in results)
    failed = len(results) - passed
    return f"XR-21D GXR UI crash test: TOTAL={len(results)} PASS={passed} FAIL={failed}"


def main():
    results = run_report()
    write_pdf_report(results)
    print(format_summary(results))
    if any(status == "FAIL" for _, status, _ in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
