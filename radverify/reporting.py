"""Draft Radiation Room Field Verification PDF - presentation only.

No shielding physics, dose acceptance criteria, legal compliance or certification
is computed here.  The canonical model remains the saved RadVerify project.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import os
import tempfile
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, LongTable, Table, TableStyle,
)

from radverify.models import RadVerifyProject

INK = colors.HexColor('#17243a')
ACCENT = colors.HexColor('#196581')
LIGHT = colors.HexColor('#eef4f7')
MUTED = colors.HexColor('#536374')
RULE = colors.HexColor('#d4e1e6')
WHITE = colors.white
STATUS_COLORS = {
    'pass': colors.HexColor('#21876e'),
    'fail': colors.HexColor('#ba3d3d'),
    'review': colors.HexColor('#c38a27'),
    'not inspected': colors.HexColor('#718096'),
    'n/a': colors.HexColor('#718096'),
}


def _safe(value: Any) -> str:
    """Escape user-supplied text for ReportLab's Paragraph markup."""
    if value is None or value == '':
        return '-'
    return escape(str(value), quote=False).replace('\n', '<br/>')


def _number(value: Any, unit: str = '') -> str:
    return '-' if value is None else f'{float(value):.3g}{unit}'


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RVTitle', parent=styles['Title'], fontName='Helvetica-Bold',
        fontSize=19, leading=23, alignment=0, textColor=INK, spaceAfter=5))
    styles.add(ParagraphStyle(name='RVSubtitle', parent=styles['Normal'], fontSize=10,
        leading=14, textColor=ACCENT, spaceAfter=11))
    styles.add(ParagraphStyle(name='RVSection', parent=styles['Heading2'], fontName='Helvetica-Bold',
        fontSize=12, leading=16, textColor=INK, spaceBefore=12, spaceAfter=6, keepWithNext=1))
    styles.add(ParagraphStyle(name='RVSmall', parent=styles['BodyText'], fontSize=7.4,
        leading=10, textColor=INK))
    styles.add(ParagraphStyle(name='RVBody', parent=styles['BodyText'], fontSize=9,
        leading=13, textColor=INK, spaceAfter=4))
    styles.add(ParagraphStyle(name='RVMuted', parent=styles['BodyText'], fontSize=7.8,
        leading=11, textColor=MUTED, spaceAfter=5))
    styles.add(ParagraphStyle(name='RVHeader', parent=styles['BodyText'], fontName='Helvetica-Bold',
        fontSize=7.4, leading=9, textColor=WHITE))
    styles.add(ParagraphStyle(name='RVWarning', parent=styles['BodyText'], fontName='Helvetica-Bold',
        fontSize=8.2, leading=12, textColor=colors.HexColor('#91451f'), spaceAfter=7))
    return styles


def _table(headers: list[str], data: Iterable[list[Any]], widths: list[float], styles, *, maxrows=None):
    p = lambda v: Paragraph(_safe(v), styles['RVSmall'])
    rows = [[Paragraph(_safe(h), styles['RVHeader']) for h in headers]]
    rows.extend([[p(cell) for cell in row] for row in data])
    if len(rows) == 1:
        rows.append([p('No records')]+[p('') for _ in headers[1:]])
    table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), INK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, -1), (-1, -1), .5, RULE),
    ]))
    return table


