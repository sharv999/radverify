"""Field UI room-geometry editability: RadShield-style dimension controls."""
from __future__ import annotations

import pytest

from app import RadVerifyApp
from geometry.geometry_model import Opening
from radverify.models import MeasurementPoint, RadVerifyProject
from radverify.radtwin import project_to_radtwin, project_from_radtwin


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset(app):
    app.project = RadVerifyProject()
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update_idletasks()


def test_floor_plan_edit_updates_shared_geometry_room_details_and_twin(app):
    panel = app.floor_tab
    panel.dimension_vars["width_m"].set("7.2")
    assert panel.commit_dimension("width_m") is True
    panel.dimension_vars["length_m"].set("4.6")
    assert panel.commit_dimension("length_m") is True
    panel.dimension_vars["height_m"].set("2.9")
    assert panel.commit_dimension("height_m") is True
    g = app.project.geometry
    assert (g.width_m, g.length_m, g.height_m) == (7.2, 4.6, 2.9)
    assert [app.room_tab.vars[k].get() for k in ("width_m", "length_m", "height_m")] == ["7.2", "4.6", "2.9"]
    dims = project_to_radtwin(app.project)["geometry"]["dimensions_m"]
    assert dims == {"south_north": 4.6, "west_east": 7.2, "height": 2.9}
    assert app._dirty is True


def test_nudge_uses_point_one_metre_and_respects_minimum(app):
    tab = app.floor_tab
    start = app.project.geometry.width_m
    assert tab.nudge_dimension("width_m", 0.1)
    assert app.project.geometry.width_m == pytest.approx(start + 0.1)
    tab.dimension_vars["width_m"].set("0.5")
    assert tab.commit_dimension("width_m")
    assert tab.nudge_dimension("width_m", -0.1)
    assert app.project.geometry.width_m == pytest.approx(0.5)


def test_invalid_input_restores_previous_dimension_without_mutation(app):
    tab = app.floor_tab
    current = app.project.geometry.height_m
    for bad in ("0", "-2", "nan", "inf", "abc"):
        tab.dimension_vars["height_m"].set(bad)
        assert tab.commit_dimension("height_m") is False
        assert app.project.geometry.height_m == current
        assert tab.dimension_vars["height_m"].get() == f"{current:g}"
    assert app._dirty is False


def test_room_details_and_import_refresh_floor_plan_editors(app):
    app.room_tab.vars["height_m"].set("3.1")
    app.room_tab.vars["width_m"].set("6.5")
    app.room_tab.apply_to_model()
    assert app.floor_tab.dimension_vars["height_m"].get() == "3.1"
    assert app.floor_tab.dimension_vars["width_m"].get() == "6.5"
    imported = project_from_radtwin(project_to_radtwin(app.project))
    app.project = imported
    app.load_project_into_ui()
    assert app.floor_tab.dimension_vars["width_m"].get() == "6.5"
    assert app.room_tab.vars["height_m"].get() == "3.1"


def test_resizing_cannot_strand_measurements_or_openings(app):
    g = app.project.geometry
    g.openings.append(Opening(id="D-N1", wall="N", offset_m=4.8, width_m=0.9))
    app.project.measurements.append(MeasurementPoint(point_id="MP-01", x_m=5.0, y_m=2.0))
    g.width_m = 6.0
    app.floor_tab.load_dimensions()
    app.room_tab.load_dimensions()
    app.floor_tab.dimension_vars["width_m"].set("5.0")
    assert app.floor_tab.commit_dimension("width_m") is False
    assert g.width_m == 6.0
    assert app.floor_tab.dimension_vars["width_m"].get() == "6"
    # A matching edit in Room Details also must not leave the door outside.
    app.room_tab.vars["width_m"].set("5.0")
    app.room_tab.apply_to_model()
    assert g.width_m == 6.0
    assert app.room_tab.vars["width_m"].get() == "6"
    g.openings.clear()
    app.project.measurements.clear()
    app.floor_tab.dimension_vars["width_m"].set("5.0")
    assert app.floor_tab.commit_dimension("width_m") is True
    assert g.width_m == 5.0


def test_opening_offset_is_centre_not_edge(app):
    g = app.project.geometry
    # The half width must be used when checking whether the opening fits.
    g.openings.append(Opening(id="D-N2", wall="N", offset_m=4.5, width_m=0.8))
    app.floor_tab.dimension_vars["width_m"].set("5.0")
    assert app.floor_tab.commit_dimension("width_m") is True
    assert g.width_m == 5.0
    app.floor_tab.dimension_vars["width_m"].set("4.8")
    assert app.floor_tab.commit_dimension("width_m") is False
    assert g.width_m == 5.0


def test_height_reduction_cannot_strand_measurement_or_opening(app):
    g = app.project.geometry
    app.project.measurements.append(MeasurementPoint(point_id="MP-high", x_m=1.0, y_m=1.0, height_m=2.5))
    app.floor_tab.dimension_vars["height_m"].set("2.4")
    assert app.floor_tab.commit_dimension("height_m") is False
    assert g.height_m == 2.7
    app.project.measurements.clear()
    g.openings.append(Opening(id="D-high", wall="N", offset_m=1.0, width_m=0.9, head_height_above_ffl_m=2.4))
    app.floor_tab.dimension_vars["height_m"].set("2.3")
    assert app.floor_tab.commit_dimension("height_m") is False
    assert g.height_m == 2.7
    app.floor_tab.dimension_vars["height_m"].set("2.5")
    assert app.floor_tab.commit_dimension("height_m") is True
