from pathlib import Path

from modalities.registry import (
    coming_soon_modality_names,
    expected_source_types_for_modality,
    is_production_modality,
    non_production_plugin_stub_names,
    locked_source_mapping,
    production_modality_names,
)
from engine.design_constraints import build_room_constraint_summary


def test_ct_xray_spect_and_pet_are_production_host_modalities():
    assert production_modality_names() == ["CT", "X-ray", "SPECT", "PET"]
    assert is_production_modality("CT")
    assert is_production_modality("SPECT")
    assert not is_production_modality("SPECT/CT")
    assert is_production_modality("PET")
    assert is_production_modality("X-ray")


def test_future_modalities_are_registered_but_coming_soon_only():
    assert coming_soon_modality_names() == ["SPECT/CT"]
    assert expected_source_types_for_modality("SPECT") == ["spect_patient"]
    assert expected_source_types_for_modality("PET") == ["pet_patient"]
    assert expected_source_types_for_modality("SPECT/CT") == [
        "spect_ct_secondary_scatter",
        "nm_patient",
    ]
    assert expected_source_types_for_modality("X-ray") == ["xray_primary"]


def test_rooms_ui_lists_only_actual_non_production_plugin_stubs():
    assert non_production_plugin_stub_names() == []


def test_active_locked_source_mapping_comes_from_production_registry_only():
    assert locked_source_mapping(production_only=True) == {
        "CT": [("ct_scatter", "Secondary scatter source diagnostic")],
        "X-ray": [("xray_primary", "General Radiography")],
        "SPECT": [("spect_patient", "SPECT Patient Source")],
        "PET": [("pet_patient", "PET Patient Source")],
    }


def test_design_constraint_summary_uses_modality_registry_metadata():
    summary = build_room_constraint_summary("CT")

    assert summary["room_type"] == "CT"
    assert summary["expected_source_types"] == ["ct_scatter"]
    assert summary["xray_generator_present"] is True


def test_app_modality_lists_are_registry_backed_not_hard_coded():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "ROOM_TYPES = production_modality_names()" in app_text
    assert "NON_PRODUCTION_PLUGIN_STUBS = non_production_plugin_stub_names()" in app_text
    assert "LOCKED_MODALITY_SOURCES = locked_source_mapping(production_only=True)" in app_text
    assert 'return str(modality or "").strip() == "CT"' not in app_text


def test_geometry_source_type_selector_is_removed_and_registry_remains_authoritative():
    geometry_text = Path("tabs/geometry_tab.py").read_text(encoding="utf-8")

    # Geometry no longer exposes a modality/source-type selector in the
    # single-room workflow. Production modality exposure remains owned by
    # the registry-backed Project modality control.
    assert '"Source type"' not in geometry_text
    assert "self.source_type_var = tk.StringVar" in geometry_text
    assert '["CT", "SPECT/CT", "X-ray"]' not in geometry_text
    assert production_modality_names() == ["CT", "X-ray", "SPECT", "PET"]
    assert "X-ray" in production_modality_names()
    assert "SPECT/CT" not in production_modality_names()


def test_ct_source_defaults_live_behind_modality_spec():
    from modalities.registry import (
        ct_ksec_source_types,
        default_source_params_for_type,
        default_source_type_for_modality,
        source_label_for_type,
        source_type_options,
        source_types_with_role,
    )

    assert default_source_type_for_modality("CT") == "ct_scatter"
    assert source_label_for_type("ct_scatter") == "Secondary scatter source diagnostic"
    assert default_source_params_for_type("ct_scatter")["workload_mAs_per_scan"] == 630
    assert default_source_params_for_type("ct_scatter")["scans_per_week"] == 60
    assert ct_ksec_source_types() == ["ct_scatter", "spect_ct_secondary_scatter"]
    assert source_types_with_role("ct_ksec_scatter") == ["ct_scatter", "spect_ct_secondary_scatter"]
    assert source_type_options(production_only=True) == ["ct_scatter", "xray_primary", "spect_patient", "pet_patient"]


def test_source_paths_consume_registry_instead_of_hard_coded_ct_assumptions():
    source_factory_text = Path("sources/source_factory.py").read_text(encoding="utf-8")
    source_readiness_text = Path("services/source_readiness.py").read_text(encoding="utf-8")
    source_validation_text = Path("sources/source_validation.py").read_text(encoding="utf-8")
    sync_guard_text = Path("services/ui_sync_guard.py").read_text(encoding="utf-8")
    source_tab_layout_text = Path("tabs/source_tab_layout.py").read_text(encoding="utf-8")

    assert "default_source_params_for_type" in source_factory_text
    assert "source_label_for_type" in source_factory_text
    assert "CANONICAL_SOURCE_NAMES" not in source_factory_text

    assert "expected_source_types_for_modality" in source_readiness_text
    assert "EXPECTED_SOURCE_TYPES_BY_MODALITY" not in source_readiness_text

    assert "ct_ksec_source_types" in source_validation_text
    assert "ct_ksec_source_types" in sync_guard_text
    assert "CT_LIKE_SOURCE_TYPES =" not in sync_guard_text

    assert "values=source_type_options(production_only=True)" in source_tab_layout_text