class FloorPlan(Flowable):
    """Schematic, dimensioned plan in the canonical SW-origin convention."""
    def __init__(self, project: RadVerifyProject, width=505, height=275):
        super().__init__()
        self.project = project
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        geo = self.project.geometry
        w, h = float(geo.width_m), float(geo.length_m)
        if w <= 0 or h <= 0:
            c.setFillColor(MUTED)
            c.drawString(8, self.height/2, 'Invalid room dimensions - unable to draw floor plan')
            return
        scale = min((self.width-98) / w, (self.height-55) / h)
        rw, rh = w*scale, h*scale
        x0, y0 = (self.width-rw)/2, (self.height-rh)/2 - 2
        status = {b.barrier_id: b.status.lower() for b in self.project.barriers}
        coords = {'N': ((x0,y0+rh),(x0+rw,y0+rh)),
                  'S': ((x0,y0),(x0+rw,y0)),
                  'E': ((x0+rw,y0),(x0+rw,y0+rh)),
                  'W': ((x0,y0),(x0,y0+rh))}
        c.setFillColor(colors.HexColor('#f8fbfc'))
        c.rect(x0,y0,rw,rh,fill=1,stroke=0)
        # Light 1 m grid uses the SAME scale as dimensions and coordinates.
        c.setStrokeColor(colors.HexColor('#e4edf0'))
        c.setLineWidth(.45)
        for i in range(1, int(w)+1):
            c.line(x0+i*scale,y0,x0+i*scale,y0+rh)
        for i in range(1, int(h)+1):
            c.line(x0,y0+i*scale,x0+rw,y0+i*scale)
        c.setLineWidth(3.2)
        for side, (a,b) in coords.items():
            c.setStrokeColor(STATUS_COLORS.get(status.get(side+' wall','not inspected'), MUTED))
            c.line(*a,*b)
        c.setFillColor(INK)
        c.setFont('Helvetica-Bold',9)
        c.drawCentredString(x0+rw/2,y0+rh+10,'N')
        c.drawCentredString(x0+rw/2,y0-17,'S')
        c.drawRightString(x0-10,y0+rh/2,'W')
        c.drawString(x0+rw+10,y0+rh/2,'E')
        for opening in geo.openings:
            wall = str(opening.wall).upper()
            offset, half = float(opening.offset_m), float(opening.width_m)/2
            maxcoord = w if wall in ('N','S') else h
            if maxcoord <= 0: continue
            start, stop = max(0,offset-half), min(maxcoord,offset+half)
            if stop <= start: continue
            c.setStrokeColor(WHITE)
            c.setLineWidth(6)
            if wall == 'N': ax,ay,bx,by = x0+start*scale,y0+rh,x0+stop*scale,y0+rh
            elif wall == 'S': ax,ay,bx,by = x0+start*scale,y0,x0+stop*scale,y0
            elif wall == 'E': ax,ay,bx,by = x0+rw,y0+start*scale,x0+rw,y0+stop*scale
            elif wall == 'W': ax,ay,bx,by = x0,y0+start*scale,x0,y0+stop*scale
            else: continue
            c.line(ax,ay,bx,by)
            key = opening.id or opening.label
            c.setStrokeColor(STATUS_COLORS.get(status.get(key,'not inspected'),MUTED))
            c.setLineWidth(4)
            c.line(ax,ay,bx,by)
            cx, cy = (ax+bx)/2, (ay+by)/2
            c.setFillColor(INK)
            c.setFont('Helvetica',6.8)
            text = (key or opening.opening_type)[:16]
            if wall in ('N','S'):
                c.drawCentredString(cx,cy+(8 if wall=='N' else -12),text)
            else:
                c.drawCentredString(cx+(-17 if wall=='W' else 17),cy+5,text)
        # Equipment/source marker, only if inside room.
        sx,sy=float(geo.source.x_m),float(geo.source.y_m)
        if 0 <= sx <= w and 0 <= sy <= h and geo.source.label:
            px,py=x0+sx*scale,y0+sy*scale
            c.setStrokeColor(ACCENT);c.setLineWidth(1.4)
            c.circle(px,py,5,stroke=1,fill=0)
            c.line(px-9,py,px+9,py);c.line(px,py-9,px,py+9)
            c.setFont('Helvetica',7);c.setFillColor(ACCENT)
            c.drawString(px+9,py+7,geo.source.label[:28])
        for point in self.project.measurements:
            px,py=x0+float(point.x_m)*scale,y0+float(point.y_m)*scale
            if not(x0 <= px <= x0+rw and y0 <= py <= y0+rh): continue
            c.setFillColor(colors.HexColor('#773c9e'))
            c.circle(px,py,3.8,stroke=0,fill=1)
            c.setFont('Helvetica',7)
            c.drawString(px+5,py+5,str(point.point_id)[:16])
        c.setFillColor(MUTED);c.setFont('Helvetica',7.5)
        c.drawString(5,5, f'Plan schematic | W-E {w:g} m | S-N {h:g} m | FFL to ceiling {geo.height_m:g} m')
        c.drawRightString(self.width-4,5,'Origin: SW corner  |  +x east, +y north')


