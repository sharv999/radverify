"""Locked non-production X-ray modality plugin stub.

The current X-ray implementation is retained in this module for later
reactivation, but the registered plugin deliberately exposes only a blocked
architecture stub.  This prevents X-ray calculations, forms, barrier results,
and reports from being used in the current CT production build.
"""

from __future__ import annotations

from typing import Any, Mapping

from modalities.base import (
    DeclarativeModalityPlugin,
    GeometryUISpec,
    LayoutRenderSpec,
    ModalitySpec,
    ReportWordingSpec,
    SourceFormFieldSpec,
    SourceFormSchema,
    SourceFormTextSpec,
    SourceSpec,
)


XRAY_MODALITY_ID = "X-ray"
XRAY_SOURCE_TYPE = "xray_primary"
XRAY_SOURCE_ALIASES = ("primary_xray", "general_xray")
XRAY_CALCULATION_BLOCK_REASON = (
    "Generic X-ray source-dose calculation remains disabled; qualified General Radiography uses the barrier-aware NCRP 147 pathway."
)
XRAY_RELEASE_BASIS = "ncrp147_general_radiography_issueable"
XRAY_FIG52_REQUALIFICATION_BLOCK_REASON = (
    "General Radiography output is temporarily fail-closed pending NCRP 147 Section 5.3 / Figure 5.2 "
    "representative-room requalification."
)
XRAY_UNQUALIFIED_OUTPUT_BLOCK_REASON = (
    "X-ray issued output requires General Radiography with the qualified NCRP 147 simplified method."
)