def test_ct_source_ui_metadata_lives_behind_modality_spec():
    from modalities.registry import (
        source_form_kind_for_type,
        source_readiness_label,
        source_ui_label,
    )

    assert source_form_kind_for_type("ct_scatter") == "ct_ksec"
    assert source_ui_label("ct_scatter", "scanner_vendor", "") == "Scanner vendor"
    assert source_ui_label("ct_scatter", "ksec_mGy_per_100mAs_at_1m", "") == "Ksec (mGy/100 mAs @ 1 m)"
    assert source_ui_label("ct_scatter", "workload_mAs_per_scan", "") == "Workload (mAs/scan)"
    assert source_readiness_label("ct_scatter", "manual_ksec_audit", "") == "Manual ksec audit"


def test_ct_ui_source_form_paths_consume_modality_metadata():
    source_form_layout_text = Path("tabs/source_form_layout.py").read_text(encoding="utf-8")
    source_form_sync_text = Path("sources/source_form_sync.py").read_text(encoding="utf-8")
    source_live_preview_text = Path("tabs/source_live_preview.py").read_text(encoding="utf-8")
    ksec_status_text = Path("services/ksec_status.py").read_text(encoding="utf-8")
    ct_display_text = Path("services/ct_source_display.py").read_text(encoding="utf-8")

    assert "source_form_schema_for_type(stype, app)" in source_form_layout_text
    assert "render_plugin_source_form(app, f, stype, schema)" in source_form_layout_text
    assert "app.ct_vars[" not in source_form_layout_text.split("def update_auto_tvl_key_display", 1)[0]
    assert "elif stype in (\"ct_scatter\", \"spect_ct_secondary_scatter\")" not in source_form_layout_text

    assert "collect_plugin_source_form_params" in source_form_sync_text
    assert "load_plugin_source_form_params" in source_form_sync_text
    assert "default_source_params_for_type(source_type)" not in source_form_sync_text
    assert "source_live_preview_lines(" in source_live_preview_text
    assert 'if stype ==' not in source_live_preview_text

    assert "CT_KSEC_SOURCE_TYPES" not in ksec_status_text
    assert "resolve_ct_ksec_status_from_params" in ksec_status_text
    assert "CT_SOURCE_TYPES" not in ct_display_text
    assert "source_form_kind_for_type(source_type_text) == \"ct_ksec\"" in ct_display_text


def test_ct_readiness_labels_are_modality_metadata_driven():
    source_readiness_text = Path("services/source_readiness.py").read_text(encoding="utf-8")
    source_validation_text = Path("sources/source_validation.py").read_text(encoding="utf-8")

    assert "source_readiness_label" in source_readiness_text
    assert "source_readiness_label" in source_validation_text


def test_ct_calculation_dispatch_metadata_lives_behind_modality_spec():
    from modalities.registry import (
        ct_scatter_dose_source_types,
        source_contribution_group,
        source_default_tvl_key,
        source_dose_model_for_type,
        source_types_with_ncrp_solver_mode,
        xray_primary_source_types,
    )

    assert source_dose_model_for_type("ct_scatter") == "ct_ksec_weekly_dose"
    assert source_default_tvl_key("ct_scatter") == "xray_140kvp"
    assert source_default_tvl_key("pet_patient") == "pet_511kev"
    assert source_contribution_group("ct_scatter") == "ct_scatter"
    assert source_types_with_ncrp_solver_mode("ncrp_ct_secondary") == [
        "ct_scatter",
        "spect_ct_secondary_scatter",
    ]
    assert ct_scatter_dose_source_types() == ["ct_scatter", "spect_ct_secondary_scatter"]
    assert xray_primary_source_types() == []


