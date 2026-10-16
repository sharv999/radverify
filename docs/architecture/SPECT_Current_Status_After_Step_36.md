# SPECT Current Status After Step 36

This document is the authoritative current-status pointer for the SPECT implementation after the Step 35 release gate and Step 36 historical wording/schema cleanup.

## Current controlled production-host scope

- SPECT is admitted through the production modality registry.
- Durable SPECT working-project state is enabled.
- Gated Tc-99m production calculation uses the Step 26 dispatch path.
- In-app production Results use the Step 27 payload path.
- The Step 25 <=1% low-transmission policy remains mandatory and fail-closed.
- The legacy generic `spect_patient` calculator remains blocked.

## Output scope remains closed

- Issued/final SPECT PDF routing is disabled.
- Machine export remains disabled.
- Certification/signature routing remains disabled.
- The Step 33 PDF renderer remains non-issueable and output-ineligible.

## Durable working-state schema

New saves use `radshield_spect_working_source_v2`, which records:

- `production_host_enabled = true`
- `production_calculation_enabled = true`
- `issued_output_enabled = false`

Legacy `radshield_spect_working_source_v1` payloads remain readable. Their historical false flags are interpreted only as the original Step 23 envelope semantics and are not used as current host-status declarations.

## Historical architecture documents

Earlier Step 19-24 documents are retained as audit evidence. Their NO-GO/non-production statements describe the state at those steps and are explicitly marked as historical snapshots; they do not override this current-status document or the Step 35/36 release gate.

## Step 37 completion marker

The current production-host architecture is formally closed by `SPECT_Architecture_Completion_Step_37.md`. Future work that widens issued output or physics scope is a new scope expansion rather than continuation of this architecture build.
