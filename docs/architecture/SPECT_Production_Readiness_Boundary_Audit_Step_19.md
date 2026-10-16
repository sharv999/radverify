# SPECT Production-Readiness Boundary Audit — Step 19

> **Historical snapshot:** This document records the state at its named step. Current SPECT host/release status is defined by Step 35/36 release-gate documentation; older NO-GO or non-production wording below is intentionally preserved as historical evidence.


Audit basis: `radshield_current_source(6).zip`
Audit date: 2026-08-23
Scope: SPECT Steps 1–18 only. No production code changes are part of this audit.

## Executive finding

**Decision: NO-GO for production enablement.**

The SPECT preview architecture is well isolated and substantially more mature than the production-readiness of its physics inputs. The current desktop remains protected by several independent gates: SPECT is not production-enabled in the modality registry, `spect_patient` is excluded from the production source inventory, the normal shielding engine blocks SPECT calculation dispatch, and SPECT preview persistence uses a dedicated `.spectpreview.json` format that normal project loading rejects.

The principal blockers are upstream of production integration:

1. the Tc-99m radionuclide/source dataset is explicitly `development_nonproduction`;
2. its dose-rate provenance explicitly states that the retained `0.0206 uSv/h/MBq at 1 m` constant is pending separate dataset approval;
3. the practical Tc-99m Archer transmission dataset is also explicitly `development_nonproduction`;
4. very low required transmission can currently produce a calculated thickness flagged as model extrapolation rather than failing closed;
5. the generic source-readiness aggregator does not currently convert the SPECT source validator's `BLOCKED` status into a project-level blocking error;
6. the generic working-project dataclasses/deserializer can represent a hand-crafted SPECT room/source even though the desktop later prunes non-production rooms;
7. there is no frozen production-style SPECT calculation-input manifest and fixture/hash regression layer equivalent to the mature PET pathway.

The correct next step is therefore **not** to enable SPECT in normal project save, Results, reports, or production dispatch. Step 20 should first establish approved/frozen SPECT physics inputs and explicit fail-closed production-readiness gates.

## Boundary matrix

| Boundary | Current implementation | Explicit? | Test protected? | Audit status |
|---|---|---:|---:|---|
| Room/UI production availability | `SPECT_MODALITY.production_enabled=False`; app `ROOM_TYPES = production_modality_names()` | Yes | Yes | **CLOSED / strong** |
| Production source inventory | `locked_source_mapping(production_only=True)` and `source_type_options(production_only=True)` exclude `spect_patient` | Yes | Yes | **CLOSED / strong** |
| Production calculation dispatch | `source_calculation_blocked_reason("spect_patient")` returns `SPECT_CALCULATION_BLOCK_REASON`; normal engine raises before dispatch | Yes | Yes | **CLOSED / strongest** |
| SPECT preview | Dedicated Step 6–18 UI path; Step 5 schedule says `production_eligible=False` | Yes | Yes | **ISOLATED / strong** |
| Preview persistence | Dedicated `.spectpreview.json`; v4 integrity + physics compatibility metadata; normal project loader rejects preview schema | Yes | Yes | **ISOLATED / strong** |
| Normal working-project schema | Generic `Room.modality` / `Source.source_type` strings are unrestricted; `project_from_dict()` accepts them | Partly | Partly | **CLOSED operationally, schema gate indirect** |
| Source-readiness/export preflight | SPECT child validator returns `BLOCKED`, but no `errors`; aggregate room readiness can still report `PASS` | No | Gap demonstrated | **NOT FAIL-CLOSED** |
| Normal Results | No Step 5 SPECT schedule consumer in normal Results; exclusion depends on upstream gates | Indirect | Partly | **CLOSED by composition** |
| Reports/output | Step 5/preview contracts absent from report path; exclusion depends on upstream gates and engine block | Indirect | Partly | **CLOSED, but direct SPECT export blocker missing** |
| Radionuclide physics dataset | Tc-99m only, but status is `development_nonproduction`; dose constant pending separate approval | Yes | Yes | **NO-GO blocker** |
| Narrow-beam attenuation dataset | NIST-based, hashed, explicitly reference-only | Yes | Yes | **REFERENCE READY; not production shielding model** |
| Practical transmission dataset | Oumano 2025 Archer model, hashed, but `development_nonproduction` | Yes | Yes | **NO-GO blocker** |
| Low-transmission handling | caution at `<=0.01`; extrapolation flag below `0.001`; extrapolated thickness still returned | Yes | Yes | **NO-GO until production acceptance policy defined** |
| Replay/provenance | Step 1 has deterministic snapshot/replay harness; preview v4 records dataset/model compatibility | Yes | Yes | **GOOD foundation, not yet production freeze** |