def test_shielding_engine_uses_registry_for_calculation_dispatch():
    engine_text = Path("engine/shielding_engine.py").read_text(encoding="utf-8")

    assert "source_dose_model_for_type(source.source_type)" in engine_text
    assert "source_default_tvl_key(source_type)" in engine_text
    assert "source_contribution_group" in engine_text
    assert "xray_primary_source_types" in engine_text
    assert "ct_scatter_dose_source_types" in engine_text
    assert 'if source.source_type in CT_SCATTER_SOURCE_TYPES' not in engine_text
    assert 'if source_type in CT_SCATTER_SOURCE_TYPES' not in engine_text
    assert 'if source_type in ("primary_xray", "xray_primary")' not in engine_text


def test_ct_validation_rules_live_behind_modality_spec():
    from modalities.ct import CT_NULL_KSEC_BLOCK_REASON, resolve_ct_ksec_status_from_params
    from modalities.registry import (
        source_blocking_reason_for_basis,
        source_readiness_result_for_source,
        source_validation_kind_for_type,
    )

    assert source_validation_kind_for_type("ct_scatter") == "ct_ksec"
    assert source_blocking_reason_for_basis("ct_scatter", "manual_override_required") == CT_NULL_KSEC_BLOCK_REASON

    status = resolve_ct_ksec_status_from_params(
        "ct_scatter",
        {
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_model": "Philips Brilliance 64",
            "scanner_source": "NULL ksec — manual override required",
            "ksec_mGy_per_100mAs_at_1m": "",
        },
    ).as_dict()
    assert status["basis"] == "manual_override_required"
    assert status["status"] == "FAIL"

    readiness = source_readiness_result_for_source(
        "ct_scatter",
        {
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_model": "Philips Brilliance 64",
            "scanner_source": "NULL ksec — manual override required",
            "ksec_mGy_per_100mAs_at_1m": "",
            "scanner_kvp": 140,
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
        },
        {
            "room_name": "CT Room 1",
            "room_modality": "CT",
            "source_name": "Secondary scatter source diagnostic",
            "radiation_type": "xray_140kvp",
        },
    )
    assert readiness is not None
    assert readiness["overall_status"] == "FAIL"
    assert readiness["ksec_basis"] == "manual_override_required"


def test_generic_readiness_paths_delegate_ct_validation_to_modality():
    source_readiness_text = Path("services/source_readiness.py").read_text(encoding="utf-8")
    source_validation_text = Path("sources/source_validation.py").read_text(encoding="utf-8")
    ksec_status_text = Path("services/ksec_status.py").read_text(encoding="utf-8")
    export_eligibility_text = Path("services/export_eligibility.py").read_text(encoding="utf-8")

    assert "source_readiness_result_for_source" in source_readiness_text
    assert "source_readiness_result_for_source" in source_validation_text
    assert "resolve_ct_ksec_status_from_params" in ksec_status_text
    assert "source_blocking_reason_for_basis" in export_eligibility_text
    assert "CT scanner ksec is missing. A documented manual override" not in source_readiness_text
    assert "Manual ksec override audit trail is incomplete" not in source_readiness_text


def test_spect_plugin_is_registered_for_controlled_production_host_integration():
    from modalities.spect import SPECT_CALCULATION_BLOCK_REASON
    from modalities.registry import (
        get_modality_spec,
        source_calculation_blocked_reason,
        source_dose_model_for_type,
        source_readiness_result_for_source,
    )

    spec = get_modality_spec("SPECT")
    assert spec is not None
    assert spec.production_enabled is True
    assert spec.patient_radioactivity_present is True
    assert spec.xray_generator_present is False
    assert spec.hybrid_ct_present is False
    assert spec.expected_source_types == ["spect_patient"]

    assert source_dose_model_for_type("spect_patient") == "spect_patient_production_dispatch"
    assert source_calculation_blocked_reason("spect_patient") == SPECT_CALCULATION_BLOCK_REASON

    readiness = source_readiness_result_for_source(
        "spect_patient",
        {},
        {"room_name": "SPECT Room 1", "source_name": "SPECT Patient Source"},
    )
    assert readiness is not None
    assert readiness["overall_status"] == "REVIEW"
    assert readiness["blocking"] is False
    assert readiness["output_blocking"] is True
    assert readiness["basis"] == "production_host_results_only"


def test_shielding_engine_blocks_nonproduction_spect_stub_before_calculation():
    from engine.shielding_engine import compute_source_weekly_dose_at_1m
    from modalities.spect import SPECT_CALCULATION_BLOCK_REASON
    from models.shielding_models import Source

    source = Source(
        name="SPECT Patient Source",
        source_type="spect_patient",
        radiation_type="tc99m_140kev",
        params={},
    )

    try:
        compute_source_weekly_dose_at_1m(source, {})
    except ValueError as exc:
        assert str(exc) == SPECT_CALCULATION_BLOCK_REASON
    else:
        raise AssertionError("SPECT stub source should be calculation-blocked")