class _Doc(BaseDocTemplate):
    def __init__(self, filename, project_id, **kwargs):
        super().__init__(filename, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=49,
                         bottomMargin=47, title='Radiation Room Field Verification - DRAFT',
                         author='RadVerify', **kwargs)
        self.project_id = project_id
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='report',frames=frame,onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        width,height=A4
        canvas.setStrokeColor(RULE);canvas.setLineWidth(.7)
        canvas.line(42,height-35,width-42,height-35)
        canvas.setFillColor(ACCENT);canvas.setFont('Helvetica-Bold',8)
        canvas.drawString(42,height-27,'RADVERIFY  /  RADIATION ROOM FIELD RECORD')
        logo = Path(__file__).resolve().parent.parent / 'reports' / 'healthphysics_logo.jpg'
        if logo.is_file():
            canvas.drawImage(str(logo), width-109, height-32, width=67, height=31, preserveAspectRatio=True, mask='auto')
        canvas.line(42,36,width-42,36)
        canvas.setFont('Helvetica',7);canvas.setFillColor(MUTED)
        canvas.drawString(42,25,f'DRAFT - NOT A COMPLIANCE CERTIFICATE  |  {str(self.project_id)[:42]}')
        canvas.drawRightString(width-42,25,f'Page {doc.page}')
        canvas.restoreState()


