# PET Step 27 — Controlled Production-Host Enablement

## Decision

PET is enabled in the normal RadShield production host for the deliberately limited scope of:

- durable working-project persistence;
- dedicated replay-verified PET calculation dispatch; and
- in-app Results.

This step does **not** enable issued/final PDF, machine export, certification, or signatures.

## Boundaries retained

The legacy generic `pet_patient` source-calculation route remains blocked. Production PET calculation continues to use the dedicated PET dispatch/replay boundary and approved PET physics/provenance contracts.

PET source readiness is `REVIEW`, `blocking=False`, `output_blocking=True`. This allows calculation and in-app Results while the central export gate continues to fail closed for all issued outputs.

## Working-state migration

New saves use `radshield_pet_working_source_v3` with explicit flags:

- `production_host_enabled: true`
- `production_calculation_enabled: true`
- `issued_output_enabled: false`

Legacy `radshield_pet_working_source_v2` payloads remain readable. A subsequent save canonicalises them to v3.

## Next parity step

Add the PET PDF integration-readiness gate and isolated non-issueable PDF preview, keeping issued output closed.
