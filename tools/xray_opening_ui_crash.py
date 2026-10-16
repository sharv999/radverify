"""XR-21E2 focused GXR opening-only parent-barrier immutability harness.

Hard invariant: adding, moving, editing or removing an Opening has zero
authority to change N/E/S/W parent-wall material, thickness, occupancy T,
or design goal P.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from tools.xray_ui_state_stress import WALLS, _reset_to_new_gxr, wall_snapshot

INVARIANT = "PARENT_BARRIER_DESIGN_IMMUTABILITY"
REPORT_PATH = Path("tests/reports/XR21E2_GXR_OPENING_ONLY_IMMUTABILITY_REPORT.pdf")
OPENING_WALLS = tuple("NESW")
SELECTED_BARRIERS = ("N", "E", "S", "W", "Floor", "Ceiling")
OPENING_TYPES = ("Door", "Viewing Panel")
BASELINES = ("default", "mixed_custom")

CUSTOM = {
    "N wall": ("Concrete", 150.0, 0.5, 20.0),
    "E wall": ("Pb", 1.10, 0.2, 5.0),
    "S wall": ("Concrete", 200.0, 1.0, 15.0),
    "W wall": ("Pb", 1.50, 0.5, 30.0),
}

@dataclass(frozen=True)
class OpeningCrashCase:
    name: str
    baseline: str
    opening_wall: str
    selected_barrier: str
    opening_type: str


def build_cases():
    out=[]
    for i, (base, ow, sb, ot) in enumerate(product(
        BASELINES, OPENING_WALLS, SELECTED_BARRIERS, OPENING_TYPES
    ), 1):
        out.append(OpeningCrashCase(
            f"opening_{i:03d}_B{base}_D{ow}_SEL{sb}_T{ot.replace(' ','')}",
            base, ow, sb, ot,
        ))
    return tuple(out)

CASES = build_cases()  # 96 focused cases; each executes a full opening lifecycle.


def _canvas_texts(g):
    return [str(g.canvas.itemcget(i, "text")) for i in g.canvas.find_all() if g.canvas.type(i) == "text"]


def _diff(before, after):
    changes=[]
    for wall in WALLS:
        b=before.get(wall); a=after.get(wall)
        if b != a:
            labels=("material","thickness_mm","T","P_uSv_per_week")
            if b is None or a is None:
                changes.append(f"{wall}: before={b}; after={a}")
            else:
                for label, old, new in zip(labels,b,a):
                    if old != new: changes.append(f"{wall}.{label}: {old} -> {new}")
    return "; ".join(changes) or "unknown difference"


def assert_parent_barrier_design_immutability(app, baseline, case_name, action):
    """Check model, live Barrier editor and rendered canvas against baseline."""
    g=app.geometry_tab; room=app.project.rooms[0]
    actual=wall_snapshot(room)
    if actual != baseline:
        raise AssertionError(
            f"{INVARIANT} FAIL | scenario={case_name} | action={action} | "
            f"{_diff(baseline, actual)} | before={baseline} | after={actual}"
        )

    original=g.barrier_wall_var.get()
    try:
        for short, wall_name in zip("NESW", WALLS):
            g.barrier_wall_var.set(short); app.update_idletasks()
            ui=(str(g.barrier_material_var.get()), round(float(g.barrier_thickness_var.get()),6),
                round(float(g.barrier_t_var.get()),6), round(float(str(g.p_var.get()).split()[0]),6))
            if ui != baseline[wall_name]:
                raise AssertionError(
                    f"{INVARIANT} FAIL | scenario={case_name} | action={action} | "
                    f"BARRIER_EDITOR {wall_name}: before={baseline[wall_name]} after={ui}"
                )
    finally:
        g.barrier_wall_var.set(original); app.update_idletasks()

    g.draw_room_with_risk(); app.update_idletasks()
    canvas="\n".join(_canvas_texts(g))
    for wall_name, (material, thickness, _t, _p) in baseline.items():
        token=f"{material} {thickness:.2f} mm"
        if token not in canvas:
            raise AssertionError(
                f"{INVARIANT} FAIL | scenario={case_name} | action={action} | "
                f"CANVAS missing {wall_name} construction token {token!r}"
            )


def _apply_baseline(app, kind):
    room=app.project.rooms[0]
    if kind == "mixed_custom":
        for b in room.barriers:
            vals=CUSTOM.get(b.name)
            if vals:
                b.material, b.thickness_mm, b.occupancy_factor, b.design_goal_uSv_per_week = vals
                b.material_legacy = b.material
    app.geometry_tab.load_selected_barrier_fields()
    app.geometry_tab.draw_room_with_risk(); app.update_idletasks()
    return wall_snapshot(room)


def _checked(app, baseline, case, action, fn):
    fn(); app.update()
    assert_parent_barrier_design_immutability(app, baseline, case.name, action)


def run_case(app, case):
    """Exercise only Opening UI operations; no Bucky or Control Wall actions."""
    _reset_to_new_gxr(app); g=app.geometry_tab
    baseline=_apply_baseline(app, case.baseline)
    assert_parent_barrier_design_immutability(app, baseline, case.name, "initial")

    # Deliberately vary the currently selected parent-barrier editor before the
    # opening is touched. This targets the stale-editor leakage seen manually.
    g.barrier_wall_var.set(case.selected_barrier); app.update()
    assert_parent_barrier_design_immutability(app, baseline, case.name, "select-barrier")

    g.opening_wall_var.set(case.opening_wall)
    g.opening_type_var.set(case.opening_type)
    g.opening_offset_var.set("1.0")
    _checked(app, baseline, case, "add-opening", g.add_opening)

    # Move the opening repeatedly in both directions.
    for i, delta in enumerate((0.10, 0.10, -0.10, -0.10), 1):
        _checked(app, baseline, case, f"move-opening-{i}", lambda d=delta: g.nudge_opening_offset(d))

    # Edit opening width and Pb equivalence through the same live fields/callbacks.
    def edit_width():
        g.opening_width_var.set("1.25")
        g.update_selected_opening_from_fields()
    _checked(app, baseline, case, "edit-opening-width", edit_width)

    def edit_pb():
        g.opening_pb_var.set("1.50")
        g.update_current_opening_thickness()
    _checked(app, baseline, case, "edit-opening-pb", edit_pb)

    # Toggle opening type/material both ways.
    for typ in ("Viewing Panel", "Door"):
        def edit_type(typ=typ):
            g.opening_type_var.set(typ)
            g.on_opening_type_changed()
            g.update_selected_opening_from_fields()
        _checked(app, baseline, case, f"edit-opening-type-{typ}", edit_type)

    # Move the same opening through every parent wall.
    for wall in "NESW":
        def edit_wall(wall=wall):
            g.opening_wall_var.set(wall)
            g.update_selected_opening_from_fields()
        _checked(app, baseline, case, f"move-opening-to-wall-{wall}", edit_wall)

    # Remove all openings, then add/remove once more to catch lifecycle leakage.
    _checked(app, baseline, case, "remove-opening", g.clear_openings)
    g.opening_wall_var.set(case.opening_wall)
    g.opening_type_var.set(case.opening_type)
    _checked(app, baseline, case, "re-add-opening", g.add_opening)
    _checked(app, baseline, case, "remove-opening-again", g.clear_openings)


def write_pdf_report(results, path=REPORT_PATH):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    passed=sum(s=="PASS" for _,s,_ in results); failed=len(results)-passed
    styles=getSampleStyleSheet(); small=ParagraphStyle("small", parent=styles["BodyText"], fontSize=6.0, leading=7.0)
    doc=SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[Paragraph("XR-21E2 GXR Opening-Only Parent-Barrier Immutability Crash Test", styles["Title"]),
           Paragraph(f"{INVARIANT} — TOTAL: {len(results)} &nbsp;&nbsp; PASS: {passed} &nbsp;&nbsp; FAIL: {failed}", styles["Heading2"]),
           Paragraph("Focused requirement: adding, moving, editing or removing an Opening must never change N/E/S/W parent-wall material, thickness, occupancy T or design goal P. Each case exercises a complete opening lifecycle and checks model state, live Barrier editor and rendered canvas after every action. No Chest Bucky or Control Wall operations are included.", styles["BodyText"]), Spacer(1,4*mm)]
    rows=[["#","Status","Scenario","Failure detail"]]+[[str(i),s,Paragraph(n,small),Paragraph(d or "-",small)] for i,(n,s,d) in enumerate(results,1)]
    t=Table(rows,colWidths=[12*mm,18*mm,105*mm,130*mm],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.25,colors.grey),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),6.0),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2)]))
    story.append(t); doc.build(story); return path
