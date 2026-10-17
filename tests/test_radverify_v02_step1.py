from __future__ import annotations

import pytest

from geometry.geometry_model import Opening
from radverify.models import MeasurementPoint, RadVerifyProject
from app import RadVerifyApp


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset_app(app):
    app.project = RadVerifyProject()
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()



def _selected_first_value(tree):
    sel = tree.selection()
    assert sel
    values = tree.item(sel[0], "values")
    assert values
    return str(values[0])


def test_floor_plan_barrier_selection_syncs_to_inspection_table(app):
        app.update_idletasks()
        assert app.floor_tab.set_selected_barrier("N wall") is True
        assert app.floor_tab.selected_barrier_id == "N wall"
        assert _selected_first_value(app.barrier_tab.tree) == "N wall"

        app.floor_tab.set_selected_barrier_status("Pass")
        barrier = next(b for b in app.project.barriers if b.barrier_id == "N wall")
        assert barrier.status == "Pass"
        assert app.floor_tab.selected_barrier_status_var.get() == "Status: Pass"


def test_barrier_table_selection_syncs_back_to_floor_plan(app):
        app.update_idletasks()
        assert app.barrier_tab.select_barrier("E wall", sync_floor=True) is True
        assert app.floor_tab.selected_barrier_id == "E wall"


def test_measurement_selection_syncs_between_floor_plan_and_table(app):
        app.project.measurements.append(MeasurementPoint(point_id="MP01", x_m=2.0, y_m=1.0))
        app.measurement_tab.refresh()
        app.floor_tab.redraw()
        assert app.floor_tab.set_selected_measurement("MP01") is True
        assert app.floor_tab.selected_measurement_id == "MP01"
        assert _selected_first_value(app.measurement_tab.tree) == "MP01"


def test_wall_hit_testing_uses_room_perimeter(app):
        app.notebook.select(app.floor_tab)
        app.update()
        app.floor_tab.redraw()
        app.update_idletasks()
        metrics = app.floor_tab._layout_metrics()
        cx = (metrics["x0"] + metrics["x1"]) / 2
        cy = (metrics["y0"] + metrics["y1"]) / 2
        assert app.floor_tab._wall_target_at(cx, metrics["y0"]) == "N wall"
        assert app.floor_tab._wall_target_at(cx, metrics["y1"]) == "S wall"
        assert app.floor_tab._wall_target_at(metrics["x0"], cy) == "W wall"
        assert app.floor_tab._wall_target_at(metrics["x1"], cy) == "E wall"
        assert app.floor_tab._wall_target_at(cx, cy) is None


def test_opening_hit_testing_returns_opening_barrier_id(app):
        app.project.geometry.openings.append(
            Opening(wall="S", opening_type="door", offset_m=2.0, width_m=0.9, label="D1", id="D1")
        )
        app.project.sync_opening_inspections()
        app.notebook.select(app.floor_tab)
        app.update()
        app.floor_tab.redraw()
        app.update_idletasks()
        bbox = app.floor_tab.canvas.bbox("D1")
        assert bbox is not None
        x = (bbox[0] + bbox[2]) / 2
        # Use the opening rectangle itself rather than the full label bbox.
        room = app.floor_tab._layout_metrics()
        y = room["y1"]
        assert app.floor_tab.barrier_target_at(x, y) == "D1"


def test_planar_and_wall_labels_are_clickable_barrier_targets(app):
        app.notebook.select(app.floor_tab)
        app.update()
        app.floor_tab.redraw()
        app.update_idletasks()
        for barrier_id in ("Floor", "Ceiling", "N wall"):
            bbox = app.floor_tab.canvas.bbox(barrier_id)
            assert bbox is not None
            x = (bbox[0] + bbox[2]) / 2
            y = (bbox[1] + bbox[3]) / 2
            assert app.floor_tab.barrier_target_at(x, y) == barrier_id
