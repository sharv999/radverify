from __future__ import annotations

"""
Backward-compatible CT scanner service facade.

The authoritative scanner-family, display-label, metadata-filtering, family-
resolution and JSON worst-case Ksec behaviour lives in
``services.ct_scanner_resolution.CTScannerResolutionService``.

This facade preserves the older ``CTScannerService`` API used by a small number
of tests/callers while ensuring scanner-resolution logic has only one
implementation.
"""

from typing import Any, Dict, Optional

from services.ct_scanner_resolution import CTScannerResolutionService


class CTScannerService(CTScannerResolutionService):
    """Compatibility facade over the canonical CT scanner resolution service."""

    def __init__(self, raw_database: Optional[Dict[str, Any]] = None, engine: Any = None):
        super().__init__(ct_scatter_engine=engine, raw_database=raw_database or {})
        # Preserve the legacy public attribute for callers that may still inspect it.
        self.engine = engine

    def configure(self, raw_database: Optional[Dict[str, Any]] = None, engine: Any = None) -> None:
        """Preserve the legacy in-place configuration API."""
        if raw_database is not None:
            self.raw_database = raw_database
        if engine is not None:
            self.engine = engine
            self.ct_scatter_engine = engine

    def family_default_phantom(self, scanner_family: str) -> str:
        """Legacy method name retained for compatibility."""
        return self.default_phantom(scanner_family)