def build_verification_pdf(project: RadVerifyProject, output: str | Path, *, generated_at: str | None = None) -> Path:
    """Build a deterministic, non-certifying room field record as a PDF.

    Produces a complete readable report even for incomplete/failed rooms. No
    automatic threshold or approval decision is made by the PDF exporter.
    Uses a temporary sibling file to avoid overwriting a good PDF on failure.
    """
    output=Path(output)
    if not output.parent.is_dir():
        raise FileNotFoundError(f'Report folder does not exist: {output.parent}')
    project.sync_opening_inspections()
    d=project.details
    summary=project.verification_summary()
    generated_at=generated_at or datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
    styles=_styles()
    P=lambda s,style='RVBody': Paragraph(_safe(s),styles[style])
    story=[]
    story.append(P('Radiation Room Verification', 'RVTitle'))
    story.append(P('DRAFT FIELD RECORD  |  NOT A REGULATORY COMPLIANCE CERTIFICATE','RVSubtitle'))
    story.append(P('This report transcribes observations recorded in RadVerify. A Pass/Fail entry is an inspector-recorded assessment, not an independently validated shielding calculation. Missing data are not assumed to pass.', 'RVMuted'))
    overview=[
        ('Project ID',d.project_id,'Site',d.site_name),
        ('Room',d.room_name,'Room number',d.room_number),
        ('Modality',d.room_type,'Building / level',d.building),
        ('Inspector',d.inspector,'Inspection date',d.inspection_date),
        ('Drawing reference',d.drawing_reference,'Report generated',generated_at),
    ]
    meta=Table([[P(x,'RVSmall') for x in row] for row in overview],colWidths=[87,165,93,165],hAlign='LEFT')
    meta.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[LIGHT,WHITE]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(meta)
    story.append(P('Room verification summary','RVSection'))
    counts=summary['barriers'];mcounts=summary['measurements']
    story.append(_table(['Field','Recorded status'],[
        ['Verification state',summary['verification_state']],
        ['RadStatus hand-off','Ready' if summary['radstatus_ready'] else 'Not ready - outstanding data / evidence'],
        ['Barrier inspections',f"Pass {counts['pass']}  |  Review {counts['review']}  |  Fail {counts['fail']}  |  Not inspected {counts['not_inspected']}  |  N/A {counts['n_a']}"],
        ['As-built / evidence completeness',f"As-built {counts['as_built_complete']}/{counts['applicable']}  |  Evidence {counts['evidence_complete']}/{counts['applicable']}  |  Integrity issues {counts['evidence_integrity_issues']}"],
        ['Measurement points',f"{mcounts['points_total']} total  |  {mcounts['points_recorded']} recorded  |  {mcounts['points_assessed']} assessed  |  {mcounts['calibration_current']} calibration-current"],
    ],[168,342],styles))
    story.append(P('Room floor plan','RVSection'))
    story.append(FloorPlan(project))
    story.append(P('Schematic plan: opening positions and survey points are plotted in metres from the south-west origin. Colours indicate recorded inspection states; geometry is not a certified as-built survey.', 'RVMuted'))

    story.append(P('Barrier inspection schedule','RVSection'))
    b_rows=[]
    for b in project.barriers:
        evidence_count=len(b.evidence_items)
        evidence = f"{evidence_count} item(s)" if evidence_count else (b.evidence_ref or 'None')
        b_rows.append([b.barrier_id,b.barrier_type,
                       b.expected_construction or '-',_number(b.expected_pb_mm),
                       b.observed_construction or '-',_number(b.observed_pb_mm),
                       b.status, evidence])
    story.append(_table(['Barrier','Type','Design','Pb-eq mm','As-built','Pb-eq mm','Status','Evidence'],
        b_rows,[71,59,78,40,78,40,60,84],styles))

    story.append(P('Inspector observations','RVSection'))
    noted=[[b.barrier_id,b.status,b.notes] for b in project.barriers if b.notes.strip()]
    story.append(_table(['Barrier','Status','Observation / note'],noted,[100,76,334],styles))

    story.append(P('Evidence register','RVSection'))
    story.append(P('Linked files are referenced, not embedded in this PDF. File verification is assessed at generation time against the stored SHA-256 fingerprint. Retain original evidence separately.', 'RVMuted'))
    evidence_rows=[]
    for b in project.barriers:
        for ev in b.evidence_items:
            file_label=Path(ev.file_path).name if ev.file_path else 'Reference only'
            evidence_rows.append([b.barrier_id,ev.evidence_id,ev.evidence_type,
                                  f'{ev.reference or file_label}\n{ev.description}',
                                  f'{ev.inspector or d.inspector}\n{ev.inspection_date or d.inspection_date}',
                                  ev.integrity_status()])
        if b.evidence_ref and not b.evidence_items:
            evidence_rows.append([b.barrier_id,'Legacy reference','Reference',b.evidence_ref,
                                  d.inspection_date,'Reference only'])
    story.append(_table(['Barrier','ID','Type','Reference / description','Inspector / date','Integrity'],
        evidence_rows,[66,62,65,148,93,76],styles))

    story.append(P('Measurement points and history','RVSection'))
    story.append(P('Readings are recorded observations, not a computed regulatory acceptance test. Corrected dose rates reflect RadVerify\'s stored gross-minus-background calculation, floored at zero.', 'RVMuted'))
    point_rows=[]
    for m in project.measurements:
        point_rows.append([m.point_id,m.location or '-',f'({m.x_m:g}, {m.y_m:g}, {m.height_m:g})',
                          str(len(m.measurement_history)),m.status])
    story.append(_table(['Point','Location','x/y/z (m)','Records','Latest status'],point_rows,[70,170,113,56,101],styles))
    history_rows=[]
    for m in project.measurements:
        if m.measurement_history:
            records=m.measurement_history
        elif m.reading_uSv_h is not None:
            records=[m]
        else:
            records=[]
        for rec in records:
            history_rows.append([
                f'{m.point_id}\n{getattr(rec,"record_id","Legacy")}',
                rec.measured_at or '-',
                f'{rec.instrument or "-"}\n{rec.instrument_id or ""}\nCal due: {rec.calibration_due_date or "not recorded"}',
                f'{_number(rec.reading_uSv_h)} / {_number(rec.background_uSv_h)} / {_number(rec.corrected_uSv_h)}',
                f'{rec.status}\n{rec.field_conditions}\n{rec.notes}',
            ])
    story.append(_table(['Point / record','When','Instrument / calibration','Gross / BG / corr. (uSv/h)','Assessment / conditions'],
        history_rows,[74,79,105,116,136],styles))

    story.append(P('Outstanding issues','RVSection'))
    issues=[[i.get('severity',''),i.get('area',''),i.get('item_id',''),i.get('issue','')]
            for i in summary['issues']]
    story.append(_table(['Severity','Area','Item','Issue'],issues,[67,80,90,273],styles))
    if d.notes.strip():
        story.append(P('Room notes','RVSection'))
        story.append(P(d.notes))
    story.append(Spacer(1,10))
    story.append(P('Document control: Generated from RadVerify field records. Review the source project and original photographs, instrument certificates, applicable legislation and any separate shielding assessment before issuing a professional opinion.', 'RVWarning'))
    fd, tmppath = tempfile.mkstemp(prefix='.radverify-report-',suffix='.pdf',dir=output.parent)
    os.close(fd)
    try:
        doc=_Doc(tmppath,d.project_id)
        doc.build(story)
        os.replace(tmppath,output)
    finally:
        if os.path.exists(tmppath):
            os.unlink(tmppath)
    return output
