from __future__ import annotations

from geometry.geometry_model import *
from config.geometry_constants import *
from modalities.registry import (
    default_source_type_for_modality,
    geometry_ui_for_modality,
    get_modality_plugin,
    modality_for_source_inventory,
    production_modalities,
    source_label_for_type,
    source_owner_plugin,
    source_type_for_modality_role,
    source_types_with_role,
)
from services.ct_scanner_resolution import friendly_ct_model_name


class SourceSyncMixin:

    def load_scanner_from_room_source(self, room):
        if not room:
            return

        sources = self.app.get_sources_for_room(room.name)
        ct_source = None

        scanner_source_types = set(source_types_with_role("ct_ksec_scatter"))
        for s in sources:
            if s.source_type in scanner_source_types:
                ct_source = s
                break

        if not ct_source:
            return

        params = getattr(ct_source, "params", {}) or {}
        family = str(params.get("scanner_family", "") or "").strip()

        if not family:
            return

        # Geometry combobox values are scanner.short_name values, which do not
        # always equal friendly_ct_model_name().  Load the saved project/source
        # scanner by reverse-mapping scanner_family to the actual combobox display
        # value.  Otherwise update_source_options() can reject the friendly label
        # and silently fall back to options[0] (CT-14E: GE default over Canon source).
        display_value = ""
        try:
            for display, family_id in getattr(self, "_scanner_display_to_family", {}).items():
                if str(family_id or "").strip() == family:
                    display_value = display
                    break
        except Exception:
            display_value = ""

        if display_value:
            self.source_option_var.set(display_value)
        else:
            self.source_option_var.set(
                friendly_ct_model_name(self.app.ct_scanner_resolution_context, family)
            )

        try:
            self._update_scanner_ksec_label()
        except Exception:
            pass

    def initialise_missing_ct_source_from_geometry_selection(self, room) -> None:
        """
        Initialise an incomplete default CT source from the visible Geometry
        scanner dropdown.

        This is deliberately narrow:
        - valid existing CT sources remain authoritative;
        - manual ksec overrides are never overwritten;
        - only an incomplete startup/default CT source is repaired.
        """
        if not room:
            return

        selected_type = str(self.source_type_var.get() or "").strip()
        geometry_ui = geometry_ui_for_modality(selected_type)
        if geometry_ui.selector_kind != "ct_scanner_database":
            return

        try:
            sources = self.app.get_sources_for_room(room.name)
        except Exception:
            sources = []

        ct_source = next(
            (
                s for s in sources
                if str(getattr(s, "source_type", "") or "").strip()
                in set(source_types_with_role("ct_ksec_scatter"))
            ),
            None,
        )

        params = getattr(ct_source, "params", {}) if ct_source is not None else {}
        if not isinstance(params, dict):
            params = {}

        manual_override = str(params.get("manual_ksec_override", "0") or "0").strip() == "1"
        if manual_override:
            return

        family = str(params.get("scanner_family", "") or "").strip()
        model = str(params.get("scanner_model", "") or "").strip()
        ksec = params.get("ksec_mGy_per_100mAs_at_1m")

        has_ksec_or_known_null = (
            ksec not in (None, "", "NULL", "null", "None")
            or str(params.get("scanner_ksec_status", "") or "").strip()
            in {"database", "manual_override_required"}
        )

        # Existing source is already complete enough. Do not let Geometry
        # dropdown defaults overwrite the Sources-tab scanner identity.
        if family and model and has_ksec_or_known_null:
            return

        selected_model = str(self.source_option_var.get() or "").strip()
        if not selected_model:
            return

        # Startup/default source is incomplete. Commit the visible scanner once
        # through the explicit scanner-change path, equivalent to the user
        # selecting the dropdown.
        self.on_geometry_scanner_changed()


    def load_source_from_project(self, room):
        if not hasattr(self, "source_type_var"):
            return

        sources = self.app.get_sources_for_room(room.name)
        types = {s.source_type for s in sources}

        self._loading = True
        try:
            matched = modality_for_source_inventory(types)
            if matched is None:
                production = production_modalities()
                matched = production[0] if production else None
            if matched is not None:
                self.source_type_var.set(matched.modality_id)

                # On room load, the project source inventory is authoritative for
                # patient-source labels.  Geometry may still contain a scanner
                # label from an earlier CT state because startup loading is
                # deliberately protected by ``_loading`` and therefore does not
                # execute the live modality-transition reset in
                # GeometryTab.update_source_options().
                #
                # Keep CT scanner labels under the CT scanner-resolution path, but
                # align PET/SPECT geometry labels with their actual project source
                # so stale CT equipment names cannot appear on initial display.
                geometry_ui = geometry_ui_for_modality(matched.modality_id)
                if geometry_ui.selector_kind != "ct_scanner_database":
                    primary_source_type = default_source_type_for_modality(matched.modality_id)
                    primary_source = next(
                        (
                            source
                            for source in sources
                            if str(getattr(source, "source_type", "") or "").strip()
                            == primary_source_type
                        ),
                        None,
                    )
                    source_label = str(getattr(primary_source, "name", "") or "").strip()
                    if not source_label:
                        source_label = source_label_for_type(primary_source_type)
                    if source_label:
                        self.source_label_var.set(source_label)
                        geometry_source = getattr(getattr(room, "geometry", None), "source", None)
                        if geometry_source is not None:
                            geometry_source.label = source_label

            self.update_source_options()
        finally:
            self._loading = False


    def _refresh_geometry_scanner_display_from_source(self, room) -> None:
        """Refresh Geometry scanner dropdown/ksec label from the canonical source model."""
        try:
            sources = self.app.get_sources_for_room(room.name)
        except Exception:
            sources = []

        ct_source = next(
            (
                s for s in sources
                if str(getattr(s, "source_type", "") or "").strip()
                in set(source_types_with_role("ct_ksec_scatter"))
            ),
            None,
        )

        if ct_source is None:
            return

        params = getattr(ct_source, "params", {}) or {}
        family = str(params.get("scanner_family", "") or "").strip()
        if not family:
            return

        try:
            display_model = friendly_ct_model_name(self.app.ct_scanner_resolution_context, family)
        except Exception:
            display_model = str(params.get("scanner_model", "") or family).strip()

        if not display_model:
            return

        was_loading = getattr(self, "_loading", False)
        self._loading = True
        try:
            self.source_option_var.set(display_model)
        finally:
            self._loading = was_loading

        try:
            self._update_scanner_ksec_label()
        except Exception:
            pass


    def apply_geometry_source_to_project(self, room):
        from models.shielding_models import Source

        if not hasattr(self.app.project, "sources") or self.app.project.sources is None:
            self.app.project.sources = []

        existing_sources = self.app.get_sources_for_room(room.name)

        self.app.project.sources = [
            s for s in self.app.project.sources
            if str(getattr(s, "room_name", "")).strip() != room.name
        ]

        selected_type = self.source_type_var.get().strip()
        selected_model = self.source_option_var.get().strip()
        plugin = get_modality_plugin(selected_type)
        if plugin is None:
            return

        geometry_ui = plugin.geometry_ui()
        selected_source_type = source_type_for_modality_role(
            selected_type,
            geometry_ui.primary_source_role,
        )

        existing_by_type = {
            str(getattr(source, "source_type", "") or ""): source
            for source in existing_sources
        }
        existing_by_role = {}
        for source in existing_sources:
            owner = source_owner_plugin(getattr(source, "source_type", ""))
            source_spec = owner.source_spec_for_type(getattr(source, "source_type", "")) if owner else None
            if source_spec is not None:
                existing_by_role.setdefault(source_spec.role, source)

        for source_spec in plugin.source_specs():
            existing = existing_by_type.get(source_spec.source_type) or existing_by_role.get(source_spec.role)
            existing_params = (
                dict(existing.params)
                if existing is not None and isinstance(getattr(existing, "params", None), dict)
                else {}
            )
            params = plugin.prepare_geometry_source_params(
                source_spec.source_type,
                existing_params,
                {
                    "selected_source_type": selected_source_type,
                    "selected_model": selected_model,
                    "app": self.app,
                },
            )

            self.app.project.sources.append(
                Source(
                    name=getattr(existing, "name", source_spec.label) if existing else source_spec.label,
                    source_type=source_spec.source_type,
                    radiation_type=(
                        getattr(existing, "radiation_type", source_spec.default_radiation_type)
                        if existing else source_spec.default_radiation_type
                    ),
                    params=params,
                    room_name=room.name,
                )
            )

        room.modality = plugin.spec.modality_id

        # Keep room mirror aligned with project-level sources
        room.sources = self.app.get_sources_for_room(room.name)
        self._sync_geometry_source_metadata_from_project_source(room)
        self._refresh_geometry_scanner_display_from_source(room)

        # Force Sources tab to reload from the newly written project.sources
        try:
            self.app.sources_room_var.set(room.name)
            self.app.current_source_index = 0
            self.app.refresh_sources_list(preserve_index=0)
            self.app._reload_source_ui_from_model(room, 0, refresh_live=True)
        except Exception:
            pass

    def prepare_geometry_source_view_for_room(self, room):
        """Return the selected plugin's complete Geometry source view."""
        plugin = get_modality_plugin(getattr(room, "modality", "") if room else "")
        if plugin is None:
            from modalities.base import GeometrySourceView
            return GeometrySourceView()

        try:
            sources = self.app.get_sources_for_room(room.name)
        except Exception:
            sources = []

        source_payloads = tuple(
            {
                "name": str(getattr(source, "name", "") or ""),
                "source_type": str(getattr(source, "source_type", "") or ""),
                "params": dict(getattr(source, "params", {}) or {}),
            }
            for source in sources
        )

        live_source_params = plugin.geometry_live_source_params(room)

        return plugin.prepare_geometry_source_view(
            source_payloads,
            {"app": self.app, "live_source_params": live_source_params},
        )

    def sync_geometry_source_metadata_from_project_source(self, room) -> None:
        """Apply the plugin-prepared source view to transient Geometry state."""
        if not room:
            return
        geometry = getattr(room, "geometry", None)
        geometry_source = getattr(geometry, "source", None)
        if geometry_source is None:
            return

        view = self.prepare_geometry_source_view_for_room(room)
        geometry_source.render_metadata.clear()
        geometry_source.render_metadata.update(dict(view.render_metadata or {}))
        if view.label:
            geometry_source.label = str(view.label)
