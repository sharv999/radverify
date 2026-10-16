from __future__ import annotations

from engine.shielding_engine import build_example_project, compute_room_barrier_table
from models.shielding_models import Source
from tabs.results_barrier_maps import get_barrier_dose_label_map, get_barrier_risk_map
from tabs.results_tab_rendering import refresh_barrier_schedule


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Tree:
    def __init__(self):
        self.items = ["stale-result"]

    def get_children(self):
        return tuple(self.items)

    def delete(self, item):
        self.items.remove(item)


class App:
    BARRIER_COLUMNS = ()

    def __init__(self, project, room):
        self.project = project
        self.room = room
        self.global_energy_var = Var("120 kVp")
        self.solver_mode_var = Var("auto")
        self.barriers_room_var = Var(room.name)
        self.barrier_table = Tree()
        self.barrier_risk_table = Tree()
        self.barrier_risk_summary_var = Var()
        self.status = ""

    def _repair_invalid_source_inventory(self):
        return None

    def _sanitize_all_nm_patient_sources(self):
        return None

    def _apply_geometry_to_selected_room_barriers(self, room):
        return None

    def get_room_by_name(self, name):
        return self.room if name == self.room.name else None

    def get_sources_for_room(self, room_name):
        return [src for src in self.project.sources if src.room_name == room_name]

    def get_room_barrier_results(self, room):
        return compute_room_barrier_table(
            self.project,
            room.name,
            self.global_energy_var.get(),
            solver_mode=self.solver_mode_var.get(),
        )

    def set_status(self, message):
        self.status = message


def _valid_ct_source(room_name: str) -> Source:
    source = Source(
        name="Secondary scatter source diagnostic",
        source_type="ct_scatter",
        radiation_type="xray_120kvp",
        params={
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex / Apex Elite",
            "scanner_family": "GE_REVOLUTION_APEX_FAMILY",
            "scanner_phantom": "body",
            "scanner_kvp": "140",
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "manual_ksec_override": "0",
            "scanner_source": "JSON worst-case Ksec lookup",
        },
    )
    source.room_name = room_name
    return source


def test_switching_to_null_ksec_invalidates_table_canvas_maps_and_displays_block_message():
    project = build_example_project()
    room = project.rooms[0]
    source = _valid_ct_source(room.name)
    project.sources = [source]
    room.sources = [source]
    app = App(project, room)

    # Valid scanner state calculates and produces current Geometry overlay data.
    assert compute_room_barrier_table(project, room.name, "120 kVp")
    assert get_barrier_risk_map(app, room.name)
    assert get_barrier_dose_label_map(app, room.name)

    # User switches to a scanner whose database ksec is NULL.
    source.params.update(
        {
            "scanner_vendor": "Philips",
            "scanner_model": "Philips Brilliance 64",
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "ksec_mGy_per_100mAs_at_1m": "",
            "manual_ksec_override": "0",
            "scanner_source": "NULL ksec — manual override required",
        }
    )

    refresh_barrier_schedule(app)

    # Stale table rows and all calculated Geometry overlays are invalidated.
    assert app.barrier_table.get_children() == ()
    assert app.barrier_risk_table.get_children() == ()
    assert get_barrier_risk_map(app, room.name) == {}
    assert get_barrier_dose_label_map(app, room.name) == {}

    # The blocked state is explicit rather than appearing as an unexplained blank table.
    assert "Calculation blocked" in app.barrier_risk_summary_var.get()
    assert "manual ksec override" in app.barrier_risk_summary_var.get()
    assert app.status == app.barrier_risk_summary_var.get()