def xray_source_readiness_result(
    source_type: str,
    source_params: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Release-gate readiness for the qualified General Radiography pathway."""

    source_name = str(context.get("source_name", "General Radiography") or "General Radiography")
    room_name = str(context.get("room_name", "X-ray Room") or "X-ray Room")
    method = str(source_params.get("xray_method", "") or "").strip()
    room_type = str(source_params.get("exam_room_type", "") or "").strip()
    xr07_qualified = (
        str(source_type or XRAY_SOURCE_TYPE).strip() == XRAY_SOURCE_TYPE
        and method == "ncrp_simplified"
        and room_type == "general_radiography"
    )
    # XR-08 requalification gate: XR-07 did not yet cover every representative-
    # room scenario in NCRP 147 Section 5.3 / Figure 5.2. Keep issued output
    # fail-closed until the joint primary/secondary and preshielding cases are
    # explicitly qualified.
    qualified = xr07_qualified
    if qualified:
        return {
            "source_type": XRAY_SOURCE_TYPE,
            "source_name": source_name,
            "room_name": room_name,
            "overall_status": "PASS",
            "status": "PASS",
            "blocking": False,
            "basis": XRAY_RELEASE_BASIS,
            "output_blocking": False,
            "message": "Qualified NCRP 147 General Radiography pathway ready for Preliminary Shielding Assessment output.",
            "checks": [],
            "errors": [],
            "warnings": [],
            "notes": [
                "Project-specific NCRP 147 Section 5.3 / Figure 5.2 barrier physics and deterministic report replay are qualified.",
                "Generic X-ray source-dose calculation remains disabled by design.",
            ],
        }

    reason = (
        XRAY_FIG52_REQUALIFICATION_BLOCK_REASON
        if xr07_qualified
        else XRAY_UNQUALIFIED_OUTPUT_BLOCK_REASON
    )
    return {
        "source_type": str(source_type or XRAY_SOURCE_TYPE),
        "source_name": source_name,
        "room_name": room_name,
        "overall_status": "BLOCKED",
        "status": "BLOCKED",
        "blocking": True,
        "basis": "not_implemented" if not source_params else "xray_unqualified_configuration",
        "output_blocking": True,
        "message": reason,
        "checks": [],
        "errors": [f"{room_name}: {reason}" if room_name else reason],
        "warnings": [],
        "notes": [reason],
    }

XRAY_DEFAULT_SOURCE_PARAMS = {
    "xray_method": "ncrp_simplified",
    "workload_uSv_per_week_at_1m": 100000,
    "use_factor": 0.25,
    "exam_room_type": "general_radiography",
    "exams_per_week": 100,
    "tube_potential_kvp": 120,
    "derived_workload_uSv_per_week_at_1m": "",
    "derived_use_factor_default": "",
    "derived_method_note": "",
}

XRAY_MODALITY = ModalitySpec(
    modality_id=XRAY_MODALITY_ID,
    display_name="X-ray",
    production_enabled=True,
    default_room_name="X-ray Room 1",
    expected_sources=(
        SourceSpec(
            source_type=XRAY_SOURCE_TYPE,
            label="General Radiography",
            role="xray_primary",
            default_radiation_type="xray_120kvp",
            default_params=XRAY_DEFAULT_SOURCE_PARAMS,
            form_kind="xray_primary",
            dose_model="not_implemented",
            default_tvl_key="",
            contribution_group="xray_primary",
            ncrp_solver_mode="",
            validation_kind="not_implemented",
            readiness_labels={
                "source": "X-ray primary source",
                "not_implemented": "X-ray calculation not implemented",
            },
            readiness_validator=xray_source_readiness_result,
            calculation_blocked_reason=XRAY_CALCULATION_BLOCK_REASON,
        ),
    ),
    geometry_ui=GeometryUISpec(
        selector_kind="static",
        static_options=("General Radiography",),
        primary_source_role="xray_primary",
        source_label="X-ray",
    ),
    layout_rendering=LayoutRenderSpec(source_symbol_kind="xray_machine", show_radiation_symbol=False, show_one_m_circle=False, show_barrier_status_text=False),
    classification="xray_controlled",
    default_energy_label="120 kVp",
    default_solver_mode="blocked",
    controlled_area_required=True,
    xray_generator_present=True,
    compliance_only=True,
    notes="General Radiography NCRP 147 Preliminary Shielding Assessment output enabled for the qualified pathway only.",
    report_wording=ReportWordingSpec(
        report_title="Preliminary X-ray Shielding Schedule",
        report_subtitle="General Radiography — NCRP Report No. 147 simplified shielding assessment",
        cover_introduction="Preliminary shielding assessment using the qualified NCRP Report No. 147 General Radiography pathway.",
        methodology_rows=(("General Radiography", "Qualified NCRP Report No. 147 simplified workload-distribution and Archer transmission pathway."),),
        construction_shielding_height_mm=2400,
        limitation_bullets=(
            "Issueable output is limited to the qualified NCRP 147 General Radiography pathway.",
            "Unsupported or manual X-ray configurations remain fail-closed.",
        ),
    ),
)


class XRayModalityPlugin(DeclarativeModalityPlugin):
    METHOD_VALUES = ("manual", "ncrp_simplified")
    EXAM_ROOM_TYPE_VALUES = ("general_radiography",)

    @staticmethod
    def _value(app, group: str, key: str, default=""):
        try:
            return getattr(app, group)[key].get()
        except Exception:
            return default

    def source_form_schema(self, app, source_type):
        if str(source_type or "").strip() not in {XRAY_SOURCE_TYPE, "primary_xray"}:
            return None

        method = str(self._value(app, "primary_vars", "xray_method", "manual")).strip() or "manual"
        common = (
            SourceFormFieldSpec(
                key="xray_method",
                label="X-ray method",
                row=0,
                variable_group="primary_vars",
                widget_kind="combobox",
                values=self.METHOD_VALUES,
                state="readonly",
                event_sequence="<<ComboboxSelected>>",
                event_kind="xray_method_changed",
            ),
        )
        if method == "manual":
            return SourceFormSchema(
                source_type=XRAY_SOURCE_TYPE,
                fields=common + (
                    SourceFormFieldSpec(
                        key="workload_uSv_per_week_at_1m",
                        label="Weekly primary workload @ 1 m (uSv/wk)",
                        row=1,
                        variable_group="primary_vars",
                    ),
                    SourceFormFieldSpec(
                        key="use_factor",
                        label="Use factor U",
                        row=2,
                        variable_group="primary_vars",
                    ),
                ),
                text_rows=(
                    SourceFormTextSpec(
                        text="Manual mode: primary barriers use B = P d² / (W U T).",
                        row=3,
                    ),
                ),
            )

        return SourceFormSchema(
            source_type=XRAY_SOURCE_TYPE,
            fields=common + (
                SourceFormFieldSpec(
                    key="exam_room_type",
                    label="X-ray room type",
                    row=1,
                    variable_group="primary_vars",
                    widget_kind="combobox",
                    values=self.EXAM_ROOM_TYPE_VALUES,
                    state="readonly",
                    event_sequence="<<ComboboxSelected>>",
                    event_kind="xray_room_type_changed",
                ),
                SourceFormFieldSpec(
                    key="exams_per_week",
                    label="Exams per week (integer)",
                    row=2,
                    variable_group="primary_vars",
                    widget_kind="integer_entry",
                ),
                SourceFormFieldSpec(
                    key="tube_potential_kvp",
                    label="Tube potential (kVp)",
                    row=3,
                    variable_group="primary_vars",
                    widget_kind="integer_entry",
                ),
                SourceFormFieldSpec(
                    key="derived_workload_uSv_per_week_at_1m",
                    label="Derived floor-primary workload @ 1 m (uSv/wk)",
                    row=4,
                    variable_group="primary_vars",
                    widget_kind="readonly_entry",
                ),
                SourceFormFieldSpec(
                    key="derived_use_factor_default",
                    label="Default use factor",
                    row=5,
                    variable_group="primary_vars",
                    widget_kind="readonly_entry",
                ),
                SourceFormFieldSpec(
                    key="derived_method_note",
                    label="Method note",
                    row=6,
                    variable_group="primary_vars",
                    widget_kind="readonly_entry",
                ),
            ),
        )

    def _refresh_derived_preview(self, app) -> None:
        from engine.shielding_engine import compute_xray_ncrp_simplified_source_summary

        try:
            method = str(self._value(app, "primary_vars", "xray_method", "manual")).strip()
            if method != "ncrp_simplified":
                for key in (
                    "derived_workload_uSv_per_week_at_1m",
                    "derived_use_factor_default",
                    "derived_method_note",
                ):
                    app.primary_vars[key].set("")
                return

            summary = compute_xray_ncrp_simplified_source_summary({
                "exam_room_type": str(self._value(app, "primary_vars", "exam_room_type", "general_radiography")).strip() or "general_radiography",
                "exams_per_week": app._safe_float(self._value(app, "primary_vars", "exams_per_week", 0), 0.0),
                "tube_potential_kvp": app._safe_int(self._value(app, "primary_vars", "tube_potential_kvp", 120), 120),
            })
            app.primary_vars["derived_workload_uSv_per_week_at_1m"].set(
                f"{float(summary.get('derived_workload_uSv_per_week_at_1m', 0.0)):.1f}"
            )
            app.primary_vars["derived_use_factor_default"].set(
                str(summary.get("derived_use_factor_default", ""))
            )
            app.primary_vars["derived_method_note"].set(str(summary.get("note", "")))
        except Exception:
            for key in (
                "derived_workload_uSv_per_week_at_1m",
                "derived_use_factor_default",
                "derived_method_note",
            ):
                try:
                    app.primary_vars[key].set("")
                except Exception:
                    pass

    def handle_source_form_event(self, app, event_kind, source_type, *, force=False):
        if event_kind == "xray_method_changed":
            if getattr(app, "_loading_source_form", False):
                return None
            app.save_current_source_form_draft()
            app.sync_current_source_to_model(ignore_errors=True)
            app._source_dirty = True
            app._loading_source_form = True
            try:
                app.refresh_source_form_by_type()
                app.update_auto_tvl_key_display()
            finally:
                app._loading_source_form = False
            app.update_live_source_preview_from_form()
            return None

        if event_kind == "xray_room_type_changed":
            self._refresh_derived_preview(app)
            app.update_auto_tvl_key_display()
            app.on_source_input_change()
        return None

    def source_form_tvl_params(self, app, source_type):
        stype = str(source_type or "").strip()
        if stype == "general_xray":
            return {
                "preset": str(self._value(app, "xray_vars", "preset", "")).strip(),
                "exams_per_week": str(self._value(app, "xray_vars", "exams_per_week", 0)).strip() or 0,
            }
        if stype not in {XRAY_SOURCE_TYPE, "primary_xray"}:
            return None

        method = str(self._value(app, "primary_vars", "xray_method", "manual")).strip() or "manual"
        if method == "manual":
            return {
                "xray_method": "manual",
                "workload_uSv_per_week_at_1m": str(self._value(app, "primary_vars", "workload_uSv_per_week_at_1m", 0)).strip() or 0,
                "use_factor": str(self._value(app, "primary_vars", "use_factor", 1.0)).strip() or 1.0,
            }
        return {
            "xray_method": "ncrp_simplified",
            "exam_room_type": str(self._value(app, "primary_vars", "exam_room_type", "general_radiography")).strip() or "general_radiography",
            "exams_per_week": str(self._value(app, "primary_vars", "exams_per_week", 0)).strip() or 0,
            "tube_potential_kvp": str(self._value(app, "primary_vars", "tube_potential_kvp", 120)).strip() or 120,
        }

    def collect_source_form_params(self, app, source_type):
        stype = str(source_type or "").strip()
        if stype not in {XRAY_SOURCE_TYPE, "primary_xray"}:
            return None
        return {
            "xray_method": str(self._value(app, "primary_vars", "xray_method", "manual")).strip() or "manual",
            "workload_uSv_per_week_at_1m": app._safe_float(self._value(app, "primary_vars", "workload_uSv_per_week_at_1m", 100000.0), 100000.0),
            "use_factor": app._safe_float(self._value(app, "primary_vars", "use_factor", 0.25), 0.25),
            "exam_room_type": str(self._value(app, "primary_vars", "exam_room_type", "general_radiography")).strip() or "general_radiography",
            "exams_per_week": app._safe_int(self._value(app, "primary_vars", "exams_per_week", 100), 100),
            "tube_potential_kvp": app._safe_int(self._value(app, "primary_vars", "tube_potential_kvp", 120), 120),
            "derived_workload_uSv_per_week_at_1m": str(self._value(app, "primary_vars", "derived_workload_uSv_per_week_at_1m", "")).strip(),
            "derived_use_factor_default": str(self._value(app, "primary_vars", "derived_use_factor_default", "")).strip(),
            "derived_method_note": str(self._value(app, "primary_vars", "derived_method_note", "")).strip(),
        }

    def load_source_form_params(self, app, source_type, params) -> bool:
        stype = str(source_type or "").strip()
        if stype not in {XRAY_SOURCE_TYPE, "primary_xray"}:
            return False
        p = dict(params or {})
        defaults = dict(XRAY_DEFAULT_SOURCE_PARAMS)
        for key in (
            "xray_method",
            "workload_uSv_per_week_at_1m",
            "use_factor",
            "exam_room_type",
            "derived_workload_uSv_per_week_at_1m",
            "derived_use_factor_default",
            "derived_method_note",
        ):
            app.primary_vars[key].set(str(p.get(key, defaults.get(key, ""))))
        app.primary_vars["exams_per_week"].set(str(int(float(p.get("exams_per_week", defaults["exams_per_week"])))))
        app.primary_vars["tube_potential_kvp"].set(str(int(float(p.get("tube_potential_kvp", defaults["tube_potential_kvp"])))))
        return True


    def live_preview_lines(self, app, source_type, source_name, radiation_type):
        stype = str(source_type or "").strip()
        if stype not in {XRAY_SOURCE_TYPE, "primary_xray", "general_xray"}:
            return None
        if stype == "general_xray":
            from models.shielding_models import Source
            from engine.shielding_engine import compute_source_weekly_dose_at_1m
            params = self.source_form_tvl_params(app, stype) or {}
            dose, tvl_key = compute_source_weekly_dose_at_1m(
                Source(name=source_name, source_type=stype, radiation_type=radiation_type, params=params)
            )
            return (
                "Inputs", "------",
                f"Preset: {params.get('preset', '')}",
                f"Exams/week: {float(params.get('exams_per_week', 0) or 0):.0f}",
                "", "Calculated", "----------",
                f"Weekly scatter dose: {dose:.3f} uSv/week @ 1 m",
                f"TVL key: {tvl_key}",
            )

        params = self.collect_source_form_params(app, stype) or {}
        method = str(params.get("xray_method", "manual") or "manual")
        if method == "manual":
            return (
                "Inputs", "------",
                "Method: Manual weekly workload",
                f"Weekly primary workload @ 1 m: {float(params.get('workload_uSv_per_week_at_1m', 0) or 0):.1f} uSv/week",
                f"Use factor U: {float(params.get('use_factor', 0) or 0):.3f}",
                "", "Calculated", "----------",
                "Primary barriers use B = P d² / (W U T) in the barrier schedule.",
            )
        from engine.shielding_engine import compute_xray_ncrp_simplified_source_summary
        summary = compute_xray_ncrp_simplified_source_summary(params)
        return (
            "Inputs", "------",
            "Method: NCRP simplified",
            f"Exam room type: {summary.get('exam_room_type', '')}",
            f"Exams/week: {float(summary.get('exams_per_week', 0.0)):.0f}",
            f"Tube potential: {int(float(summary.get('tube_potential_kvp', 120)))} kVp",
            "", "Calculated", "----------",
            f"Derived workload @ 1 m: {float(summary.get('derived_workload_uSv_per_week_at_1m', 0.0)):.1f} uSv/week",
            f"Default use factor: {float(summary.get('derived_use_factor_default', 0.25)):.3f}",
            f"Note: {summary.get('note', '')}",
        )


# XR-04: expose the qualified General X-ray UI/geometry behaviour while the
# source readiness/dose-model contract remains explicitly blocked for issued output.
XRAY_PLUGIN = XRayModalityPlugin(XRAY_MODALITY)
