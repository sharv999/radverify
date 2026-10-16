"""Central modality registry.

CT, PET, and SPECT are production-host modalities. X-ray and legacy SPECT/CT
remain registered as non-production placeholders. SPECT issued PDF/export and
certification remain separately gated even though its room/calculation/Results
host paths are enabled.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modalities.base import (
    DeclarativeModalityPlugin,
    GeometryUISpec,
    LayoutRenderSpec,
    ModalityContractError,
    ModalityPlugin,
    ModalitySpec,
    ReportWordingSpec,
    SourceFormFieldSpec,
    SourceFormSchema,
    SourceSpec,
    validate_modality_plugin,
)
from modalities.ct import CT_PLUGIN
from modalities.spect import SPECT_PLUGIN
from modalities.pet import PET_PLUGIN
from modalities.xray import XRAY_PLUGIN


NM_PATIENT_DEFAULT_PARAMS = {
    "radionuclide": "Tc99m",
    "NMPS_R": 20,
    "NMPS_S": 20,
    "NBONE": 40,
    "AMPS_R": 350,
    "AMPS_S": 1000,
    "ABONE": 1000,
    "tMPS_R": 0.33,
    "tMPS_S": 0.33,
    "tBONE": 1.0,
    "RMPS": 0.0206,
    "RBONE": 0.0125,
}


class _SpectCTPlaceholderPlugin(DeclarativeModalityPlugin):
    """Legacy hybrid placeholder with plugin-owned NM form metadata."""

    def source_form_schema(self, app, source_type):
        if str(source_type or "").strip() != "nm_patient":
            return None
        return SourceFormSchema(
            source_type="nm_patient",
            fields=(
                SourceFormFieldSpec(
                    key="radionuclide", label="Radionuclide", row=0,
                    variable_group="nm_vars", widget_kind="combobox",
                    values=("Tc99m", "I131"), state="readonly",
                ),
                SourceFormFieldSpec(key="NMPS_R", label="No. MPS-R", row=1, variable_group="nm_vars", widget_kind="integer_entry"),
                SourceFormFieldSpec(key="NMPS_S", label="No. MPS-S", row=2, variable_group="nm_vars", widget_kind="integer_entry"),
                SourceFormFieldSpec(key="NBONE", label="No. Bone", row=3, variable_group="nm_vars", widget_kind="integer_entry"),
                SourceFormFieldSpec(key="AMPS_R", label="Activity MPS-R (MBq)", row=4, variable_group="nm_vars"),
                SourceFormFieldSpec(key="AMPS_S", label="Activity MPS-S (MBq)", row=5, variable_group="nm_vars"),
                SourceFormFieldSpec(key="ABONE", label="Activity Bone (MBq)", row=6, variable_group="nm_vars"),
                SourceFormFieldSpec(key="tMPS_R", label="Time MPS-R (h)", row=7, variable_group="nm_vars"),
                SourceFormFieldSpec(key="tMPS_S", label="Time MPS-S (h)", row=8, variable_group="nm_vars"),
                SourceFormFieldSpec(key="tBONE", label="Time Bone (h)", row=9, variable_group="nm_vars"),
                SourceFormFieldSpec(key="RMPS", label="R factor MPS", row=10, variable_group="nm_vars"),
                SourceFormFieldSpec(key="RBONE", label="R factor Bone", row=11, variable_group="nm_vars"),
            ),
        )

    def source_form_tvl_params(self, app, source_type):
        if str(source_type or "").strip() != "nm_patient":
            return None
        try:
            radionuclide = str(app.nm_vars["radionuclide"].get()).strip()
        except Exception:
            radionuclide = "Tc99m"
        return {"radionuclide": radionuclide or "Tc99m"}

    def collect_source_form_params(self, app, source_type):
        if str(source_type or "").strip() != "nm_patient":
            return None
        params = {
            "radionuclide": str(app.nm_vars["radionuclide"].get()).strip() or "Tc99m",
            "NMPS_R": app._safe_int(app.nm_vars["NMPS_R"].get(), 20),
            "NMPS_S": app._safe_int(app.nm_vars["NMPS_S"].get(), 20),
            "NBONE": app._safe_int(app.nm_vars["NBONE"].get(), 40),
            "AMPS_R": app._safe_float(app.nm_vars["AMPS_R"].get(), 350.0),
            "AMPS_S": app._safe_float(app.nm_vars["AMPS_S"].get(), 1000.0),
            "ABONE": app._safe_float(app.nm_vars["ABONE"].get(), 1000.0),
            "tMPS_R": app._safe_float(app.nm_vars["tMPS_R"].get(), 0.33),
            "tMPS_S": app._safe_float(app.nm_vars["tMPS_S"].get(), 0.33),
            "tBONE": app._safe_float(app.nm_vars["tBONE"].get(), 1.0),
            "RMPS": app._safe_float(app.nm_vars["RMPS"].get(), 0.0206),
            "RBONE": app._safe_float(app.nm_vars["RBONE"].get(), 0.0125),
        }
        return self.sanitize_source_params(source_type, params)

    def load_source_form_params(self, app, source_type, params) -> bool:
        if str(source_type or "").strip() != "nm_patient":
            return False
        p = self.sanitize_source_params(source_type, params)
        defaults = {
            "radionuclide": "Tc99m", "NMPS_R": 20, "NMPS_S": 20, "NBONE": 40,
            "AMPS_R": 350, "AMPS_S": 1000, "ABONE": 1000,
            "tMPS_R": 0.33, "tMPS_S": 0.33, "tBONE": 1.0,
            "RMPS": 0.0206, "RBONE": 0.0125,
        }
        for key, default in defaults.items():
            app.nm_vars[key].set(str(p.get(key, default)))
        return True

    def sanitize_source_params(self, source_type, params):
        clean = dict(params or {})
        radionuclide = str(clean.get("radionuclide", "Tc99m")).strip() or "Tc99m"
        supported = {"Tc99m", "I131"}
        if radionuclide not in supported:
            clean["radionuclide"] = "Tc99m"
            clean["_invalid_radionuclide"] = radionuclide
        return clean

    def finalise_source_form_params(self, app, source_type, params):
        return self.sanitize_source_params(source_type, params)

    def live_preview_lines(self, app, source_type, source_name, radiation_type):
        if str(source_type or "").strip() != "nm_patient":
            return None
        from models.shielding_models import Source
        from engine.shielding_engine import compute_nm_source_summary
        params = self.collect_source_form_params(app, source_type) or {}
        summary = compute_nm_source_summary(
            Source(name=source_name, source_type="nm_patient", radiation_type=radiation_type, params=params)
        )
        return (
            "Inputs", "------",
            f"Radionuclide: {params.get('radionuclide', 'Tc99m')}",
            f"NMPS-R: {summary['NMPS_R']} patients/wk",
            f"NMPS-S: {summary['NMPS_S']} patients/wk",
            f"NBONE: {summary['NBONE']} patients/wk",
            f"AMPS-R: {summary['AMPS_R']} MBq Tc-99m/pt",
            f"AMPS-S: {summary['AMPS_S']} MBq Tc-99m/pt",
            f"ABONE: {summary['ABONE']} MBq Tc-99m/pt",
            f"tMPS-R: {summary['tMPS_R']:.2f} h",
            f"tMPS-S: {summary['tMPS_S']:.2f} h",
            f"tBONE: {summary['tBONE']:.2f} h",
            f"RMPS: {summary['RMPS']:.4f} uSv/h/MBq @ 1 m",
            f"RBONE: {summary['RBONE']:.4f} uSv/h/MBq @ 1 m",
            "", "Calculated", "----------",
            f"Weekly scintigraphic dose: {summary['dscint_mSv_per_week_at_1m']:.3f} mSv/week @ 1 m",
        )


_SPECT_CT_PLACEHOLDER_PLUGIN = _SpectCTPlaceholderPlugin(
    ModalitySpec(
        modality_id="SPECT/CT",
        display_name="SPECT/CT",
        production_enabled=False,
        default_room_name="SPECT/CT Room 1",
        expected_sources=(
            SourceSpec(
                "spect_ct_secondary_scatter",
                "Secondary scatter source hybrid",
                role="ct_ksec_scatter",
                default_radiation_type="xray_140kvp",
                dose_model="ct_ksec_weekly_dose",
                default_tvl_key="xray_140kvp",
                contribution_group="ct_scatter",
                ncrp_solver_mode="ncrp_ct_secondary",
            ),
            SourceSpec(
                "nm_patient", "NM Patient", role="nm_patient",
                default_radiation_type="tc99m_140kev",
                default_params=NM_PATIENT_DEFAULT_PARAMS,
            ),
        ),
        geometry_ui=GeometryUISpec(
            selector_kind="ct_scanner_database",
            scanner_metadata_group="hybrid_ct_component_attenuation_correction",
            symbol_kind="ct_scanner",
            primary_source_role="ct_ksec_scatter",
            source_label="CT",
        ),
        layout_rendering=LayoutRenderSpec(
            source_symbol_kind="ct_scanner",
            show_radiation_symbol=True,
            show_patient_symbol=True,
            show_one_m_circle=True,
            reference_circle_anchor="source",
            annotation_kind="ct_weekly_scatter",
            equipment_width_m=2.2,
            equipment_depth_m=0.85,
            table_width_m=0.6,
            table_length_m=2.5,
            label_cleanup_phrases=("diagnostic CT family.", "diagnostic CT.", "CT component."),
            source_label_param="scanner_model",
            render_param_keys=(
                "ksec_mGy_per_100mAs_at_1m",
                "scans_per_week",
                "workload_mAs_per_scan",
                "scanner_kvp",
                "scanner_family",
                "scanner_vendor",
                "scanner_model",
                "scanner_source",
                "scanner_ksec_status",
                "ksec_energy_kvp",
            ),
            render_param_defaults={
                "scans_per_week": 60,
                "workload_mAs_per_scan": 630,
                "scanner_kvp": 140,
            },
        ),
        classification="hybrid_spect_ct_controlled",
        default_energy_label="140 kVp",
        default_solver_mode="auto",
        controlled_area_required=True,
        patient_radioactivity_present=True,
        xray_generator_present=True,
        hybrid_ct_present=True,
        notes="Hybrid SPECT/CT room placeholder; not production-enabled in the CT quotation build.",
        report_wording=ReportWordingSpec(
            methodology_paragraphs=(
                "For hybrid SPECT/CT rooms, the governing barrier requirement is determined by the component that controls the barrier outcome under the stated assumptions.",
            ),
            methodology_rows=(("SPECT/CT", "Combined CT and NM contribution model using the governing barrier component."),),
            construction_shielding_height_mm=2400,
        ),
    )
)

_REGISTERED_PLUGINS: tuple[ModalityPlugin, ...] = (
    CT_PLUGIN,
    XRAY_PLUGIN,
    SPECT_PLUGIN,
    PET_PLUGIN,
    _SPECT_CT_PLACEHOLDER_PLUGIN,
)


def _validated_plugins(plugins: Iterable[ModalityPlugin]) -> tuple[ModalityPlugin, ...]:
    validated: list[ModalityPlugin] = []
    modality_ids: set[str] = set()
    source_owners: dict[str, str] = {}

    for plugin in plugins:
        validate_modality_plugin(plugin)
        spec = plugin.spec
        if spec.modality_id in modality_ids:
            raise ModalityContractError(f"Duplicate modality id {spec.modality_id!r}.")
        modality_ids.add(spec.modality_id)

        for source in plugin.source_specs():
            source_type = source.source_type
            owner = source_owners.get(source_type)
            if owner is not None:
                raise ModalityContractError(
                    f"Source type {source_type!r} is owned by both {owner!r} and {spec.modality_id!r}."
                )
            source_owners[source_type] = spec.modality_id
        validated.append(plugin)

    return tuple(validated)


_VALIDATED_PLUGINS: tuple[ModalityPlugin, ...] = _validated_plugins(_REGISTERED_PLUGINS)
_REGISTERED_MODALITIES: tuple[ModalitySpec, ...] = tuple(
    plugin.spec for plugin in _VALIDATED_PLUGINS
)

MODALITY_PLUGIN_REGISTRY: dict[str, ModalityPlugin] = {
    plugin.spec.modality_id: plugin for plugin in _VALIDATED_PLUGINS
}
MODALITY_REGISTRY: dict[str, ModalitySpec] = {
    modality_id: plugin.spec for modality_id, plugin in MODALITY_PLUGIN_REGISTRY.items()
}
SOURCE_PLUGIN_REGISTRY: dict[str, ModalityPlugin] = {
    source.source_type: plugin
    for plugin in _VALIDATED_PLUGINS
    for source in plugin.source_specs()
}
# Backward-compatible source aliases are routed to their owning plugin so
# legacy projects still receive plugin-owned UI and TVL behaviour.
SOURCE_PLUGIN_REGISTRY.update({
    "primary_xray": XRAY_PLUGIN,
    "general_xray": XRAY_PLUGIN,
})


def registered_modalities() -> list[ModalitySpec]:
    return list(_REGISTERED_MODALITIES)


def production_modalities() -> list[ModalitySpec]:
    return [spec for spec in _REGISTERED_MODALITIES if spec.production_enabled]


def coming_soon_modalities() -> list[ModalitySpec]:
    return [spec for spec in _REGISTERED_MODALITIES if not spec.production_enabled]


def production_modality_names() -> list[str]:
    return [spec.modality_id for spec in production_modalities()]


def coming_soon_modality_names() -> list[str]:
    return [spec.modality_id for spec in coming_soon_modalities()]


def non_production_plugin_stub_names() -> list[str]:
    """Return standalone registered modality stubs shown in the Rooms UI.

    Legacy hybrid compatibility placeholders such as SPECT/CT remain registered
    for saved-project support, but are not advertised as standalone plugin stubs.
    """

    return [
        spec.display_name
        for spec in coming_soon_modalities()
        if spec.compliance_only and not spec.hybrid_ct_present
    ]


def is_production_modality(modality_id: str) -> bool:
    spec = get_modality_spec(modality_id)
    return bool(spec and spec.production_enabled)


def get_modality_plugin(modality_id: str | None) -> ModalityPlugin | None:
    return MODALITY_PLUGIN_REGISTRY.get(str(modality_id or "").strip())


def require_modality_plugin(modality_id: str | None) -> ModalityPlugin:
    plugin = get_modality_plugin(modality_id)
    if plugin is None:
        known = ", ".join(sorted(MODALITY_PLUGIN_REGISTRY)) or "none"
        raise KeyError(f"Unknown modality {modality_id!r}; known modalities: {known}")
    return plugin


def get_modality_spec(modality_id: str | None) -> ModalitySpec | None:
    plugin = get_modality_plugin(modality_id)
    return plugin.spec if plugin is not None else None


def require_modality_spec(modality_id: str | None) -> ModalitySpec:
    spec = get_modality_spec(modality_id)
    if spec is None:
        known = ", ".join(sorted(MODALITY_REGISTRY)) or "none"
        raise KeyError(f"Unknown modality {modality_id!r}; known modalities: {known}")
    return spec




def layout_rendering_for_modality(modality_id: str | None) -> LayoutRenderSpec:
    plugin = get_modality_plugin(modality_id)
    return plugin.layout_rendering() if plugin is not None else LayoutRenderSpec()

def source_owner_plugin(source_type: str | None) -> ModalityPlugin | None:
    return SOURCE_PLUGIN_REGISTRY.get(str(source_type or "").strip())



def initialise_modality_services(app, base_path) -> None:
    """Let each registered plugin initialise any private runtime service state."""
    for plugin in _VALIDATED_PLUGINS:
        plugin.initialise_app_services(app, base_path)


def source_form_vendor_values(source_type: str | None, app) -> list[str]:
    plugin = source_owner_plugin(source_type)
    return list(plugin.source_form_vendor_values(app, source_type)) if plugin is not None else []


def source_form_model_values(source_type: str | None, app) -> list[str]:
    plugin = source_owner_plugin(source_type)
    return list(plugin.source_form_model_values(app, source_type)) if plugin is not None else []


def source_form_schema_for_type(source_type: str | None, app) -> SourceFormSchema | None:
    plugin = source_owner_plugin(source_type)
    return plugin.source_form_schema(app, source_type) if plugin is not None else None


def source_form_tvl_params_for_type(source_type: str | None, app) -> dict[str, Any] | None:
    plugin = source_owner_plugin(source_type)
    return plugin.source_form_tvl_params(app, source_type) if plugin is not None else None


def handle_source_form_event(app, event_kind: str, source_type: str | None, *, force: bool = False):
    plugin = source_owner_plugin(source_type)
    if plugin is None:
        return None
    return plugin.handle_source_form_event(app, event_kind, source_type, force=force)


def collect_plugin_source_form_params(app, source_type: str | None) -> dict[str, Any] | None:
    plugin = source_owner_plugin(source_type)
    return plugin.collect_source_form_params(app, source_type) if plugin is not None else None


def load_plugin_source_form_params(app, source_type: str | None, params: Mapping[str, Any]) -> bool:
    plugin = source_owner_plugin(source_type)
    return bool(plugin and plugin.load_source_form_params(app, source_type, params))


def sanitize_source_params_for_type(
    source_type: str | None, params: Mapping[str, Any]
) -> dict[str, Any]:
    plugin = source_owner_plugin(source_type)
    return plugin.sanitize_source_params(source_type, params) if plugin is not None else dict(params or {})


def finalise_source_form_params_for_type(
    app, source_type: str | None, params: Mapping[str, Any]
) -> dict[str, Any]:
    plugin = source_owner_plugin(source_type)
    return (
        plugin.finalise_source_form_params(app, source_type, params)
        if plugin is not None
        else dict(params or {})
    )


def source_live_preview_lines(
    app,
    source_type: str | None,
    source_name: str,
    radiation_type: str,
) -> tuple[str, ...] | None:
    plugin = source_owner_plugin(source_type)
    if plugin is None:
        return None
    return plugin.live_preview_lines(app, source_type, source_name, radiation_type)


def report_wording_for_modality(modality_id: str | None) -> ReportWordingSpec:
    plugin = get_modality_plugin(modality_id)
    return plugin.report_wording() if plugin is not None else ReportWordingSpec()


def source_report_summary_columns_for_type(source_type: str | None) -> list[tuple[str, str]]:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        columns = plugin.spec.report_summary_columns_for_source_type(text)
        if columns:
            return columns
    return [
        ("name", "Source"),
        ("source_type", "Type"),
        ("radiation_type", "Radiation"),
    ]


def source_report_summary_row_for_payload(source_payload: dict | None) -> list[str]:
    row = source_payload or {}
    source_type = str(row.get("source_type", "") or "").strip()
    plugin = source_owner_plugin(source_type)
    if plugin is not None:
        summary = plugin.spec.report_summary_row_for_source(row)
        if summary:
            return summary
    return [str(row.get(key, "") or "") for key, _heading in source_report_summary_columns_for_type(source_type)]



def source_report_content_for_payload(source_payload: dict | None) -> dict:
    row = source_payload or {}
    source_type = str(row.get("source_type", "") or "").strip()
    plugin = source_owner_plugin(source_type)
    if plugin is None:
        return {}
    return plugin.report_content_for_source(row)


def report_content_for_modalities(modality_ids: Iterable[str]) -> dict:
    """Return prepared modality-owned report content for export services."""
    paragraphs: list[str] = []
    rows: list[list[str]] = []
    assumptions: list[str] = []
    seen_modalities: set[str] = set()
    for modality_id in modality_ids:
        text = str(modality_id or "").strip()
        if not text or text in seen_modalities:
            continue
        seen_modalities.add(text)
        wording = report_wording_for_modality(text)
        for paragraph in wording.methodology_paragraphs:
            if paragraph not in paragraphs:
                paragraphs.append(paragraph)
        for element, method in wording.methodology_rows:
            row = [str(element), str(method)]
            if row not in rows:
                rows.append(row)
        for bullet in wording.assumption_bullets:
            if bullet not in assumptions:
                assumptions.append(bullet)
    return {
        "methodology_paragraphs": paragraphs,
        "methodology_rows": rows,
        "assumption_bullets": assumptions,
    }


def construction_shielding_height_for_modality(modality_id: str | None) -> int:
    return int(report_wording_for_modality(modality_id).construction_shielding_height_mm)

def locked_source_mapping(production_only: bool = True) -> dict[str, list[tuple[str, str]]]:
    specs: Iterable[ModalitySpec] = production_modalities() if production_only else registered_modalities()
    return {spec.modality_id: spec.source_mapping for spec in specs}


def _iter_specs(production_only: bool = False) -> Iterable[ModalitySpec]:
    return production_modalities() if production_only else registered_modalities()


def _iter_plugins(production_only: bool = False) -> Iterable[ModalityPlugin]:
    if not production_only:
        return _VALIDATED_PLUGINS
    return tuple(plugin for plugin in _VALIDATED_PLUGINS if plugin.spec.production_enabled)


def expected_source_types_for_modality(modality_id: str | None) -> list[str]:
    spec = get_modality_spec(modality_id)
    return spec.expected_source_types if spec else []


def default_source_type_for_modality(modality_id: str | None) -> str:
    spec = get_modality_spec(modality_id)
    return spec.default_source_type if spec else ""


def source_type_options(*, production_only: bool = False) -> list[str]:
    seen: set[str] = set()
    options: list[str] = []
    for spec in _iter_specs(production_only=production_only):
        for source_type in spec.expected_source_types:
            if source_type not in seen:
                seen.add(source_type)
                options.append(source_type)
    return options


def source_label_for_type(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        source_spec = plugin.source_spec_for_type(text)
        if source_spec is not None:
            return source_spec.label
    return text or "Source"


def default_source_params_for_type(source_type: str | None) -> dict:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.default_source_params(text)
    return {}


def source_form_kind_for_type(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.form_kind_for_source_type(text)
    return "generic"


def source_ui_labels_for_type(source_type: str | None) -> dict[str, str]:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.ui_labels_for_source_type(text)
    return {}


def source_ui_label(source_type: str | None, key: str, default: str) -> str:
    return source_ui_labels_for_type(source_type).get(key, default)


def source_readiness_labels_for_type(source_type: str | None) -> dict[str, str]:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.readiness_labels_for_source_type(text)
    return {}


def source_readiness_label(source_type: str | None, key: str, default: str) -> str:
    return source_readiness_labels_for_type(source_type).get(key, default)



def source_dose_model_for_type(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.dose_model_for_source_type(text)
    return "generic"


def source_default_tvl_key(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.default_tvl_key_for_source_type(text)
    return ""


def source_contribution_group(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.contribution_group_for_source_type(text)
    return "other"


def source_ncrp_solver_mode(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.ncrp_solver_mode_for_source_type(text)
    return ""



def source_validation_kind_for_type(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.validation_kind_for_source_type(text)
    return "generic"


def source_blocking_reason_for_basis(source_type: str | None, basis: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.blocking_reason_for_source_basis(text, basis)
    return ""


def source_calculation_blocked_reason(source_type: str | None) -> str:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.spec.calculation_blocked_reason_for_source_type(text)
    return ""


def source_readiness_result_for_source(
    source_type: str | None,
    params: dict | None,
    context: dict | None = None,
) -> dict | None:
    text = str(source_type or "").strip()
    plugin = source_owner_plugin(text)
    if plugin is not None:
        return plugin.readiness_result(text, params or {}, context or {})
    return None


def source_types_with_role(role: str, *, production_only: bool = False) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for plugin in _iter_plugins(production_only=production_only):
        for source_type in plugin.source_types_with_role(role):
            if source_type not in seen:
                seen.add(source_type)
                values.append(source_type)
    return values


def ct_ksec_source_types(*, production_only: bool = False) -> list[str]:
    return source_types_with_role("ct_ksec_scatter", production_only=production_only)


def source_types_with_dose_model(dose_model: str, *, production_only: bool = False) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for plugin in _iter_plugins(production_only=production_only):
        for source_type in plugin.source_types_with_dose_model(dose_model):
            if source_type not in seen:
                seen.add(source_type)
                values.append(source_type)
    return values


def source_types_with_contribution_group(group: str, *, production_only: bool = False) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for plugin in _iter_plugins(production_only=production_only):
        for source_type in plugin.source_types_with_contribution_group(group):
            if source_type not in seen:
                seen.add(source_type)
                values.append(source_type)
    return values


def source_types_with_ncrp_solver_mode(solver_mode: str, *, production_only: bool = False) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for plugin in _iter_plugins(production_only=production_only):
        for source_type in plugin.source_types_with_ncrp_solver_mode(solver_mode):
            if source_type not in seen:
                seen.add(source_type)
                values.append(source_type)
    return values


def ct_scatter_dose_source_types(*, production_only: bool = False) -> list[str]:
    return source_types_with_dose_model("ct_ksec_weekly_dose", production_only=production_only)


def xray_primary_source_types(*, production_only: bool = False) -> list[str]:
    return source_types_with_dose_model("xray_primary", production_only=production_only)


def geometry_ui_for_modality(modality_id: str | None):
    plugin = get_modality_plugin(modality_id)
    if plugin is None:
        from modalities.base import GeometryUISpec
        return GeometryUISpec()
    return plugin.geometry_ui()


def modality_for_source_inventory(source_types: Iterable[str]) -> ModalitySpec | None:
    inventory = {str(value or '').strip() for value in source_types if str(value or '').strip()}
    for plugin in _VALIDATED_PLUGINS:
        if set(plugin.spec.expected_source_types) == inventory:
            return plugin.spec
    return None


def source_type_for_modality_role(modality_id: str | None, role: str) -> str:
    plugin = get_modality_plugin(modality_id)
    if plugin is None:
        return ''
    values = plugin.source_types_with_role(role)
    return values[0] if values else ''
