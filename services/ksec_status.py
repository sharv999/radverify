from __future__ import annotations

"""
Compatibility boundary for CT ksec status resolution.

The CT-specific validation/blocking rules now live with the CT modality
specification in ``modalities.ct``.  This module remains as the stable import
path for existing services, reports and tests.
"""

from typing import Any, Dict, Optional

from modalities.ct import (
    KsecStatus,
    is_ct_ksec_source_type,
    resolve_ct_ksec_status_from_params,
)


def resolve_ksec_status_from_params(
    source_type: Any,
    params: Optional[Dict[str, Any]],
) -> KsecStatus:
    return resolve_ct_ksec_status_from_params(source_type, params or {})


def resolve_ksec_status(src: Any) -> Dict[str, Any]:
    """Convenience wrapper for a Source-like object."""

    source_type = getattr(src, "source_type", "")
    params = getattr(src, "params", {}) or {}
    return resolve_ksec_status_from_params(source_type, params).as_dict()


__all__ = [
    "KsecStatus",
    "is_ct_ksec_source_type",
    "resolve_ksec_status_from_params",
    "resolve_ksec_status",
]
