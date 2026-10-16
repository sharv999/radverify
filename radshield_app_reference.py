from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import data

from models.shielding_models import Source, Barrier, Room, Project
from engine.shielding_engine import (
    AREA_PRESETS,
    DEFAULT_NM_TCM99M_SOURCE_FACTORS,
    DEFAULT_PATIENT_DOSE_CONSTANT_USV_H_PER_MBQ_AT_1M,
    ENERGY_OPTIONS,
    MATERIAL_OPTIONS,
    CT_SCATTER_PRESETS,
    XRAY_PRESETS,
    SOLVER_MODE_AUTO,
    SOLVER_MODE_NCRP,
    SOLVER_MODE_MU,
    SOLVER_MODE_OPTIONS,
    auto_select_tvl_key,
    build_example_project,
    compute_room_barrier_table,
    compute_ct_source_summary,
    compute_room_source_summary,
    compute_source_weekly_dose_at_1m,
    default_barriers,
    compute_xray_ncrp_simplified_source_summary,
    calc_barrier_result,
)
from engine.design_constraints import (
    get_room_constraint_profile,
    get_barrier_design_defaults,
    build_room_constraint_summary,
    room_sources_match_profile,
)
from modalities.registry import (
    non_production_plugin_stub_names,
    is_production_modality,
    locked_source_mapping,
    production_modality_names,
    initialise_modality_services,
    handle_source_form_event,
)
from engine.barrier_optimizer import optimise_flagged_barriers

from reports.report_generator import generate_report_from_app
from geometry.geometry_model import RoomGeometry
from tabs.geometry_tab import GeometryTab

from engine.normalization import normalize_source_params
from geometry.geometry_model import RoomGeometry, RadiationSourceGeometry

from tabs.barriers_tab import BarrierInlineEditor
from sources.source_form_sync import SourceFormSyncMixin, sync_project_state_for_save
from sources.source_factory import SourceFactoryMixin
from sources.source_validation import SourceValidationMixin

from geometry.geometry_model import (
    RoomGeometry,
    RadiationSourceGeometry,
)
from config.geometry_constants import *

class ShieldingDesktopApp(
    SourceFactoryMixin,
    SourceValidationMixin,
    SourceFormSyncMixin,
    tk.Tk,
):

    ROOM_TYPES = production_modality_names()
    NON_PRODUCTION_PLUGIN_STUBS = non_production_plugin_stub_names()

    # Production source inventory comes from the modality registry.
    # Step 34 admits SPECT through the same registry-driven host path as CT;
    # modality-specific issued-output gates remain separate from room eligibility.
    LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)
    BARRIER_EDIT_COLUMNS = [
        "name",
        "thickness_mm",
        "material",
        "barrier_role",
        "distance_m",
        "occupancy_factor",
        "design_goal_uSv_per_week",
        "unshielded_weekly_dose_uSv",
        "transmitted_dose_uSv_per_week",
    ]

    BARRIER_RESULT_COLUMNS = [
        "barrier_transmission_factor_B",
        "display_required_thickness_mm",
        "solver_used",
        "compliance_status",
    ]

    BARRIER_COLUMNS = (
        BARRIER_EDIT_COLUMNS
        + BARRIER_RESULT_COLUMNS
    )

    def __init__(self):
        super().__init__()
        self.title("Shielding Assessment Desktop App")
        self.geometry("1600x980")
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                self.geometry(f"{sw}x{sh}+0+0")
        self.project = build_example_project()
        self._prune_unsupported_rooms()
        self.current_file: Optional[Path] = None
        self.inline_editor: Optional[BarrierInlineEditor] = None
        self.source_form_drafts: Dict[str, Dict[str, Any]] = {}
        self.last_selected_source_index: Optional[int] = None
        self.last_selected_source_room_name: Optional[str] = None
        self.current_source_index: Optional[int] = None
        self.current_room_index: Optional[int] = None
        self._loading_room_form = False
        self._loading_source_form = False
        self._source_dirty = False
        self.ct_db = None
        self.spect_ct_db = None
        initialise_modality_services(self, Path(__file__).resolve().parent)
        self.solver_mode_var = tk.StringVar(value=SOLVER_MODE_AUTO)
        self.room_constraint_summary: Dict[str, Any] = {}

        self.optimizer_last_recommendations: list[Dict[str, Any]] = []
        self.heatmap_mode_var = tk.BooleanVar(value=False)

        self._configure_app_style()
        self._build_ui()
        self.refresh_all()


