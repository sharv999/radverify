# PET Current Status After Step 29

This document is the authoritative current-status pointer for the PET implementation after controlled production-host enablement, the Step 28 non-issueable PDF boundary, and the Step 29 final release/cleanup/completion gate.

## Current controlled production-host scope

- PET is admitted through the production modality registry.
- Durable PET working-project state is enabled.
- Production PET calculation uses the dedicated replay-verified dispatch boundary and approved PET physics/provenance contracts.
- In-app PET Results use the frozen canonical Results model.
- The legacy generic `pet_patient` calculator remains blocked.
- PET/CT CT shielding continues to be assessed through the CT modality until a composite workflow is introduced.

## Output scope remains closed

- Issued/final PET PDF routing is disabled.
- Machine export remains disabled.
- Certification/signature routing remains disabled.
- The Step 28 PDF renderer remains non-issueable and output-ineligible.

## Durable working-state schema

New saves use `radshield_pet_working_source_v3`, which records:

- `production_host_enabled = true`
- `production_calculation_enabled = true`
- `issued_output_enabled = false`

Legacy `radshield_pet_working_source_v2` payloads remain readable and migrate to v3 when saved again.

## Historical architecture documents

The Step 15 production-readiness audit is retained as audit evidence and is explicitly marked as a historical snapshot. Its NO-GO/non-production statements describe PET at Step 15 and do not override this current-status document or the Step 29 release/completion gates.

## Completion marker

PET is formally architecturally complete for the current production-host scope. Future work that opens issued output or materially expands the physics/source model is a new scope expansion rather than continuation of the core PET architecture build.
