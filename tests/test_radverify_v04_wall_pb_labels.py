"""Floor-plan Pb-equivalent labelling must never confuse design and as-built."""
from __future__ import annotations

import pytest

from app import RadVerifyApp
from radverify.models import BarrierInspection, RadVerifyProject
from radverify.radtwin import project_to_radtwin
from radverify.tabs import floor_plan_wall_pb_labels


def _plan_labels(canvas, wall):
    return [canvas.itemcget(item, 'text') for item in canvas.find_withtag(wall)
            if canvas.type(item) == 'text']


def test_as_built_missing_does_not_inherit_design_or_status():
    north = BarrierInspection('N wall', expected_pb_mm=2.0, status='Pass')
    west = BarrierInspection('W wall', observed_pb_mm=1.5, expected_pb_mm=2.0, status='Review')
    as_built, design = floor_plan_wall_pb_labels([north, west, BarrierInspection('Floor')])
    assert as_built == {'N wall': 'As-built Pb eq: not recorded', 'W wall': 'As-built Pb eq: 1.5 mm'}
    assert design == {'N wall': 'Design Pb eq: 2 mm', 'W wall': 'Design Pb eq: 2 mm'}


def test_explicit_zero_is_not_mistaken_for_missing():
    as_built, design = floor_plan_wall_pb_labels([
        BarrierInspection('E wall', observed_pb_mm=0.0, expected_pb_mm=1.0),
        BarrierInspection('S wall', status='Not inspected'),
    ])
    assert as_built['E wall'] == 'As-built Pb eq: 0 mm'
    assert as_built['S wall'] == 'As-built Pb eq: not recorded'
    assert 'S wall' not in design


@pytest.fixture(scope='module')
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


def test_wall_labels_redraw_when_inspection_saves(app):
    project = RadVerifyProject()
    north = next(b for b in project.barriers if b.barrier_id == 'N wall')
    north.expected_pb_mm = 2.0
    north.status = 'Pass'
    app.project = project
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()

    assert 'As-built Pb eq: not recorded' in _plan_labels(app.floor_tab.canvas, 'N wall')
    assert 'Design Pb eq: 2 mm' in _plan_labels(app.floor_tab.canvas, 'N wall')
    app.floor_tab.set_selected_barrier('N wall')
    assert 'As-built Pb eq: not recorded' in app.floor_tab.selected_barrier_pb_var.get()

    app.barrier_tab.select_barrier('N wall')
    app.barrier_tab.asbuilt_construction_var.set('Lead-lined wall')
    app.barrier_tab.asbuilt_pb_var.set('1.5')
    app.barrier_tab.status_var.set('Fail')
    assert app.barrier_tab.save_selected() is True
    app.update()

    assert 'As-built Pb eq: 1.5 mm' in _plan_labels(app.floor_tab.canvas, 'N wall')
    assert 'Design Pb eq: 2 mm' in _plan_labels(app.floor_tab.canvas, 'N wall')
    assert 'As-built Pb eq: 1.5 mm' in app.floor_tab.selected_barrier_pb_var.get()
    assert project_to_radtwin(app.project)['barriers'][0]['as_built']['pb_equivalent_mm'] == 1.5
    assert project_to_radtwin(app.project)['barriers'][0]['design_specification']['pb_equivalent_mm'] == 2.0

    # Not-inspected E wall must remain unknown, even after another wall is verified.
    assert 'As-built Pb eq: not recorded' in _plan_labels(app.floor_tab.canvas, 'E wall')
