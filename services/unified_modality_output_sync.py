"""Synchronise shared production UI outputs after PET/SPECT source-state edits.

The unified Sources tab edits modality-owned PET/SPECT working state directly,
so it bypasses the legacy generic Source form ``Apply`` path. This helper
re-establishes the same production UI synchronisation boundary: repair the
room Source inventory first, then refresh the shared Results surface and the
Geometry risk rendering from canonical Results.
"""
from __future__ import annotations

from typing import Any


def sync_unified_modality_outputs(app: Any) -> None:
    """Refresh shared Results/Geometry after modality working-state edits.

    Source-inventory repair must run first because Geometry display gating is
    driven by canonical source readiness. Without that repair, valid PET/SPECT
    Results can be hidden and the canvas can fall back to its base fail colour.
    """
    repair = getattr(app, "_repair_invalid_source_inventory", None)
    if callable(repair):
        try:
            repair()
        except Exception:
            pass

    # The Barriers tab is now a peer presentation of the same canonical
    # modality Results model. Refresh it immediately after source-inventory
    # repair so PET/SPECT source edits cannot leave a stale or empty schedule.
    refresh_barriers = getattr(app, "refresh_barrier_schedule", None)
    if callable(refresh_barriers):
        try:
            refresh_barriers()
        except Exception:
            pass

    refresh_results = getattr(app, "refresh_results_tab", None)
    if callable(refresh_results):
        try:
            refresh_results()
        except Exception:
            pass

    geometry_tab = getattr(app, "geometry_tab", None)
    request_redraw = getattr(geometry_tab, "request_redraw", None)
    if callable(request_redraw):
        try:
            request_redraw()
        except Exception:
            pass
