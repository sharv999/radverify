from __future__ import annotations

# Central public CT ksec resolver boundary.
# Implementation lives with the scanner-resolution service to keep scanner
# metadata and ksec lookup rules in one place.
from services.ct_scanner_resolution import resolve_database_ct_ksec

__all__ = ["resolve_database_ct_ksec"]
