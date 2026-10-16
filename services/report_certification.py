from __future__ import annotations

"""
Report certification/gating helper.

This module is kept as the public certification API, but the final wording
decision is delegated to services.report_wording_guard so report status,
source readiness, export eligibility and calculation-integrity wording cannot
drift apart.
"""

from typing import Any, Dict

from services.report_wording_guard import build_report_wording_state


def build_report_certification_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the controlled certificate/report wording state for a payload."""
    return build_report_wording_state(payload)