# ------------------------------------------------------------------------
#                              HELPER FUNCTIONS
# ------------------------------------------------------------------------

    def _coerce_barrier_schema(self, barrier: Barrier) -> None:
        from services.barrier_schema import coerce_barrier_schema

        return coerce_barrier_schema(barrier)

    def _coerce_project_barrier_schema(self) -> None:
        for room in getattr(self.project, "rooms", []) or []:
            for barrier in getattr(room, "barriers", []) or []:
                self._coerce_barrier_schema(barrier)


    def _apply_room_constraint_defaults(self, room: Room) -> None:
        from services.room_defaults import apply_room_constraint_defaults

        return apply_room_constraint_defaults(self, room)


    def _room_constraint_text(self, room: Optional[Room]) -> str:
        if not room:
            return ""
        summary = build_room_constraint_summary(room.modality)
        return (
            f"Classification: {summary['classification']} | "
            f"Energy default: {summary['default_energy_label']} | "
            f"Solver default: {summary['default_solver_mode']} | "
            f"Expected sources: {', '.join(summary['expected_source_types'])}"
        )


    def _room_sources_are_locked(self, room: Optional[Room]) -> bool:
        return bool(room and room.modality in self.LOCKED_MODALITY_SOURCES)


    def enforce_room_source_types(self, room: Room) -> None:
        from sources.room_source_enforcement import enforce_room_source_types

        return enforce_room_source_types(self, room)
    

    def _apply_geometry_to_selected_room_barriers(self, room: Room) -> None:
        from geometry.barrier_sync import apply_geometry_to_selected_room_barriers

        return apply_geometry_to_selected_room_barriers(self, room)


    def _get_current_source(self) -> Optional[Source]:
        from tabs.source_ct_actions import get_current_source

        return get_current_source(self)

    def _configure_source_type_combo_for_room(self, room: Optional[Room]) -> None:
        """Constrain the source-type dropdown to valid choices for the selected room."""
        if not hasattr(self, "source_type_combo"):
            return
        allowed = self._allowed_source_types_for_room(room)
        try:
            self.source_type_combo["values"] = allowed
        except Exception:
            return
        if allowed and str(self.source_type_var.get()).strip() not in allowed:
            self.source_type_var.set(allowed[0])

    def _reload_source_ui_from_model(
        self,
        room: Optional[Room] = None,
        source_index: Optional[int] = None,
        refresh_live: bool = True,
    ) -> None:
        from tabs.source_form_state import reload_source_ui_from_model

        return reload_source_ui_from_model(
            self,
            room=room,
            source_index=source_index,
            refresh_live=refresh_live,
        )

    def _update_sources_readonly_state(self) -> None:
        from tabs.source_ct_actions import update_sources_readonly_state

        return update_sources_readonly_state(self)

    def on_source_selector_vendor_change(self, event=None):
        if getattr(self, "_loading_source_form", False):
            return
        source_type = self.source_type_var.get().strip()
        handle_source_form_event(self, "vendor_changed", source_type)
        self.on_source_input_change()

    def on_source_selector_model_change(self, event=None):
        if getattr(self, "_loading_source_form", False):
            return
        source_type = self.source_type_var.get().strip()
        handle_source_form_event(self, "model_changed", source_type)
        self.on_source_input_change()

    def on_source_selector_energy_change(self, *args):
        if getattr(self, "_loading_source_form", False):
            return
        source_type = self.source_type_var.get().strip()
        handle_source_form_event(self, "energy_changed", source_type)
        self.on_source_input_change()

    def refresh_selected_source_resolution(self, force: bool = False, source_type: str | None = None):
        stype = str(source_type or self.source_type_var.get().strip())
        return handle_source_form_event(self, "resolve", stype, force=force)

 
    def _build_ui(self):
        from ui.main_window import build_ui

        return build_ui(self)
    def set_status(self, msg: str):
        self.status_var.set(msg)
        self.update_idletasks()


    def _configure_app_style(self):
        from ui.app_style import configure_app_style

        return configure_app_style(self)


    def _configure_source_calc_text_tags(self) -> None:
        from tabs.source_live_preview import configure_source_calc_text_tags

        return configure_source_calc_text_tags(self)


    def _source_calc_line_tags(self, line: str) -> tuple[str, ...]:
        from tabs.source_live_preview import source_calc_line_tags

        return source_calc_line_tags(self, line)


    def _insert_source_calc_lines(self, lines: list[str]) -> None:
        from tabs.source_live_preview import insert_source_calc_lines

        return insert_source_calc_lines(self, lines)


    def _build_project_tab(self):
        from tabs.project_tab_layout import build_project_tab

        return build_project_tab(self)


    def create_default_room_geometry(self, room_name: str, modality: str = "CT") -> RoomGeometry:
        from geometry.default_room_geometry import create_default_room_geometry

        return create_default_room_geometry(room_name=room_name, modality=modality)

    def jump_to_barrier(self, room_name: str, barrier_name: str):
        from tabs.barriers_optimizer import jump_to_barrier

        return jump_to_barrier(self, room_name, barrier_name)


    def refresh_barrier_schedule(self):
        from tabs.results_tab_rendering import refresh_barrier_schedule

        return refresh_barrier_schedule(self)


    def _build_sources_tab(self):
        from tabs.source_tab_layout import build_sources_tab

        return build_sources_tab(self)


    def on_source_type_change(self):
        from tabs.source_ct_actions import on_source_type_change

        return on_source_type_change(self)

    def center_row(self, table, iid):
        table.update_idletasks()
        bbox = table.bbox(iid)
        if not bbox:
            return
        y = bbox[1]
        height = table.winfo_height()
        table.yview_moveto(max(0, (y - height // 2) / max(1, table.bbox(table.get_children()[-1])[1])))

    def _clear_source_form_container(self):
        from tabs.source_form_layout import clear_source_form_container

        return clear_source_form_container(self)

    def _validate_integer_input(self, proposed: str) -> bool:
        from tabs.source_form_layout import validate_integer_input

        return validate_integer_input(self, proposed)

    def _format_integer_var_on_focus_out(self, variable):
        from tabs.source_form_layout import format_integer_var_on_focus_out

        return format_integer_var_on_focus_out(self, variable)

    def _make_readonly_entry(self, parent, variable):
        from tabs.source_form_layout import make_readonly_entry

        return make_readonly_entry(self, parent, variable)

    def _add_labeled_readonly_entry(self, parent, row, label, variable):
        from tabs.source_form_layout import add_labeled_readonly_entry

        return add_labeled_readonly_entry(self, parent, row, label, variable)

    def _make_integer_entry(self, parent, variable):
        from tabs.source_form_layout import make_integer_entry

        return make_integer_entry(self, parent, variable)

    def _add_labeled_entry(self, parent, row, label, variable):
        from tabs.source_form_layout import add_labeled_entry

        return add_labeled_entry(self, parent, row, label, variable)

    def _add_labeled_integer_entry(self, parent, row, label, variable):
        from tabs.source_form_layout import add_labeled_integer_entry

        return add_labeled_integer_entry(self, parent, row, label, variable)

    def _is_supported_modality(self, modality: str) -> bool:
        return is_production_modality(modality)

    def _prune_unsupported_rooms(self) -> None:
        """Keep only production-enabled modality rooms in the active project.

        Modalities become selectable by enabling their registry entries, not by
        adding hard-coded modality checks here. Step 34 deliberately relies on
        this generic path for controlled SPECT host integration.
        """
        rooms = getattr(self.project, "rooms", []) or []
        filtered = [room for room in rooms if self._is_supported_modality(getattr(room, "modality", ""))]
        self.project.rooms = filtered

    def update_auto_tvl_key_display(self):
        from tabs.source_form_layout import update_auto_tvl_key_display

        return update_auto_tvl_key_display(self)
    


    def on_source_input_change(self, *args):
        from tabs.source_ct_actions import on_source_input_change

        return on_source_input_change(self, *args)

    def update_live_source_preview_from_form(self):
        from tabs.source_live_preview import update_live_source_preview_from_form

        return update_live_source_preview_from_form(self)

    def save_current_source_form_draft(self):
        stype = self.source_type_var.get().strip()
        if not stype:
            return

        try:
            self.source_form_drafts[stype] = self.collect_source_params_from_form(stype)
        except Exception:
            pass

    def load_source_form_draft(self, stype: str):
        from tabs.source_ct_state import load_source_form_draft

        return load_source_form_draft(self, stype)

    def refresh_source_form_by_type(self):
        from tabs.source_form_layout import refresh_source_form_by_type

        return refresh_source_form_by_type(self)

    def _build_barriers_tab(self):
        from tabs.barriers_tab_layout import build_barriers_tab

        return build_barriers_tab(self)

   
    def render_barrier_risk_panel(self, room, room_results=None):
        from tabs.results_tab_rendering import render_barrier_risk_panel

        return render_barrier_risk_panel(self, room, room_results=room_results)


    def _build_results_tab(self):
        from tabs.results_tab_layout import build_results_tab

        return build_results_tab(self)


    def _safe_float_or_none(self, value):
        from tabs.results_tab_text import safe_float_or_none

        return safe_float_or_none(value)

    def _fmt_mm(self, x, decimals=2):
        from tabs.results_tab_text import fmt_mm

        return fmt_mm(x, decimals=decimals)

    def _fmt_delta(self, x):
        from tabs.results_tab_text import fmt_delta

        return fmt_delta(x)

    def _parse_source_contribution_parts(self, contributions: Any) -> list[tuple[str, Optional[float], str]]:
        from tabs.results_tab_text import parse_source_contribution_parts

        return parse_source_contribution_parts(contributions)


    def _largest_contribution_label(self, contributions: Any) -> str:
        from tabs.results_tab_text import largest_contribution_label

        return largest_contribution_label(contributions)


    def _canonical_source_label(self, label: str) -> str:
        from tabs.results_tab_text import canonical_source_label

        return canonical_source_label(label)


    def _status_summary_text(self, status: str) -> str:
        from tabs.results_tab_text import status_summary_text

        return status_summary_text(status)


    def _fmt_material_with_mm(self, material: str, thickness_mm: Optional[float]) -> str:
        from tabs.results_tab_text import fmt_material_with_mm

        return fmt_material_with_mm(material, thickness_mm)


    def _dominant_reason_text(self, contributions: Any) -> str:
        from tabs.results_tab_text import dominant_reason_text

        return dominant_reason_text(contributions)


    def _build_live_results_lines(self):
        from tabs.results_tab_rendering import build_live_results_lines

        return build_live_results_lines(self)


    def refresh_results_tab(self):
        from tabs.results_tab_rendering import refresh_results_tab

        return refresh_results_tab(self)


    def _row_confidence_from_live(self, barrier_name: str, live):
        from tabs.results_tab_rendering import row_confidence_from_live

        return row_confidence_from_live(self, barrier_name, live)
    

# ------------------------------------------------------------------------
#                                  FUNCTIONS
# ------------------------------------------------------------------------

    def new_project(self):
        from tabs.project_tab_actions import new_project

        return new_project(self)

    def open_project(self):
        from tabs.project_tab_actions import open_project

        return open_project(self)

    def save_project(self):
        from tabs.project_tab_actions import save_project

        return save_project(self)

    def save_project_as(self):
        from tabs.project_tab_actions import save_project_as

        return save_project_as(self)


    def apply_project_form(self):
        from tabs.project_tab_actions import apply_project_form

        return apply_project_form(self)
    

    def get_selected_room_index(self) -> int | None:
        from tabs.project_tab_actions import get_selected_room_index

        return get_selected_room_index(self)


    def refresh_project_form(self):
        from tabs.project_tab_actions import refresh_project_form

        return refresh_project_form(self)


    def refresh_single_room_state(self):
        from tabs.project_tab_actions import refresh_single_room_state

        return refresh_single_room_state(self)


    def on_room_form_change(self, *_):
        from tabs.project_tab_actions import on_room_form_change

        return on_room_form_change(self, *_)


    def load_selected_room(self, _event=None):
        from tabs.project_tab_actions import load_selected_room

        return load_selected_room(self, _event)


    def apply_room_form(self):
        from tabs.project_tab_actions import apply_room_form

        return apply_room_form(self)


    def get_room_barrier_results(self, room):
        return compute_room_barrier_table(
            self.project,
            room.name,
            self.global_energy_var.get(),
            solver_mode=self.solver_mode_var.get(),
        )

    def get_room_results_model(self, room):
        """Return the canonical in-app Results model for the room's active modality."""
        from services.pet_results_model import build_room_results_model as build_pet_results_model
        from services.spect_results_model import build_room_results_model as build_spect_results_model
        from services.xray_results_model import build_xray_results_model
        from services.room_results_dispatch import build_active_room_results_model

        return build_active_room_results_model(
            self.project,
            room,
            pet_builder=build_pet_results_model,
            spect_builder=build_spect_results_model,
            xray_builder=build_xray_results_model,
            generic_builder=self.get_room_barrier_results,
        )


    def get_room_by_name(self, name: str) -> Optional[Room]:
        for room in self.project.rooms:
            if room.name == name:
                return room
        return None

    def get_sources_for_room(self, room_name: str) -> list[Source]:
        room_name = str(room_name or "").strip()
        return [
            src for src in getattr(self.project, "sources", []) or []
            if str(getattr(src, "room_name", "")).strip() == room_name
        ]


    def refresh_sources_list(self, preserve_index: int | None = None):
        from tabs.source_tab_actions import refresh_sources_list

        return refresh_sources_list(self, preserve_index=preserve_index)


    def get_selected_source_index(self) -> int | None:
        from tabs.source_tab_actions import get_selected_source_index

        return get_selected_source_index(self)


    def on_sources_room_change(self, *_):
        from tabs.source_tab_actions import on_sources_room_change

        return on_sources_room_change(self, *_)


    def clear_source_form(self):
        from tabs.source_tab_actions import clear_source_form

        return clear_source_form(self)


    def on_source_form_change(self, *_):
        from tabs.source_tab_actions import on_source_form_change

        return on_source_form_change(self, *_)


    def persist_previous_selected_source(self):
        from tabs.source_tab_actions import persist_previous_selected_source

        return persist_previous_selected_source(self)


    def load_selected_source(self, _event=None):
        from tabs.source_tab_actions import load_selected_source

        return load_selected_source(self, _event=_event)


    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            s = str(value).strip()
            if s == "":
                return float(default)
            return float(s)
        except Exception:
            return float(default)

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            s = str(value).strip()
            if s == "":
                return int(default)
            return int(float(s))
        except Exception:
            return int(default)

    def _safe_auto_select_tvl_key(self, source_type: str, params: Dict[str, Any], fallback: str = "") -> str:
        try:
            return auto_select_tvl_key(source_type, params, fallback)
        except Exception:
            return fallback or self.radiation_type_var.get().strip() or "xray_120kvp"

    def _repair_invalid_source_inventory(self):
        from sources.source_inventory_repair import repair_invalid_source_inventory

        return repair_invalid_source_inventory(self)

    def _sanitize_all_nm_patient_sources(self):
        # Backward-compatible method name; sanitisation is plugin-owned.
        from modalities.registry import sanitize_source_params_for_type

        for src in getattr(self.project, "sources", []) or []:
            source_type = str(getattr(src, "source_type", "") or "")
            src.params = sanitize_source_params_for_type(
                source_type,
                getattr(src, "params", {}) or {},
            )
            try:
                src.radiation_type = self._safe_auto_select_tvl_key(
                    source_type,
                    src.params,
                    getattr(src, "radiation_type", ""),
                )
            except Exception:
                pass


    def add_source(self):
        from tabs.source_tab_actions import add_source

        return add_source(self)


    def delete_source(self):
        from tabs.source_tab_actions import delete_source

        return delete_source(self)


    def update_source_options(self):
        from tabs.source_tab_actions import update_source_options

        return update_source_options(self)


    def sync_current_source_to_model(self, ignore_errors: bool = False):
        from tabs.source_tab_actions import sync_current_source_to_model

        return sync_current_source_to_model(self, ignore_errors=ignore_errors)
    

    def apply_source_form(self):
        from tabs.source_tab_actions import apply_source_form

        return apply_source_form(self)


    def refresh_source_calculations(self):
        from tabs.source_tab_actions import refresh_source_calculations

        return refresh_source_calculations(self)


    def geometry_changed(self):
        from geometry.barrier_sync import geometry_changed

        return geometry_changed(self)


    def add_barrier(self):
        from tabs.barriers_tab_actions import add_barrier

        return add_barrier(self)
    

    def delete_selected_barrier_from_table(self):
        from tabs.barriers_tab_actions import delete_selected_barrier_from_table

        return delete_selected_barrier_from_table(self)


    def apply_area_preset_to_selected_barrier(self):
        from tabs.barriers_tab_actions import apply_area_preset_to_selected_barrier

        return apply_area_preset_to_selected_barrier(self)


    def _optimizer_row_tag(self, predicted_status: str) -> str:
        status = str(predicted_status or "").upper()
        if status in {"FAIL", "ERROR", "NON-COMPLIANT"}:
            return "opt_fail"
        if status in {"REVIEW", "WARN", "WARNING"}:
            return "opt_review"
        return "opt_pass"


    def render_optimizer_recommendations(self, recommendations: list[Dict[str, Any]]):
        from tabs.barriers_optimizer import render_optimizer_recommendations

        return render_optimizer_recommendations(self, recommendations)
    def _optimise_barriers(self, room_name: Optional[str] = None):
        from tabs.barriers_optimizer import optimise_barriers

        return optimise_barriers(self, room_name=room_name)

    def optimise_selected_room(self):
        from tabs.barriers_optimizer import optimise_selected_room

        return optimise_selected_room(self)

    def optimise_all_rooms(self):
        from tabs.barriers_optimizer import optimise_all_rooms

        return optimise_all_rooms(self)

    def refresh_all(self):
        from services.app_refresh import refresh_all

        return refresh_all(self)

    def generate_outputs(self):
        from tabs.results_tab_actions import generate_outputs

        return generate_outputs(self)


    def prepare_project_for_save(self) -> dict:
        """Prepare editable working-project JSON for saving."""
        return sync_project_state_for_save(self)




def main():
    app = ShieldingDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