## 1. Registry and room-creation boundary

`modalities/spect.py` registers SPECT with:

- `production_enabled=False`;
- `source_type="spect_patient"`;
- `validation_kind="nonproduction_headless_only"`;
- `calculation_blocked_reason=SPECT_CALCULATION_BLOCK_REASON`.

The desktop derives its selectable room modalities from `production_modality_names()`. In the audited codebase, CT is the only production modality. SPECT remains visible only as a non-production plugin stub.

On project open, `app._prune_unsupported_rooms()` keeps only modalities for which `is_production_modality()` is true. A hand-crafted SPECT room therefore does not survive as an active desktop room.

**Status: strong closed boundary. Do not open yet.**

## 2. Production source inventory

The production source inventory is registry-derived. `locked_source_mapping(production_only=True)` contains CT only, and `source_type_options(production_only=True)` excludes `spect_patient`.

This is a useful independent gate: even if SPECT source-form code exists for preview purposes, it is not part of the normal production source inventory.

**Status: strong closed boundary.**

## 3. Production calculation dispatch

The normal shielding engine asks the registry for `source_calculation_blocked_reason()` before source-dose dispatch. For `spect_patient` the result is the explicit SPECT non-production block reason.

This means the Step 1/4/5 headless SPECT calculation stack cannot be reached accidentally through the normal production shielding engine.

**Status: strongest closed boundary.**

This gate should remain closed until approved datasets, production input provenance, export gating, and canonical production request/replay contracts are complete.

## 4. Headless calculation architecture

There are currently two SPECT headless calculation lineages:

1. **Step 1 compatibility/test harness** — `services/spect_calculation_service.py` plus `serialization/spect_project_contract.py` uses caller-supplied `TvlAttenuationInput` and the generic isotropic TVL solver.
2. **Step 3–5 practical preview pathway** — `engine/spect_practical_transmission.py`, `engine/spect_barrier_calculation.py`, and `engine/spect_barrier_schedule.py` use the Oumano broad-beam Archer transmission model directly.

The Step 3–5 pathway is the physically relevant candidate for future production SPECT shielding. The older Step 1 TVL service is useful as a deterministic architecture/replay harness but should not become a second production implementation.

**Audit requirement before production:** explicitly designate one canonical SPECT production calculation path and quarantine/deprecate the other from production dispatch.

## 5. Tc-99m radionuclide/source physics

`data/spect/spect_radionuclide_physics_development.json` is intentionally non-production:

- dataset ID: `spect-radionuclide-physics-development`;
- revision: `2026-08-18-step-1`;
- approval status: `development_nonproduction`;
- supported radionuclide: Tc-99m only.

The half-life provenance is explicit. The dose-rate provenance is not yet production-grade: it states that the existing Radshield `RMPS = 0.0206 uSv/h/MBq at 1 m` constant is retained for architecture validation **pending separate dataset approval**.

The loader also enforces the development status rather than supporting an approved production revision.

**Status: NO-GO blocker.**

Before any production integration, the Tc-99m source dataset needs independent source verification, a production-approved revision, immutable/hash-checked loading, and a documented acceptance basis for the patient-source dose-rate constant.

## 6. Narrow-beam attenuation reference boundary

`data/spect/spect_tc99m_attenuation_development.json` is a well-defined provenance reference:

- NIST XCOM basis;
- explicit 140.511 keV energy;
- record hash;
- explicit `narrow_beam_exponential_reference_only` scope;
- explicit `development_nonproduction` status.

The Step 4/5 practical shielding calculation does not use this narrow-beam dataset. It is currently used for preview compatibility/provenance only.

**Status: suitable reference boundary, but it must not be promoted as the practical shielding model.**

A future production provenance manifest may record it as a reference dataset, but the production shielding result should continue to come from the approved practical transmission model.

## 7. Practical broad-beam transmission model

`data/spect/spect_tc99m_practical_transmission_development.json` contains Oumano et al. (2025) Archer-fit data for Tc-99m and multiple materials. The loader validates:

- dataset status and scope;
- contract version;
- record SHA-256;
- material identity;
- Archer parameters;
- reproduction of the published fractional-value layers.

This is a strong development boundary, but the dataset still declares:

- `approval_status="development_nonproduction"`;
- `model_scope="broad_beam_archer_reference_model"`.

**Status: NO-GO blocker until reviewed/frozen as a production-approved dataset.**

