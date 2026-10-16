from __future__ import annotations
from typing import Any, Dict
from models.shielding_models import Source
from engine.normalization import normalize_source_params
from modalities.registry import (
    default_source_params_for_type,
    default_source_type_for_modality,
    source_label_for_type,
    collect_plugin_source_form_params,
    load_plugin_source_form_params,
)
from services.project_serializer import project_to_working_dict


def sync_project_state_for_save(app) -> dict:
    """Return a clean editable project payload for Save/Save As.

    This keeps the save-state orchestration outside app.py while preserving the
    existing order of UI/model sync operations.
    """
    app.apply_project_form()

    try:
        if hasattr(app, "geometry_tab"):
            app.geometry_tab.update_model_from_fields(show_errors=False)
    except Exception:
        pass

    try:
        app.sync_current_source_to_model(ignore_errors=True)
    except Exception:
        pass

    # PET durable working state supports the controlled production-host scope;
    # the dedicated replay-verified dispatcher remains separate from project.sources.
    try:
        from tabs.pet_preview_panel import persist_pet_preview_to_room
        persist_pet_preview_to_room(app)
    except Exception:
        pass

    # Step 23: SPECT now has durable working-project source/workload inputs under
    # Room.modality_state. This remains explicitly non-production; preview-only
    # what-if geometry continues to live outside normal project save.
    try:
        from tabs.spect_preview_panel import persist_spect_preview_source_to_room
        persist_spect_preview_source_to_room(app)
    except Exception:
        pass

    for room in getattr(app.project, "rooms", []) or []:
        try:
            app.enforce_room_source_types(room)
        except Exception:
            pass

        try:
            app._apply_geometry_to_selected_room_barriers(room)
        except Exception:
            pass

        for barrier in getattr(room, "barriers", []) or []:
            try:
                app._coerce_barrier_schema(barrier)
            except Exception:
                pass

    return project_to_working_dict(app.project)

class SourceFormSyncMixin:

    def collect_source_params_from_form(self, source_type: str) -> Dict[str, Any]:
        plugin_params = collect_plugin_source_form_params(self, source_type)
        if plugin_params is not None:
            return normalize_source_params(source_type, plugin_params)

        fallback_type = default_source_type_for_modality("CT") or "ct_scatter"
        return self._default_source_for_type(
            fallback_type,
            source_label_for_type(fallback_type),
        ).params.copy()


    def load_source_params_into_form(self, src: Source):
        p = normalize_source_params(src.source_type, src.params or {})

        if load_plugin_source_form_params(self, src.source_type, p):
            self.radiation_type_var.set(
                self._safe_auto_select_tvl_key(src.source_type, p, src.radiation_type)
            )

        params = getattr(src, "params", {}) or {}
        manual_override = str(params.get("manual_ksec_override", "0") or "0").strip() == "1"
        if not manual_override:
            self.refresh_selected_source_resolution(force=True, source_type=src.source_type)