def test_spect_ct_scanner_entries_remain_ct_database_records_not_spect_plugin_sources():
    from modalities.registry import expected_source_types_for_modality

    assert "spect_ct_secondary_scatter" not in expected_source_types_for_modality("SPECT")
    assert "ct_scatter" not in expected_source_types_for_modality("SPECT")



def test_pet_plugin_is_production_host_enabled_but_legacy_calculation_blocked():
    from modalities.pet import PET_CALCULATION_BLOCK_REASON
    from modalities.registry import (
        get_modality_spec,
        source_calculation_blocked_reason,
        source_dose_model_for_type,
        source_readiness_result_for_source,
    )

    spec = get_modality_spec("PET")
    assert spec is not None
    assert spec.production_enabled is True
    assert spec.patient_radioactivity_present is True
    assert spec.xray_generator_present is False
    assert spec.hybrid_ct_present is False
    assert spec.expected_source_types == ["pet_patient"]

    assert source_dose_model_for_type("pet_patient") == "pet_patient_production_dispatch"
    assert source_calculation_blocked_reason("pet_patient") == PET_CALCULATION_BLOCK_REASON

    readiness = source_readiness_result_for_source(
        "pet_patient",
        {},
        {"room_name": "PET Room 1", "source_name": "PET Patient Source"},
    )
    assert readiness is not None
    assert readiness["overall_status"] == "REVIEW"
    assert readiness["blocking"] is False
    assert readiness["output_blocking"] is True
    assert readiness["basis"] == "production_host_results_only"


def test_shielding_engine_blocks_nonproduction_pet_stub_before_calculation():
    from engine.shielding_engine import compute_source_weekly_dose_at_1m
    from modalities.pet import PET_CALCULATION_BLOCK_REASON
    from models.shielding_models import Source

    source = Source(
        name="PET Patient Source",
        source_type="pet_patient",
        radiation_type="f18_511kev",
        params={},
    )

    try:
        compute_source_weekly_dose_at_1m(source, {})
    except ValueError as exc:
        assert str(exc) == PET_CALCULATION_BLOCK_REASON
    else:
        raise AssertionError("PET stub source should be calculation-blocked")


def test_pet_ct_scanner_entries_remain_ct_database_records_not_pet_plugin_sources():
    from modalities.registry import expected_source_types_for_modality

    assert "pet_ct_secondary_scatter" not in expected_source_types_for_modality("PET")
    assert "ct_scatter" not in expected_source_types_for_modality("PET")

def test_final_modality_plugin_contract_is_enforced_at_registration():
    from modalities.base import (
        DeclarativeModalityPlugin,
        ModalityContractError,
        ModalitySpec,
        SourceSpec,
        validate_modality_plugin,
    )

    valid = DeclarativeModalityPlugin(
        ModalitySpec(
            modality_id="Test",
            display_name="Test",
            production_enabled=False,
            default_room_name="Test Room 1",
            expected_sources=(SourceSpec("test_source", "Test Source"),),
        )
    )
    validate_modality_plugin(valid)

    invalid = DeclarativeModalityPlugin(
        ModalitySpec(
            modality_id="Broken",
            display_name="Broken",
            production_enabled=True,
            default_room_name="Broken Room 1",
            expected_sources=(),
        )
    )
    try:
        validate_modality_plugin(invalid)
    except ModalityContractError as exc:
        assert "production modality requires a source" in str(exc)
    else:
        raise AssertionError("Invalid production plugin should fail contract validation")


def test_xray_plugin_stub_is_registered_locked_and_calculation_blocked():
    from modalities.base import ModalityPlugin
    from modalities.registry import (
        default_source_params_for_type,
        get_modality_spec,
        source_calculation_blocked_reason,
        source_default_tvl_key,
        source_dose_model_for_type,
        source_form_kind_for_type,
        source_ncrp_solver_mode,
        source_readiness_result_for_source,
    )
    from modalities.xray import XRAY_CALCULATION_BLOCK_REASON, XRAY_PLUGIN

    assert isinstance(XRAY_PLUGIN, ModalityPlugin)
    spec = get_modality_spec("X-ray")
    assert spec is XRAY_PLUGIN.spec
    assert spec is not None
    assert spec.production_enabled is True
    assert spec.compliance_only is True
    assert spec.expected_source_types == ["xray_primary"]

    assert default_source_params_for_type("xray_primary")["xray_method"] == "ncrp_simplified"
    assert source_form_kind_for_type("xray_primary") == "xray_primary"
    assert source_dose_model_for_type("xray_primary") == "not_implemented"
    assert source_default_tvl_key("xray_primary") == ""
    assert source_ncrp_solver_mode("xray_primary") == ""
    assert source_calculation_blocked_reason("xray_primary") == XRAY_CALCULATION_BLOCK_REASON

    readiness = source_readiness_result_for_source(
        "xray_primary",
        {},
        {"room_name": "X-ray Room 1", "source_name": "X-ray Primary"},
    )
    assert readiness is not None
    assert readiness["overall_status"] == "BLOCKED"
    assert readiness["basis"] == "not_implemented"


