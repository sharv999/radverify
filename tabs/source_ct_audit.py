from __future__ import annotations

from typing import Any, Dict

from tabs.source_ct_actions import mark_manual_ct_ksec_override
from tabs.source_ct_state import (
    ct_audit_params_from_vars,
    load_ct_audit_vars_from_params,
)


def inject_ct_audit_params(app, params: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(params or {})
    clean.update(ct_audit_params_from_vars(app))
    return clean