Before approval, the exact publication values, transcription, material identities/densities, units, and implemented Archer equations should be independently reviewed and signed off.

## 8. Low-transmission / room-scatter boundary

The practical model defines:

- room-scatter caution threshold: `0.01`;
- source-model minimum simulated transmission: `0.001`.

For target transmission below `0.001`, the code returns an Archer-derived thickness with `source_model_extrapolation=True` and text stating that it must not be used as a production shielding result.

For transmission at or below `0.01`, the result carries a room-scatter caution because finite-barrier and room scatter may dominate.

This is appropriate for preview/what-if use. It is not yet a production acceptance rule.

**Status: NO-GO until a production policy is explicit.**

Before production, define whether:

- `<0.001` is a hard calculation block rather than a warning;
- `<=0.01` requires mandatory physicist review or geometry-specific modelling;
- PASS/FAIL must be suppressed or downgraded when either condition applies.

## 9. Preview isolation and persistence

The SPECT preview remains strongly segregated:

- Step 5 result explicitly has `production_eligible=False`;
- UI state is transient unless saved to `.spectpreview.json`;
- preview source position is distinct from saved `RoomGeometry`;
- preview persistence is a separate schema;
- v4 snapshots include SHA-256 integrity and exact physics compatibility metadata;
- normal `services/project_io.py` explicitly rejects the SPECT preview schema as a working project.

Steps 16–18 add only presentation state, workflow hardening, and a non-production decision summary.

**Status: strong isolation boundary.**

This preview architecture should remain intact even after production integration begins. Production state should not be created by silently reusing preview persistence.

## 10. Normal working-project schema

The generic dataclasses are modality-agnostic:

- `Room.modality` is an unrestricted string;
- `Source.source_type` is an unrestricted string;
- `Source.params` is an unrestricted dictionary;
- `project_from_dict()` does not reject non-production modalities or source types.

Therefore a hand-crafted working-project JSON can deserialize a SPECT room/source. The desktop then removes the room through `_prune_unsupported_rooms()`.

This is operationally safe today because registry/dispatch gates remain closed, but the schema itself is not a production eligibility boundary.

**Status: closed indirectly; do not rely on this as the future SPECT safety gate.**

When SPECT persistence is eventually opened, use an explicit versioned production SPECT room/source contract rather than accepting arbitrary preview state.

## 11. Source-readiness / export preflight gap

`spect_source_readiness_result()` returns:

- `overall_status="BLOCKED"`;
- `status="BLOCKED"`;
- the non-production block message.

However, it does not return an `errors` list containing that blocking reason.

`validate_room_source_readiness()` aggregates child `errors` and determines its own `blocking` flag from the presence of errors. With an otherwise complete hand-crafted SPECT room/source, the audited implementation can therefore produce:

- child SPECT source status: `BLOCKED`;
- room overall status: `PASS`;
- room `blocking=False`.

This is the most important production-safety gap found by the audit.

It is masked today by the room-pruning and production calculation-dispatch gates, but it must be fixed **before any upstream SPECT gate is opened**.

**Status: NOT FAIL-CLOSED.**

## 12. Results boundary

The normal Results path does not import the Step 5 SPECT schedule or SPECT preview contracts. New SPECT preview results stay in the preview panel.

The normal Results modules contain some generic/legacy textual handling for SPECT/NM terminology, but that is not an integration of the new `spect_patient` calculation path.

**Status: closed by upstream registry/dispatch gates.**

Before normal Results integration, add a direct regression proving a SPECT working source cannot appear in normal Results until an explicitly production-eligible canonical result contract exists.

## 13. Reports and export boundary

The new SPECT Step 3–18 calculation/preview contracts are not imported into report modules. Normal report generation continues to consume the normal project/results pipeline.

Because the SPECT source-readiness result is not currently propagated as a blocking error, report/export safety should not rely on source-readiness alone. The production shielding-engine block is currently the stronger protection.

There is no direct end-to-end SPECT export test equivalent to the PET production-output blockers.

**Status: operationally closed, but direct fail-closed export protection is required before production integration.**

## 14. Replay, integrity, and provenance maturity

The project already has good building blocks:

- deterministic Step 1 source calculation tests;
- a non-production Step 1 snapshot/replay contract;
- Step 3 record hashes;
- deterministic Step 5 barrier schedule;
- preview v4 canonical payload SHA-256;
- preview v4 exact dataset/model compatibility metadata.

However, there is not yet a single production-style SPECT request envelope and regression manifest that binds the canonical practical Step 3–5 path to frozen input/output hashes in the same way the mature PET pathway does.