def test_shielding_engine_blocks_nonproduction_xray_stub_before_calculation():
    from engine.shielding_engine import compute_source_weekly_dose_at_1m
    from modalities.xray import XRAY_CALCULATION_BLOCK_REASON
    from models.shielding_models import Source

    source = Source(
        name="X-ray Primary",
        source_type="xray_primary",
        radiation_type="xray_120kvp",
        params={
            "xray_method": "manual",
            "workload_uSv_per_week_at_1m": 100000,
            "use_factor": 0.25,
        },
    )

    try:
        compute_source_weekly_dose_at_1m(source, {})
    except ValueError as exc:
        assert str(exc) == XRAY_CALCULATION_BLOCK_REASON
    else:
        raise AssertionError("X-ray stub source should be calculation-blocked")


def test_xray_defaults_are_not_hard_coded_in_generic_source_factory():
    source_factory_text = Path("sources/source_factory.py").read_text(encoding="utf-8")
    registry_text = Path("modalities/registry.py").read_text(encoding="utf-8")

    assert 'elif source_type == "xray_primary"' not in source_factory_text
    assert "from modalities.xray import XRAY_PLUGIN" in registry_text
    assert 'modality_id="X-ray"' not in registry_text


def test_modality_plugin_contract_is_behavioural_not_attribute_only():
    from modalities.base import ModalityContractError, ModalitySpec, SourceSpec, validate_modality_plugin

    class AttributeOnlyPlugin:
        api_version = 1
        spec = ModalitySpec(
            modality_id="AttributeOnly",
            display_name="Attribute Only",
            production_enabled=False,
            default_room_name="Attribute Only Room 1",
            expected_sources=(SourceSpec("attribute_source", "Attribute Source"),),
        )

    try:
        validate_modality_plugin(AttributeOnlyPlugin())
    except ModalityContractError as exc:
        assert "implement ModalityPlugin" in str(exc)
    else:
        raise AssertionError("Attribute-only descriptor must not satisfy the behavioural plugin contract")


def test_registry_exposes_plugins_and_routes_source_behaviour_to_owner():
    from modalities.ct import CT_PLUGIN
    from modalities.registry import (
        get_modality_plugin,
        report_wording_for_modality,
        source_owner_plugin,
        source_readiness_result_for_source,
    )

    assert get_modality_plugin("CT") is CT_PLUGIN
    assert source_owner_plugin("ct_scatter") is CT_PLUGIN
    assert report_wording_for_modality("CT") is CT_PLUGIN.report_wording()

    readiness = source_readiness_result_for_source(
        "ct_scatter",
        {
            "scanner_family": "PHILIPS_BRILLIANCE_64",
            "scanner_model": "Philips Brilliance 64",
            "scanner_source": "NULL ksec — manual override required",
            "ksec_mGy_per_100mAs_at_1m": "",
            "scanner_kvp": 140,
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
        },
        {
            "room_name": "CT Room 1",
            "room_modality": "CT",
            "source_name": "Secondary scatter source diagnostic",
            "radiation_type": "xray_140kvp",
        },
    )
    assert readiness is not None
    assert readiness["overall_status"] == "FAIL"


def test_declarative_plugin_implements_complete_contract_methods():
    from modalities.base import ModalityPlugin
    from modalities.pet import PET_PLUGIN

    assert isinstance(PET_PLUGIN, ModalityPlugin)
    assert PET_PLUGIN.source_specs() == PET_PLUGIN.spec.expected_sources
    assert PET_PLUGIN.source_spec_for_type("pet_patient") is PET_PLUGIN.spec.expected_sources[0]
    assert PET_PLUGIN.default_source_params("pet_patient") == {}
    assert PET_PLUGIN.source_types_with_role("pet_patient") == ["pet_patient"]
    assert PET_PLUGIN.source_types_with_dose_model("pet_patient_production_dispatch") == ["pet_patient"]
    assert PET_PLUGIN.source_types_with_contribution_group("pet_patient") == ["pet_patient"]
    assert PET_PLUGIN.source_types_with_ncrp_solver_mode("") == ["pet_patient"]
