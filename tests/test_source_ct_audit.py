from pathlib import Path


def test_source_ct_audit_module_owns_manual_override_audit_helpers():
    app_text = Path("app.py").read_text(encoding="utf-8")
    audit_text = Path("tabs/source_ct_audit.py").read_text(encoding="utf-8")
    actions_text = Path("tabs/source_ct_actions.py").read_text(encoding="utf-8")
    state_text = Path("tabs/source_ct_state.py").read_text(encoding="utf-8")

    assert "from tabs.source_ct_actions import mark_manual_ct_ksec_override" in audit_text
    assert "ct_audit_params_from_vars" in audit_text
    assert "load_ct_audit_vars_from_params" in audit_text
    assert "def inject_ct_audit_params(" in audit_text

    assert "def mark_manual_ct_ksec_override(" in actions_text
    assert "def ct_audit_params_from_vars(" in state_text
    assert "def load_ct_audit_vars_from_params(" in state_text

    removed_app_methods = [
        "def _mark_manual_ct_ksec_override(self",
        "def _ct_audit_params_from_vars(self",
        "def _inject_ct_audit_params(self",
        "def _load_ct_audit_vars_from_params(self",
    ]

    for token in removed_app_methods:
        assert token not in app_text


def test_ct_audit_callers_use_module_helpers_directly():
    joined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "tabs/source_form_layout.py",
            "tabs/source_form_state.py",
            "tabs/source_tab_actions.py",
        ]
    )

    forbidden = [
        "app._mark_manual_ct_ksec_override",
        "app._inject_ct_audit_params(",
        "app._load_ct_audit_vars_from_params(",
        "app._ct_audit_params_from_vars(",
    ]

    for token in forbidden:
        assert token not in joined

    ct_text = Path("modalities/ct.py").read_text(encoding="utf-8")
    assert "from tabs.source_ct_audit import mark_manual_ct_ksec_override" in ct_text
    assert "return mark_manual_ct_ksec_override(app)" in ct_text
    assert "load_ct_audit_vars_from_params(app," in joined
    assert "from tabs.source_ct_audit import inject_ct_audit_params" in ct_text
    assert "inject_ct_audit_params(" in ct_text
    assert "inject_ct_audit_params(" not in Path("tabs/source_tab_actions.py").read_text(encoding="utf-8")
