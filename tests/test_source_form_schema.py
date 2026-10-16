from modalities.base import SourceFormSchema
from modalities.registry import source_owner_plugin


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class _App:
    def __init__(self):
        self.ct_vars = {
            "scanner_vendor": _Var("GE"),
            "scanner_model": _Var("Discovery CT750 HD"),
        }
        self.ct_scanner_resolution_context = object()


def test_ct_source_form_schema_preserves_exact_row_layout(monkeypatch):
    plugin = source_owner_plugin("ct_scatter")
    monkeypatch.setattr(type(plugin), "source_form_vendor_values", lambda self, app, source_type: ("GE", "Siemens"))
    monkeypatch.setattr(type(plugin), "source_form_model_values", lambda self, app, source_type: ("Discovery CT750 HD",))

    schema = plugin.source_form_schema(_App(), "ct_scatter")
    assert isinstance(schema, SourceFormSchema)
    assert [field.row for field in schema.fields] == list(range(12))
    assert [field.label for field in schema.fields] == [
        "Scanner vendor",
        "Scanner model",
        "Scanner kVp",
        "Scans per week",
        "Workload (mAs/scan)",
        "Ksec (mGy/100 mAs @ 1 m)",
        "Manual ksec entered by",
        "Manual ksec reason/source",
        "Manual ksec reference",
        "Manual ksec updated",
        "Ksec status/source",
        "Scanner resolved",
    ]
    assert schema.fields[0].widget_kind == "combobox"
    assert schema.fields[0].state == "disabled"
    assert schema.fields[1].widget_kind == "combobox"
    assert schema.fields[1].state == "disabled"
    assert schema.fields[2].widget_kind == "readonly_entry"
    assert (schema.fields[4].row, schema.fields[4].key, schema.fields[4].label) == (
        4, "workload_mAs_per_scan", "Workload (mAs/scan)"
    )
    assert (schema.fields[5].row, schema.fields[5].key, schema.fields[5].label) == (
        5, "ksec_mGy_per_100mAs_at_1m", "Ksec (mGy/100 mAs @ 1 m)"
    )
    assert schema.fields[5].widget_attr == "ct_ksec_entry"
    assert [field.row for field in schema.fields[6:]] == [6, 7, 8, 9, 10, 11]
    assert schema.fields[5].event_sequence == "<KeyRelease>"
    assert schema.fields[5].event_kind == "manual_ksec_edited"
    assert all(field.variable_group == "ct_vars" for field in schema.fields)


def test_generic_form_renderer_contains_no_ct_widget_construction():
    from pathlib import Path

    text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")
    form_section = text.split("def refresh_source_form_by_type", 1)[1].split(
        "def update_auto_tvl_key_display", 1
    )[0]
    assert "ct_vendor_combo" not in form_section
    assert "ct_model_combo" not in form_section
    assert "ct_ksec_entry" not in form_section
    assert "app.ct_vars" not in form_section
    assert "source_ui_label" not in form_section


class _FormApp:
    def __init__(self, method="manual"):
        self.primary_vars = {
            "xray_method": _Var(method),
            "workload_uSv_per_week_at_1m": _Var("100000"),
            "use_factor": _Var("0.25"),
            "exam_room_type": _Var("general_radiography"),
            "exams_per_week": _Var("100"),
            "tube_potential_kvp": _Var("120"),
            "derived_workload_uSv_per_week_at_1m": _Var(""),
            "derived_use_factor_default": _Var(""),
            "derived_method_note": _Var(""),
        }
        self.nm_vars = {"radionuclide": _Var("Tc99m")}


def test_xray_host_exposes_plugin_owned_source_form_schema():
    plugin = source_owner_plugin("xray_primary")

    manual = plugin.source_form_schema(_FormApp("manual"), "xray_primary")
    ncrp = plugin.source_form_schema(_FormApp("ncrp_simplified"), "xray_primary")
    assert manual is not None
    assert [field.key for field in manual.fields] == ["xray_method", "workload_uSv_per_week_at_1m", "use_factor"]
    assert ncrp is not None
    assert [field.key for field in ncrp.fields] == [
        "xray_method", "exam_room_type", "exams_per_week", "tube_potential_kvp",
        "derived_workload_uSv_per_week_at_1m", "derived_use_factor_default", "derived_method_note",
    ]


def test_nm_source_form_schema_preserves_exact_row_layout():
    plugin = source_owner_plugin("nm_patient")
    schema = plugin.source_form_schema(_FormApp(), "nm_patient")
    assert [field.row for field in schema.fields] == list(range(12))
    assert [field.label for field in schema.fields] == [
        "Radionuclide",
        "No. MPS-R",
        "No. MPS-S",
        "No. Bone",
        "Activity MPS-R (MBq)",
        "Activity MPS-S (MBq)",
        "Activity Bone (MBq)",
        "Time MPS-R (h)",
        "Time MPS-S (h)",
        "Time Bone (h)",
        "R factor MPS",
        "R factor Bone",
    ]
    assert schema.fields[0].values == ("Tc99m", "I131")
    assert all(field.variable_group == "nm_vars" for field in schema.fields)


def test_form_layout_contains_no_source_type_specific_form_or_tvl_branches():
    from pathlib import Path

    text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")
    assert 'stype in ("primary_xray", "xray_primary")' not in text
    assert 'stype == "nm_patient"' not in text
    assert 'stype == "general_xray"' not in text
    assert "app.primary_vars" not in text
    assert "app.nm_vars" not in text
    assert "app.ct_vars" not in text
    assert "source_form_tvl_params_for_type(source_type, app)" in text
