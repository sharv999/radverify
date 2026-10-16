from __future__ import annotations

"""Modality-owned display context for the unified Barriers tab."""

from dataclasses import dataclass
from typing import Any

from modalities.registry import get_modality_spec, source_form_kind_for_type
from services.ct_source_display import build_ct_source_display_state_from_source


@dataclass(frozen=True)
class BarriersModalityContext:
    energy_basis_display: str
    solver_display: str
    solver_editable: bool


def barriers_modality_context(room: Any, *, current_solver_mode: str = "auto") -> BarriersModalityContext:
    spec = get_modality_spec(getattr(room, "modality", ""))
    if spec is None:
        return BarriersModalityContext("", str(current_solver_mode or "auto"), True)

    sources = list(getattr(room, "sources", []) or [])
    if str(getattr(room, "modality", "") or "").strip().upper() == "X-RAY":
        return BarriersModalityContext(
            energy_basis_display="120 kVp radiographic workload distributions",
            solver_display="NCRP 147 §5.3 / Fig. 5.2",
            solver_editable=False,
        )

    ct_source = next(
        (
            source
            for source in sources
            if source_form_kind_for_type(getattr(source, "source_type", "")) == "ct_ksec"
        ),
        None,
    )

    if ct_source is not None:
        display = build_ct_source_display_state_from_source(ct_source)
        return BarriersModalityContext(
            energy_basis_display=display.energy_basis_display or spec.default_energy_label,
            solver_display=str(current_solver_mode or spec.default_solver_mode or "auto"),
            solver_editable=True,
        )

    return BarriersModalityContext(
        energy_basis_display=str(spec.default_energy_label or ""),
        solver_display=str(spec.default_solver_mode or ""),
        solver_editable=False,
    )
