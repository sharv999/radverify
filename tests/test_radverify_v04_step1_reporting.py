"""Draft field verification reporting contract; no Tk needed."""
from __future__ import annotations

from pathlib import Path
import pytest
from radverify.models import RadVerifyProject, MeasurementPoint, MeasurementRecord, EvidenceItem
from radverify.reporting import build_verification_pdf, FloorPlan
from geometry.geometry_model import Opening


def test_incomplete_default_room_generates_pdf_without_certifying(tmp_path):
    p=RadVerifyProject()
    path=build_verification_pdf(p,tmp_path/'default.pdf',generated_at='2026-10-19 09:00 AEST')
    assert path.exists() and path.stat().st_size > 3500
    import fitz
    with fitz.open(path) as doc:
        text='\n'.join(page.get_text() for page in doc)
    assert 'NOT A COMPLIANCE CERTIFICATE' in text
    assert 'Not ready' in text
    assert 'Not inspected' in text
    assert 'No measurement points recorded' in text
    assert 'Room floor plan' in text


def test_asbuilt_evidence_history_and_asymmetric_geometry_are_reported(tmp_path):
    p=RadVerifyProject()
    p.details.project_id='FIELD-2026-008'
    p.details.site_name='Example & <Hospital>'
    p.details.inspector='Inspector A'
    p.details.room_name='CT East'
    p.geometry.width_m=7.2
    p.geometry.length_m=4.6
    p.geometry.height_m=2.9
    p.geometry.source.x_m=2.1
    p.geometry.source.y_m=3.2
    p.geometry.source.label='CT Source'
    p.geometry.openings=[Opening(id='D-W1',wall='W',opening_type='door',offset_m=1.3,width_m=1.0),Opening(id='VP-N1',wall='N',opening_type='viewing_panel',offset_m=5.6,width_m=1.2)]
    p.sync_opening_inspections()
    north=next(b for b in p.barriers if b.barrier_id=='N wall')
    north.expected_pb_mm=2.0
    north.observed_pb_mm=1.5
    north.expected_construction='Design Pb'
    north.observed_construction='As-built Pb'
    north.status='Fail'
    north.notes='Wall gap near cable tray'
    evpath=tmp_path/'north.txt'
    evpath.write_text('image evidence')
    ev=EvidenceItem(evidence_id='EV-N01',file_path=str(evpath),reference='IMG_101')
    ev.refresh_hash()
    north.evidence_items=[ev]
    point=MeasurementPoint(point_id='MP-01',x_m=1.1,y_m=2.0,location='Entry')
    for idx,val in enumerate((0.2,0.4),start=1):
        point.add_measurement_record(MeasurementRecord(record_id=f'MP-01-M{idx:02d}',measured_at='2026-10-19',instrument='Meter X',reading_uSv_h=val,background_uSv_h=0.1,status='Review',field_conditions=f'Condition {idx}'))
    p.measurements=[point]
    output=build_verification_pdf(p,tmp_path/'draft.pdf',generated_at='2026-10-19 09:00 AEST')
    import fitz
    with fitz.open(output) as doc:
        text='\n'.join(page.get_text() for page in doc)
    for token in ['FIELD-2026-008','Example & <Hospital>','As-built Pb','2', '1.5','Fail','Wall gap near cable tray','EV-N01','Verified','MP-01-M01','MP-01-M02','Condition 2','7.2 m','4.6 m','D-W1','VP-N1']:
        assert token in text, (token,text)
    # Absolute local evidence paths are not copied into client-facing reports.
    assert str(tmp_path) not in text


def test_failed_export_does_not_overwrite_existing_report(tmp_path,monkeypatch):
    p=RadVerifyProject()
    output=tmp_path/'existing.pdf'
    output.write_bytes(b'prior approved report')
    from radverify import reporting
    def fail(*args,**kwargs):
        raise RuntimeError('test failure')
    monkeypatch.setattr(reporting._Doc,'build',fail)
    with pytest.raises(RuntimeError,match='test failure'):
        build_verification_pdf(p,output)
    assert output.read_bytes()==b'prior approved report'
    assert not list(tmp_path.glob('.radverify-report-*'))
