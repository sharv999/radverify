from __future__ import annotations

from typing import Any, Dict

from services.ct_scanner_resolution import ct_model_values_for_source_type


def populate_ct_model_combo_values(app, source_type: str | None = None):
    if not hasattr(app, "ct_model_combo"):
        return

    stype = source_type or app.source_type_var.get().strip()
    vendor = str(app.ct_vars["scanner_vendor"].get()).strip()

    # Prefer JSON models filtered by ct_scanner_metadata.
    values = ct_model_values_for_source_type(app.ct_scanner_resolution_context, stype, vendor)

    try:
        if app.ct_model_combo.winfo_exists():
            app.ct_model_combo["values"] = values
    except Exception:
        return

    current = str(app.ct_vars["scanner_model"].get()).strip()
    if values and current not in values:
        app.ct_vars["scanner_model"].set(values[0])


def ct_audit_params_from_vars(app) -> Dict[str, Any]:
    """Return manual ksec audit fields from the Sources tab variables."""
    if not hasattr(app, "ct_vars"):
        return {}

    keys = (
        "manual_ksec_override",
        "manual_ksec_entered_by",
        "manual_ksec_reason",
        "manual_ksec_reference",
        "manual_ksec_last_updated",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        try:
            out[key] = app.ct_vars[key].get()
        except Exception:
            pass
    return out


def load_ct_audit_vars_from_params(app, params: Dict[str, Any]) -> None:
    """Load manual ksec audit fields into the Sources tab variables."""
    if not hasattr(app, "ct_vars"):
        return

    params = params or {}
    for key in (
        "manual_ksec_override",
        "manual_ksec_entered_by",
        "manual_ksec_reason",
        "manual_ksec_reference",
        "manual_ksec_last_updated",
    ):
        if key in app.ct_vars:
            try:
                app.ct_vars[key].set(str(params.get(key, "")))
            except Exception:
                pass


def load_source_form_draft(app, stype: str):
    draft = app.source_form_drafts.get(stype)
    if not isinstance(draft, dict):
        return

    try:
        if stype in ("primary_xray", "xray_primary"):
            for k, v in app.primary_vars.items():
                if k in draft:
                    v.set(str(draft[k]))

        elif stype in ("ct_scatter", "spect_ct_secondary_scatter"):
            for k, v in app.ct_vars.items():
                if k in draft:
                    v.set(str(draft[k]))

        elif stype == "nm_patient":
            for k, v in app.nm_vars.items():
                if k in draft:
                    v.set(str(draft[k]))
    except Exception:
        pass
