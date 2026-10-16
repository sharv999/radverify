"""Barriers tab layout boundary.

This module owns the public layout entry point for the Barriers tab.
The existing implementation remains in ``tabs.barriers_tab`` for this slice so
``app.py`` can delegate tab construction consistently with the other extracted
tab-layout modules.
"""

from __future__ import annotations

from typing import Any

from tabs.barriers_tab import build_barriers_tab as _build_barriers_tab


def build_barriers_tab(app: Any) -> Any:
    """Build the Barriers tab widgets for the desktop app."""
    return _build_barriers_tab(app)
