# PET Step 26 — Production-Host Readiness Audit

## Decision

**Validated foundations: YES. Production-host integration: NO-GO until three explicit host blockers are resolved.**

PET already has approved/frozen radionuclide and 511 keV attenuation data, deterministic replay-protected calculation dispatch from durable working state, a canonical in-app Results model, and a frozen non-issueable report preview boundary. These foundations are sufficient for controlled host promotion.

## Remaining host blockers

1. **Production registry remains closed.** `PET` is not in `production_modality_names()` and `PET_MODALITY.production_enabled` remains false.
2. **Working-state semantics are historical.** The durable PET working-state v2 still serialises `production_eligible=false`. The next step must evolve this contract backward-compatibly rather than rewriting old project files in place.
3. **Source readiness still globally blocks PET.** Persisted PET state currently produces a blocking source-readiness error. For parity with SPECT, this must become calculation/Results-enabled but `output_blocking=true`.

## Boundaries that must remain closed

- The legacy generic `pet_patient` shielding-engine path remains blocked. Production PET must continue to use the dedicated replay-verified PET dispatch boundary.
- Issued/final PDF generation remains closed.
- CSV/JSON or other machine export remains closed.
- Certification/signatures remain closed.
- The current report preview remains explicitly non-issueable.

## Next step

Controlled PET production-host enablement: promote PET through the registry, evolve the durable working-state schema backward-compatibly to current host/calculation semantics, and change source readiness from globally blocking to host-review/output-blocking. Do not open issued outputs.
