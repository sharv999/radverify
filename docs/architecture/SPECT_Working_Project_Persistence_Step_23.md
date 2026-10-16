# SPECT Working-Project Persistence Boundary — Step 23

> **Historical snapshot:** This document records the state at its named step. Current SPECT host/release status is defined by Step 35/36 release-gate documentation; older NO-GO or non-production wording below is intentionally preserved as historical evidence.


Date: 2026-08-23  
Scope: durable SPECT working inputs only. Production calculation dispatch, Results, reports, export, and certification remain closed.

## Decision

Step 23 opens only the ordinary working-project persistence boundary for validated Tc-99m source/workload inputs. The state is stored under `Room.modality_state` and is explicitly marked non-production.

Persisted SPECT working state contains:

- Tc-99m radionuclide identity;
- administered activity;
- patients per week;
- imaging duration;
- the exact Step 20 physics-freeze identity;
- the exact Step 21 canonical request schema/version identity.

It does not contain:

- calculated dose or barrier results;
- preview-only X/Y what-if geometry;
- Results/report payloads;
- production eligibility;
- export/certification state.

## Geometry boundary

Normal room and barrier geometry continues to be persisted through the existing `Room.geometry` and barrier model. The dedicated `.spectpreview.json` format remains the only persistence path for SPECT preview what-if geometry. Step 23 does not copy preview X/Y coordinates into normal project state.

## Fail-closed loading

`services.project_io.load_project_from_file()` validates any SPECT working state before returning a loaded project. A stale Step 20 physics freeze, unknown Step 21 request contract, malformed source value, or SPECT state attached to a non-SPECT room causes load failure.

## Calculation reconstruction

`engine.spect_working_project_request` can combine a validated durable source state with caller-supplied Step 5 barrier requests to reconstruct the exact Step 21 canonical request envelope. This proves persistence/replay compatibility without connecting normal project loading to production calculation dispatch.

## Production gates retained

Step 23 deliberately leaves all existing production gates closed:

- `SPECT` remains absent from `production_modality_names()`;
- `spect_patient` remains calculation-blocked;
- the Step 22 output blocker remains active;
- Results and report modules do not import the Step 23 working-state contract;
- no SPECT production calculation is triggered by save or load.

## Exit criteria

Step 23 is complete when a valid SPECT working source can round-trip through normal project JSON, stale or malformed SPECT working state fails closed, preview geometry remains segregated, and the restored source can reproduce the Step 21 canonical request boundary deterministically.
