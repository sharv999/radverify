"""Lightweight modality interface contracts.

The application core should depend on these modality descriptors rather than
hard-coded modality names, source inventories, or production/coming-soon lists.

This module deliberately contains metadata only.  CT physics remains in the
existing CT engine; future modality plugins can add calculation adapters behind
this stable registry without disturbing the working CT path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Tuple, runtime_checkable


SourceSummaryFormatter = Callable[[Mapping[str, Any]], tuple[str, ...]]
SourceReportContentBuilder = Callable[[Mapping[str, Any]], dict[str, Any]]
SourceReadinessValidator = Callable[[str, Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
GeometrySourceParamsBuilder = Callable[["SourceSpec", Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
GeometrySourceViewBuilder = Callable[[tuple[Mapping[str, Any], ...], Mapping[str, Any]], "GeometrySourceView"]
GeometryLiveSourceParamsBuilder = Callable[[Any], Mapping[str, Any]]


MODALITY_PLUGIN_API_VERSION = 1


@runtime_checkable
class ModalityPlugin(Protocol):
    """Behavioural contract implemented by every registered modality plugin.

    The registry and application core may inspect ``spec`` for immutable
    modality metadata, but all source-level behaviour is reached through these
    methods.  Future code-backed plugins can therefore implement the same
    contract without requiring the core to know their module, modality name, or
    internal representation.
    """

    api_version: int
    spec: "ModalitySpec"

    def initialise_app_services(self, app: Any, base_path: Any) -> None: ...

    def source_form_vendor_values(self, app: Any, source_type: str | None) -> tuple[str, ...]: ...

    def source_form_model_values(self, app: Any, source_type: str | None) -> tuple[str, ...]: ...

    def source_form_schema(self, app: Any, source_type: str | None) -> "SourceFormSchema | None": ...

    def source_form_tvl_params(self, app: Any, source_type: str | None) -> dict[str, Any] | None: ...

    def handle_source_form_event(
        self, app: Any, event_kind: str, source_type: str | None, *, force: bool = False
    ) -> Any: ...

    def collect_source_form_params(self, app: Any, source_type: str | None) -> dict[str, Any] | None: ...

    def load_source_form_params(
        self, app: Any, source_type: str | None, params: Mapping[str, Any]
    ) -> bool: ...

    def sanitize_source_params(
        self, source_type: str | None, params: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def finalise_source_form_params(
        self, app: Any, source_type: str | None, params: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def live_preview_lines(
        self,
        app: Any,
        source_type: str | None,
        source_name: str,
        radiation_type: str,
    ) -> tuple[str, ...] | None: ...

    def source_specs(self) -> tuple["SourceSpec", ...]: ...

    def source_spec_for_type(self, source_type: str | None) -> "SourceSpec | None": ...

    def default_source_params(self, source_type: str | None) -> dict[str, Any]: ...

    def report_wording(self) -> "ReportWordingSpec": ...

    def report_content_for_source(
        self, source_payload: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def geometry_ui(self) -> "GeometryUISpec": ...

    def layout_rendering(self) -> "LayoutRenderSpec": ...

    def prepare_geometry_source_params(
        self,
        source_type: str | None,
        existing_params: Mapping[str, Any] | None,
        context: Mapping[str, Any],
    ) -> dict[str, Any]: ...

    def prepare_geometry_source_view(
        self,
        source_payloads: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any],
    ) -> "GeometrySourceView": ...

    def geometry_live_source_params(self, room: Any) -> dict[str, Any]: ...

    def readiness_result(
        self,
        source_type: str | None,
        params: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any] | None: ...

    def source_types_with_role(self, role: str) -> list[str]: ...

    def source_types_with_dose_model(self, dose_model: str) -> list[str]: ...

    def source_types_with_contribution_group(self, group: str) -> list[str]: ...

    def source_types_with_ncrp_solver_mode(self, solver_mode: str) -> list[str]: ...


@dataclass(frozen=True)
class DeclarativeModalityPlugin:
    """Standard implementation for immutable, metadata-driven modalities."""

    spec: "ModalitySpec"
    api_version: int = MODALITY_PLUGIN_API_VERSION

    def initialise_app_services(self, app: Any, base_path: Any) -> None:
        return None

    def source_form_vendor_values(self, app: Any, source_type: str | None) -> tuple[str, ...]:
        return tuple()

    def source_form_model_values(self, app: Any, source_type: str | None) -> tuple[str, ...]:
        return tuple()

    def source_form_schema(self, app: Any, source_type: str | None) -> "SourceFormSchema | None":
        return None

    def source_form_tvl_params(self, app: Any, source_type: str | None) -> dict[str, Any] | None:
        return None

    def handle_source_form_event(
        self, app: Any, event_kind: str, source_type: str | None, *, force: bool = False
    ) -> Any:
        return None

    def collect_source_form_params(self, app: Any, source_type: str | None) -> dict[str, Any] | None:
        return None

    def load_source_form_params(
        self, app: Any, source_type: str | None, params: Mapping[str, Any]
    ) -> bool:
        return False

    def sanitize_source_params(
        self, source_type: str | None, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        return dict(params or {})

    def finalise_source_form_params(
        self, app: Any, source_type: str | None, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.sanitize_source_params(source_type, params)

    def live_preview_lines(
        self,
        app: Any,
        source_type: str | None,
        source_name: str,
        radiation_type: str,
    ) -> tuple[str, ...] | None:
        return None

    def source_specs(self) -> tuple["SourceSpec", ...]:
        return self.spec.expected_sources

    def source_spec_for_type(self, source_type: str | None) -> "SourceSpec | None":
        return self.spec.source_spec_for_type(source_type)

    def default_source_params(self, source_type: str | None) -> dict[str, Any]:
        return self.spec.default_params_for_source_type(source_type)

    def report_wording(self) -> "ReportWordingSpec":
        return self.spec.report_wording

    def report_content_for_source(
        self, source_payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.spec.report_content_for_source(source_payload)

    def geometry_ui(self) -> "GeometryUISpec":
        return self.spec.geometry_ui

    def layout_rendering(self) -> "LayoutRenderSpec":
        return self.spec.layout_rendering

    def prepare_geometry_source_params(
        self,
        source_type: str | None,
        existing_params: Mapping[str, Any] | None,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.spec.prepare_geometry_source_params(source_type, existing_params, context)

    def prepare_geometry_source_view(
        self,
        source_payloads: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any],
    ) -> "GeometrySourceView":
        return self.spec.prepare_geometry_source_view(source_payloads, context)

    def geometry_live_source_params(self, room: Any) -> dict[str, Any]:
        return self.spec.geometry_live_source_params(room)

    def readiness_result(
        self,
        source_type: str | None,
        params: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        return self.spec.readiness_result_for_source(source_type, params, context)

    def source_types_with_role(self, role: str) -> list[str]:
        return self.spec.source_types_with_role(role)

    def source_types_with_dose_model(self, dose_model: str) -> list[str]:
        return self.spec.source_types_with_dose_model(dose_model)

    def source_types_with_contribution_group(self, group: str) -> list[str]:
        return self.spec.source_types_with_contribution_group(group)

    def source_types_with_ncrp_solver_mode(self, solver_mode: str) -> list[str]:
        return self.spec.source_types_with_ncrp_solver_mode(solver_mode)


class ModalityContractError(ValueError):
    """Raised when a modality plugin cannot safely enter the registry."""


def validate_modality_plugin(plugin: ModalityPlugin) -> None:
    """Enforce the registry boundary before application startup.

    This deliberately validates structure and dispatch metadata only; it does
    not run or alter any shielding equation.
    """

    if not isinstance(plugin, ModalityPlugin):
        raise ModalityContractError("Registered modality must implement ModalityPlugin.")
    if plugin.api_version != MODALITY_PLUGIN_API_VERSION:
        raise ModalityContractError(
            f"Unsupported modality plugin API version {plugin.api_version!r}; "
            f"expected {MODALITY_PLUGIN_API_VERSION}."
        )

    spec = plugin.spec
    if not isinstance(spec, ModalitySpec):
        raise ModalityContractError("Modality plugin spec must be a ModalitySpec.")
    if not spec.modality_id.strip():
        raise ModalityContractError("Modality id must not be blank.")
    if not spec.display_name.strip():
        raise ModalityContractError(f"{spec.modality_id}: display name must not be blank.")
    if not spec.default_room_name.strip():
        raise ModalityContractError(f"{spec.modality_id}: default room name must not be blank.")
    if spec.production_enabled and not spec.expected_sources:
        raise ModalityContractError(f"{spec.modality_id}: production modality requires a source.")

    declared_sources = plugin.source_specs()
    if not isinstance(declared_sources, tuple):
        raise ModalityContractError(
            f"{spec.modality_id}: source_specs() must return a tuple of SourceSpec values."
        )
    if declared_sources != spec.expected_sources:
        raise ModalityContractError(
            f"{spec.modality_id}: source_specs() must match spec.expected_sources."
        )
    if plugin.report_wording() is not spec.report_wording:
        raise ModalityContractError(
            f"{spec.modality_id}: report_wording() must return spec.report_wording."
        )
    if plugin.geometry_ui() is not spec.geometry_ui:
        raise ModalityContractError(
            f"{spec.modality_id}: geometry_ui() must return spec.geometry_ui."
        )
    if plugin.layout_rendering() is not spec.layout_rendering:
        raise ModalityContractError(
            f"{spec.modality_id}: layout_rendering() must return spec.layout_rendering."
        )
    view = plugin.prepare_geometry_source_view(tuple(), {})
    if not isinstance(view, GeometrySourceView):
        raise ModalityContractError(
            f"{spec.modality_id}: prepare_geometry_source_view() must return GeometrySourceView."
        )

    seen: set[str] = set()
    for source in declared_sources:
        source_type = source.source_type.strip()
        if not source_type:
            raise ModalityContractError(f"{spec.modality_id}: source type must not be blank.")
        if source_type in seen:
            raise ModalityContractError(
                f"{spec.modality_id}: duplicate source type {source_type!r}."
            )
        seen.add(source_type)
        if not source.label.strip():
            raise ModalityContractError(
                f"{spec.modality_id}/{source_type}: source label must not be blank."
            )
        if not source.dose_model.strip():
            raise ModalityContractError(
                f"{spec.modality_id}/{source_type}: dose model must not be blank."
            )
        if plugin.source_spec_for_type(source_type) is not source:
            raise ModalityContractError(
                f"{spec.modality_id}/{source_type}: source lookup must return the declared SourceSpec."
            )
        if plugin.default_source_params(source_type) != dict(source.default_params or {}):
            raise ModalityContractError(
                f"{spec.modality_id}/{source_type}: default source parameters are inconsistent."
            )
        if source.dose_model == "not_implemented" and not source.calculation_blocked_reason.strip():
            raise ModalityContractError(
                f"{spec.modality_id}/{source_type}: blocked source requires a reason."
            )


@dataclass(frozen=True)
class ReportWordingSpec:
    """Report wording owned by the modality descriptor.

    PDF/report builders should consume this metadata rather than hard-coding
    modality-specific titles, quotation wording, or limitation text.
    """

    report_title: str = "Preliminary Shielding Schedule"
    report_subtitle: str = "Preliminary shielding assessment schedule"
    cover_introduction: str = (
        "This output is intended as an internal calculation schedule to support early project pricing and design review. "
        "It is not a certified radiation shielding assessment report."
    )
    limitations_heading: str = "Preliminary assessment limitations"
    limitation_bullets: Tuple[str, ...] = (
        "This document is a preliminary shielding schedule for internal quotation and early design review only.",
        "It is not a certified radiation shielding assessment report and should not be issued as final regulatory documentation.",
        "Final shielding assessment requires review of architectural drawings, construction details, source/workload assumptions, occupancy assumptions and installed materials.",
        "Calculated results depend on the entered room geometry, source data, workload, design goal and occupancy factors.",
    )
    room_schedule_prefix: str = "Room schedule"
    room_layout_heading: str = "Room layout"
    barrier_schedule_heading: str = "Barrier schedule"
    source_inputs_heading: str = "Source inputs"
    methodology_paragraphs: Tuple[str, ...] = field(default_factory=tuple)
    methodology_rows: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    assumption_bullets: Tuple[str, ...] = field(default_factory=tuple)
    construction_shielding_height_mm: int = 2100


@dataclass(frozen=True)
class GeometrySourceView:
    """Complete plugin-prepared source state consumed by Geometry renderers."""

    source_type: str = ""
    label: str = "Source"
    render_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeometryUISpec:
    """Modality-owned Geometry-tab behaviour.

    Core UI/orchestration consumes this descriptor instead of branching on
    modality identifiers.
    """

    selector_kind: str = "none"
    scanner_metadata_group: str = ""
    static_options: Tuple[str, ...] = field(default_factory=tuple)
    symbol_kind: str = "point_source"
    primary_source_role: str = ""
    source_label: str = ""
    source_info_label: str = ""
    source_info_param_key: str = ""
    source_info_unit: str = ""



@dataclass(frozen=True)
class LayoutRenderSpec:
    """Plugin-owned source rendering instructions for Tk and PDF layouts.

    Renderers consume this neutral descriptor and do not infer modality from
    source labels or import modality-specific physical dimensions.
    """

    source_symbol_kind: str = "point_source"
    show_radiation_symbol: bool = True
    radiation_symbol_offset_m: float = 0.0
    show_patient_symbol: bool = False
    patient_symbol_offset_m: float = 0.5
    patient_label_offset_px: float = 20.0
    patient_marker_label: str = "NM"
    show_one_m_circle: bool = True
    reference_circle_anchor: str = "source"
    reference_circle_radius_m: float = 1.0
    reference_circle_label_gap_px: float = 10.0
    preview_source_label_gap_px: float = 6.0
    preview_overlay_kind: str = ""
    show_barrier_status_text: bool = True
    annotation_kind: str = ""
    equipment_width_m: float = 0.0
    equipment_depth_m: float = 0.0
    table_width_m: float = 0.0
    table_length_m: float = 0.0
    projection_length_m: float = 0.5
    label_cleanup_phrases: Tuple[str, ...] = field(default_factory=tuple)
    label_wrap_separator: str = " / "
    source_label_param: str = ""
    render_param_keys: Tuple[str, ...] = field(default_factory=tuple)
    render_param_defaults: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_symbol_kind": self.source_symbol_kind,
            "show_radiation_symbol": self.show_radiation_symbol,
            "radiation_symbol_offset_m": self.radiation_symbol_offset_m,
            "show_patient_symbol": self.show_patient_symbol,
            "patient_symbol_offset_m": self.patient_symbol_offset_m,
            "patient_label_offset_px": self.patient_label_offset_px,
            "patient_marker_label": self.patient_marker_label,
            "show_one_m_circle": self.show_one_m_circle,
            "reference_circle_anchor": self.reference_circle_anchor,
            "reference_circle_radius_m": self.reference_circle_radius_m,
            "reference_circle_label_gap_px": self.reference_circle_label_gap_px,
            "preview_source_label_gap_px": self.preview_source_label_gap_px,
            "preview_overlay_kind": self.preview_overlay_kind,
            "show_barrier_status_text": self.show_barrier_status_text,
            "annotation_kind": self.annotation_kind,
            "equipment_width_m": self.equipment_width_m,
            "equipment_depth_m": self.equipment_depth_m,
            "table_width_m": self.table_width_m,
            "table_length_m": self.table_length_m,
            "projection_length_m": self.projection_length_m,
            "label_cleanup_phrases": list(self.label_cleanup_phrases),
            "label_wrap_separator": self.label_wrap_separator,
            "source_label_param": self.source_label_param,
            "render_param_keys": list(self.render_param_keys),
            "render_param_defaults": dict(self.render_param_defaults),
        }


@dataclass(frozen=True)
class SourceFormFieldSpec:
    """One plugin-prepared row in the generic source-form renderer."""

    key: str
    label: str
    row: int
    variable_group: str
    widget_kind: str = "entry"
    values: Tuple[str, ...] = field(default_factory=tuple)
    state: str = "normal"
    widget_attr: str = ""
    event_sequence: str = ""
    event_kind: str = ""


@dataclass(frozen=True)
class SourceFormTextSpec:
    """Static text row prepared by a plugin for the generic form renderer."""

    text: str
    row: int
    column: int = 0
    columnspan: int = 2
    sticky: str = "w"


@dataclass(frozen=True)
class SourceFormSchema:
    """Complete modality-owned source form consumed by the Tk host renderer."""

    source_type: str
    fields: Tuple[SourceFormFieldSpec, ...] = field(default_factory=tuple)
    text_rows: Tuple[SourceFormTextSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SourceSpec:
    """One source required by a modality room.

    ``role`` is intentionally generic metadata.  Services can ask the
    registry for sources with a role such as ``ct_ksec_scatter`` instead of
    hard-coding modality-specific source-type strings throughout the app.
    ``default_params`` is used by source creation/repair paths; physics
    calculations remain in the existing engine.
    """

    source_type: str
    label: str
    role: str = "generic"
    default_radiation_type: str = ""
    default_params: Mapping[str, Any] = field(default_factory=dict)
    form_kind: str = "generic"
    ui_labels: Mapping[str, str] = field(default_factory=dict)
    readiness_labels: Mapping[str, str] = field(default_factory=dict)
    report_summary_columns: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    report_summary_formatter: SourceSummaryFormatter | None = None
    report_content_builder: SourceReportContentBuilder | None = None
    dose_model: str = "generic"
    default_tvl_key: str = ""
    contribution_group: str = "other"
    ncrp_solver_mode: str = ""
    validation_kind: str = "generic"
    readiness_validator: SourceReadinessValidator | None = None
    blocking_reason_by_basis: Mapping[str, str] = field(default_factory=dict)
    calculation_blocked_reason: str = ""


@dataclass(frozen=True)
class ModalitySpec:
    """Descriptor for one shielding modality.

    ``production_enabled`` is the switch the UI uses to decide whether a room
    can be created/edited in the current build.  Non-production specs may remain
    registered as forward-looking placeholders, but they must not be selectable
    as active production modalities.
    """

    modality_id: str
    display_name: str
    production_enabled: bool
    default_room_name: str
    expected_sources: Tuple[SourceSpec, ...] = field(default_factory=tuple)
    geometry_ui: GeometryUISpec = field(default_factory=GeometryUISpec)
    layout_rendering: LayoutRenderSpec = field(default_factory=LayoutRenderSpec)

    classification: str = "generic"
    default_energy_label: str = "140 kVp"
    default_solver_mode: str = "auto"

    controlled_area_required: bool = False
    patient_radioactivity_present: bool = False
    xray_generator_present: bool = False
    hybrid_ct_present: bool = False
    compliance_only: bool = False

    default_internal_design_goal_uSv_per_week: float = 50.0
    default_external_design_goal_uSv_per_week: float = 10.0
    default_internal_occupancy_factor: float = 1.0
    default_external_occupancy_factor: float = 0.2

    notes: str = ""
    report_wording: ReportWordingSpec = field(default_factory=ReportWordingSpec)
    geometry_source_params_builder: GeometrySourceParamsBuilder | None = None
    geometry_source_view_builder: GeometrySourceViewBuilder | None = None
    geometry_live_source_params_builder: GeometryLiveSourceParamsBuilder | None = None

    def prepare_geometry_source_params(
        self,
        source_type: str | None,
        existing_params: Mapping[str, Any] | None,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        source_spec = self.source_spec_for_type(source_type)
        if source_spec is None:
            return {}
        if self.geometry_source_params_builder is not None:
            return dict(self.geometry_source_params_builder(source_spec, existing_params or {}, context))

        if existing_params:
            params = dict(existing_params)
        else:
            selected_type = str(context.get("selected_source_type", "") or "")
            selected_params = context.get("selected_source_params", {}) or {}
            params = dict(selected_params) if selected_type == source_spec.source_type else {}
        defaults = dict(source_spec.default_params or {})
        defaults.update(params)
        return defaults

    def geometry_live_source_params(self, room: Any) -> dict[str, Any]:
        if self.geometry_live_source_params_builder is None:
            return {}
        try:
            return dict(self.geometry_live_source_params_builder(room) or {})
        except Exception:
            return {}

    def prepare_geometry_source_view(
        self,
        source_payloads: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any],
    ) -> GeometrySourceView:
        if self.geometry_source_view_builder is not None:
            return self.geometry_source_view_builder(source_payloads, context)

        primary_role = self.geometry_ui.primary_source_role
        primary_spec = next(
            (source for source in self.expected_sources if source.role == primary_role),
            self.expected_sources[0] if self.expected_sources else None,
        )
        if primary_spec is None:
            return GeometrySourceView(label=self.geometry_ui.source_label or "Source")

        payload = next(
            (item for item in source_payloads if str(item.get("source_type", "") or "") == primary_spec.source_type),
            {},
        )
        params = dict(payload.get("params", {}) or {})
        live_params = dict(context.get("live_source_params", {}) or {})
        for key, value in live_params.items():
            if params.get(key) in (None, "") and value not in (None, ""):
                params[key] = value

        rendering = self.layout_rendering
        metadata = dict(rendering.render_param_defaults or {})
        for key in rendering.render_param_keys:
            value = params.get(key)
            if value not in (None, ""):
                metadata[key] = value

        label = str(payload.get("name", "") or primary_spec.label or self.geometry_ui.source_label or "Source")
        if rendering.source_label_param:
            label_value = params.get(rendering.source_label_param)
            if label_value not in (None, ""):
                label = str(label_value)

        return GeometrySourceView(
            source_type=primary_spec.source_type,
            label=label,
            render_metadata=metadata,
        )

    @property
    def source_mapping(self) -> list[tuple[str, str]]:
        """Return legacy-compatible ``[(source_type, label), ...]`` mapping."""

        return [(source.source_type, source.label) for source in self.expected_sources]

    @property
    def expected_source_types(self) -> list[str]:
        return [source.source_type for source in self.expected_sources]

    @property
    def default_source_type(self) -> str:
        return self.expected_sources[0].source_type if self.expected_sources else ""

    def source_spec_for_type(self, source_type: str | None) -> SourceSpec | None:
        text = str(source_type or "").strip()
        for source in self.expected_sources:
            if source.source_type == text:
                return source
        return None

    def source_label_for_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        if spec is not None:
            return spec.label
        text = str(source_type or "").strip()
        return text or "Source"

    def default_params_for_source_type(self, source_type: str | None) -> dict[str, Any]:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return {}
        return dict(spec.default_params or {})

    def form_kind_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.form_kind if spec is not None else "generic"

    def ui_labels_for_source_type(self, source_type: str | None) -> dict[str, str]:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return {}
        return dict(spec.ui_labels or {})

    def readiness_labels_for_source_type(self, source_type: str | None) -> dict[str, str]:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return {}
        return dict(spec.readiness_labels or {})

    def report_summary_columns_for_source_type(self, source_type: str | None) -> list[tuple[str, str]]:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return []
        return [tuple(item) for item in (spec.report_summary_columns or ())]

    def dose_model_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.dose_model if spec is not None else "generic"

    def default_tvl_key_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.default_tvl_key if spec is not None else ""

    def contribution_group_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.contribution_group if spec is not None else "other"

    def ncrp_solver_mode_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.ncrp_solver_mode if spec is not None else ""

    def validation_kind_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        return spec.validation_kind if spec is not None else "generic"

    def blocking_reason_for_source_basis(self, source_type: str | None, basis: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return ""
        return str((spec.blocking_reason_by_basis or {}).get(str(basis or ""), "") or "")

    def calculation_blocked_reason_for_source_type(self, source_type: str | None) -> str:
        spec = self.source_spec_for_type(source_type)
        if spec is None:
            return ""
        return str(spec.calculation_blocked_reason or "")

    def readiness_result_for_source(
        self,
        source_type: str | None,
        params: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        spec = self.source_spec_for_type(source_type)
        if spec is None or spec.readiness_validator is None:
            return None
        return dict(spec.readiness_validator(str(source_type or ""), params, context))

    def report_summary_row_for_source(self, source_payload: Mapping[str, Any]) -> list[str]:
        source_type = str(source_payload.get("source_type", "") or "")
        spec = self.source_spec_for_type(source_type)
        if spec is not None and spec.report_summary_formatter is not None:
            return list(spec.report_summary_formatter(source_payload))
        columns = self.report_summary_columns_for_source_type(source_type)
        return [str(source_payload.get(key, "") or "") for key, _heading in columns]

    def report_content_for_source(self, source_payload: Mapping[str, Any]) -> dict[str, Any]:
        source_type = str(source_payload.get("source_type", "") or "")
        spec = self.source_spec_for_type(source_type)
        if spec is None or spec.report_content_builder is None:
            return {}
        return dict(spec.report_content_builder(source_payload) or {})

    def source_types_with_role(self, role: str) -> list[str]:
        return [source.source_type for source in self.expected_sources if source.role == role]

    def source_types_with_dose_model(self, dose_model: str) -> list[str]:
        return [source.source_type for source in self.expected_sources if source.dose_model == dose_model]

    def source_types_with_contribution_group(self, group: str) -> list[str]:
        return [source.source_type for source in self.expected_sources if source.contribution_group == group]

    def source_types_with_ncrp_solver_mode(self, solver_mode: str) -> list[str]:
        return [source.source_type for source in self.expected_sources if source.ncrp_solver_mode == solver_mode]