**Status: strong foundation, incomplete production freeze.**

## Required blockers before production enablement

### P0 — must be completed before any production gate opens

1. **Approve/freeze the Tc-99m radionuclide/source dataset.**
   - independently verify half-life and the patient-source dose-rate constant;
   - replace the development dataset with an approved immutable revision;
   - fail closed on dataset ID/revision/hash mismatch.

2. **Approve/freeze the practical Tc-99m transmission dataset.**
   - independently verify the published Archer coefficients/fractional layers;
   - freeze exact material identities and units;
   - replace the development-only loader expectation with an approved production revision.

3. **Define low-transmission production policy.**
   - decide hard-block/review semantics for `<0.001` extrapolation;
   - decide mandatory-review semantics for `<=0.01` room-scatter caution;
   - prevent a plain production PASS when the model is outside its accepted range.

4. **Fix source-readiness fail-closed behaviour.**
   - SPECT non-production status must create an explicit blocking error;
   - add end-to-end export/certification tests proving SPECT remains blocked while production dispatch is closed.

5. **Freeze a canonical SPECT production calculation path.**
   - designate the Step 3–5 practical Archer pathway as canonical, if approved;
   - keep the Step 1 caller-supplied TVL service out of production dispatch.

6. **Create production calculation-input provenance/replay.**
   - bind exact approved datasets and contract versions;
   - add known-answer request fixtures;
   - add deterministic output hashes / replay manifest.

### P1 — only after P0 is green

7. Introduce explicit versioned SPECT production working-project persistence.
8. Keep SPECT absent from `production_modality_names()` while persistence is first proven.
9. Add direct normal Results exclusion tests.
10. Add direct PDF/CSV/final-certification fail-closed tests.

### P2 — final controlled opening

11. Enable production calculation dispatch.
12. Map the canonical SPECT result into normal Results.
13. Open report generation last.
14. Only then set the SPECT modality to production-selectable.

## Recommended opening order

Unlike PET at its production-readiness audit, **SPECT should not open the normal project-schema boundary next**, because the source and practical shielding datasets are still explicitly development-only.

Recommended sequence:

### Step 20 — physics dataset approval/freeze

Create production-approved Tc-99m radionuclide/source and practical transmission datasets, with independent provenance review, exact hashes, and fail-closed approved loaders. Define the accepted low-transmission range.

No UI/report/production dispatch change.

### Step 21 — canonical SPECT request/replay freeze

Create a versioned request envelope for the Step 3–5 practical calculation path, bind approved dataset/model provenance, add known-answer fixtures and a deterministic CLI/regression manifest.

No normal desktop integration yet.

### Step 22 — explicit production-readiness/export blocker

Make SPECT non-production state a first-class blocking error in `services/source_readiness.py` / export eligibility and add end-to-end tests for PDF/CSV/certification blocking.

### Step 23 — production working-project persistence only

Introduce a versioned SPECT working-state contract that survives normal save/load while modality selection, dispatch, Results, and reports remain closed.

### Step 24 — production calculation dispatch

Route persisted SPECT state to the frozen practical calculation service.

### Step 25 — Results integration

Map canonical SPECT results into the normal Results model.

### Step 26 — report integration

Open reports last, using the canonical Results payload only.

## GO / NO-GO checklist

| Requirement | Current status |
|---|---|
| Registry production gate closed | GO |
| Production source inventory excludes SPECT | GO |
| Production calculation dispatch blocked | GO |
| Preview isolated from project/report state | GO |
| Preview integrity and compatibility metadata | GO |
| Tc-99m source dataset production-approved | **NO-GO** |
| Practical transmission dataset production-approved | **NO-GO** |
| Low-transmission production acceptance policy | **NO-GO** |
| SPECT source-readiness fail-closed | **NO-GO** |
| Direct production export/certification blocker | **NO-GO** |
| Canonical practical request/replay manifest | **NO-GO** |
| Production working-project SPECT schema | Not yet required |
| Normal Results integration | Intentionally closed |
| Report integration | Intentionally closed |

## Final decision

**NO-GO: do not enable SPECT production selection, normal project persistence, production dispatch, Results, or reports yet.**

The preview architecture is sufficiently isolated to continue serving as a what-if/development tool. The next work should be **SPECT Step 20 — physics dataset approval/freeze**, not additional UI capability and not production integration.

The first production-facing boundary should remain closed until the Tc-99m source constant and practical transmission model are approved/frozen, low-transmission acceptance semantics are explicit, and source-readiness/export gating is fail-closed.
