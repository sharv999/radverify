from __future__ import annotations

import pytest

from app import RadVerifyApp
from radverify.models import BarrierInspection, RadVerifyProject
from radverify.radtwin import project_to_radtwin


@pytest.fixture(scope="module")
def app():
    root = RadVerifyApp()
    root.update()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def reset_app(app):
    project = RadVerifyProject()
    north = next(b for b in project.barriers if b.barrier_id == "N wall")
    north.expected_construction = "Lead sheet behind plasterboard"
    north.expected_pb_mm = 2.0
    north.observed_construction = ""
    north.observed_pb_mm = None
    north.status = "Not inspected"
    app.project = project
    app.current_file = None
    app._dirty = False
    app.load_project_into_ui()
    app.update()


def test_design_fields_are_read_only_and_loaded_from_design_layer(app):
    assert app.barrier_tab.select_barrier("N wall", focus_tab=True) is True
    assert app.barrier_tab.design_construction_var.get() == "Lead sheet behind plasterboard"
    assert app.barrier_tab.design_pb_var.get() == "2"
    assert str(app.barrier_tab.design_construction_entry.cget("state")) == "readonly"
    assert str(app.barrier_tab.design_pb_entry.cget("state")) == "readonly"


def test_save_changes_only_as_built_and_verification_layers(app):
    assert app.barrier_tab.select_barrier("N wall") is True
    app.barrier_tab.asbuilt_construction_var.set("Lead sheet, discontinuity at service penetration")
    app.barrier_tab.asbuilt_pb_var.set("1.5")
    app.barrier_tab.status_var.set("Fail")
    app.barrier_tab.evidence_var.set("IMG_0102")
    app.barrier_tab.notes_text.delete("1.0", "end")
    app.barrier_tab.notes_text.insert("1.0", "Gap requires remediation")

    assert app.barrier_tab.save_selected() is True
    north = next(b for b in app.project.barriers if b.barrier_id == "N wall")

    # Design intent must be immutable in the RadVerify editor.
    assert north.expected_construction == "Lead sheet behind plasterboard"
    assert north.expected_pb_mm == 2.0
    # Field observation / verification is updated independently.
    assert north.observed_construction == "Lead sheet, discontinuity at service penetration"
    assert north.observed_pb_mm == 1.5
    assert north.status == "Fail"
    assert north.evidence_ref == "IMG_0102"
    assert north.notes == "Gap requires remediation"
    assert app.barrier_tab.comparison_var.get().startswith("Differs:")
    assert "Pb -0.5 mm" in app.barrier_tab.comparison_var.get()

    twin = project_to_radtwin(app.project)
    north_twin = next(b for b in twin["barriers"] if b["id"] == "N wall")
    assert north_twin["design_specification"]["pb_equivalent_mm"] == 2.0
    assert north_twin["as_built"]["pb_equivalent_mm"] == 1.5
    assert north_twin["verification"]["status"] == "Fail"


def test_comparison_summary_distinguishes_match_difference_and_missing_data():
    b = BarrierInspection(
        barrier_id="N wall",
        expected_construction="1.5 mm Pb",
        expected_pb_mm=1.5,
        observed_construction="1.5 mm Pb",
        observed_pb_mm=1.5,
        status="Pass",
    )
    assert app_comparison(b) == "Matches design"

    b.observed_pb_mm = 1.0
    assert "Differs:" in app_comparison(b)
    assert "Pb -0.5 mm" in app_comparison(b)

    b = BarrierInspection(barrier_id="E wall", status="Not inspected")
    assert app_comparison(b) == "Not inspected"

    b = BarrierInspection(barrier_id="S wall", observed_construction="Concrete", status="Review")
    assert app_comparison(b) == "No design specification"


def app_comparison(barrier: BarrierInspection) -> str:
    # Keep the comparison contract unit-testable without creating another Tk root.
    from radverify.tabs import BarrierInspectionTab

    return BarrierInspectionTab.comparison_summary(barrier)


def test_table_exposes_design_and_as_built_as_separate_columns(app):
    assert app.barrier_tab.select_barrier("N wall") is True
    selected = app.barrier_tab.tree.selection()
    assert selected
    values = app.barrier_tab.tree.item(selected[0], "values")
    columns = dict(zip(app.barrier_tab.COLUMNS, values))
    assert columns["design"] == "Lead sheet behind plasterboard"
    assert str(columns["design_pb"]) == "2"
    assert columns["as_built"] == ""
    assert str(columns["as_built_pb"]) == ""
    assert columns["difference"] == "Not inspected"
