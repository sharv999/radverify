> **Historical snapshot:** This Step 15 document records the PET readiness state at that point in development. PET was subsequently promoted to the controlled production-host scope in Steps 27-29. Current status is governed by the Step 29 release/completion gates; the historical non-production statements below must not be interpreted as current registry or calculation state.

# PET Production-Readiness Boundary Audit

Audit basis: `radshield_refactor_source23(1).zip`

## Executive finding

The PET headless physics pathway is substantially stronger than the production integration boundary around it. The approved radionuclide dataset, approved attenuation dataset, solver/physics contract versions, and calculation-input provenance manifest are all frozen and fail-closed. PET is still intentionally excluded from the normal desktop workflow by several independent gates.

The four requested production boundaries are all still closed, but not all are equally explicit or equally test-protected. The registry/dispatch boundary is strongest. The normal working-project schema boundary is the weakest because the generic dataclasses and loader are modality-agnostic: a hand-crafted working-project JSON can contain a PET room/source, after which the desktop UI prunes unsupported rooms rather than rejecting the file at schema load.

## Boundary matrix

| Boundary | Current gate | Explicit? | Test protected? | Audit status |
|---|---|---:|---:|---|
| Room/UI availability | `PET_MODALITY.production_enabled=False`; `ROOM_TYPES=production_modality_names()`; loaded non-production rooms pruned by `_prune_unsupported_rooms()` | Yes | Yes | CLOSED / strong |
| Production source inventory | `locked_source_mapping(production_only=True)` and `source_type_options(production_only=True)` exclude `pet_patient` | Yes | Yes | CLOSED / strong |
| Production calculation dispatch | PET `SourceSpec.dose_model="not_implemented"` plus `calculation_blocked_reason`; `compute_source_weekly_dose_at_1m()` raises before dispatch | Yes | Yes | CLOSED / strongest |
| Normal working-project schema | PET has separate `radshield_pet_project_domain_v1` with `production_eligible=false`; normal `Project`/`Source` dataclasses contain no PET-specific fields | Partly | Partly | CLOSED operationally, but schema gate is indirect |
| Normal Results tab | Results consume normal room/source calculation path; PET rooms cannot be created in UI and PET production dispatch raises | Indirect | Partly | CLOSED by upstream gates |
| Reports/output | PET isolated serializers are forbidden from report modules; production payload/report path consumes normal project calculation/readiness | Indirect | Partly | CLOSED by upstream gates; direct PET-export fail-closed test missing |
| PET preview | Dedicated transient preview and `.petpreview.json`; explicit `production_eligible=false` and single-source-per-room | Yes | Yes | ISOLATED / strong |
| Physics/provenance | Approved radionuclide + attenuation datasets, contract versions and provenance manifest pinned | Yes | Yes | READY as headless input boundary |

## 1. Registry and room creation

`modalities/pet.py` registers PET with `production_enabled=False`. The desktop derives `ROOM_TYPES` from `production_modality_names()`, so PET cannot be selected as a normal room modality. The source inventory is likewise built from `locked_source_mapping(production_only=True)`.

On project open, `_prune_unsupported_rooms()` removes rooms whose modality is not production enabled. This means a PET room present in a generic working-project payload does not become an active desktop room.

Tests explicitly assert PET is not a production modality and `pet_patient` is not a production source option.

**Status: strong closed boundary.**

## 2. Production calculation dispatch

PET's registered source definition remains deliberately non-production:

- `form_kind="not_implemented"`
- `dose_model="not_implemented"`
- `validation_kind="not_implemented"`
- `calculation_blocked_reason=PET_CALCULATION_BLOCK_REASON`

`engine.shielding_engine.compute_source_weekly_dose_at_1m()` checks `source_calculation_blocked_reason()` before dose-model dispatch and raises immediately for `pet_patient`.

This is independently covered by registry, PET contract, calculation-service, request-fixture, and replay tests.

**Status: strongest closed boundary; do not open first.**

## 3. Normal project schema

PET has a separate versioned project-domain serializer (`serialization/pet_project_contract.py`) which explicitly requires `production_eligible=false`. Tests ensure this serializer is not imported by `app.py`, the normal working-project serializer, the production shielding engine, or report modules.

However, the normal model itself is generic:

- `Room.modality` is an unrestricted string.
- `Source.source_type` is an unrestricted string.
- `Source.params` is an unrestricted dictionary.
- `project_from_dict()` does not reject non-production modalities or source types.
- `services/project_io.py` loads the generic project before the UI later prunes unsupported rooms.

Therefore the schema boundary is not fail-closed at deserialisation. It is operationally closed by the UI's production-modality pruning.

**Status: closed, but this is the weakest/least explicit requested boundary.**

## 4. Normal Results tab

The Results tab is wired to `app.get_room_barrier_results()` and the normal shielding engine. There is no PET preview adapter injected into this path. PET preview output remains in the dedicated non-production PET preview tab.

There is no direct `if PET` exclusion inside Results; exclusion is achieved by the registry/UI and dispatch gates. A PET room cannot normally survive into the active UI project, and a `pet_patient` passed to the normal engine is blocked.

**Status: closed by composition rather than a Results-specific gate.**

This is acceptable while PET is non-production, but when the first upstream gate is opened, a dedicated regression test should continue proving PET cannot enter normal Results until that boundary is intentionally opened.

## 5. Reports and export

The isolated PET serializers are explicitly kept out of report modules by tests. Report construction is modality-agnostic and consumes the normal project/results payload rather than PET preview state.

There is an important audit gap: there is no dedicated end-to-end test that constructs a PET-bearing normal working project and proves PDF/CSV/final certification are rejected specifically because PET is non-production.

Also, `pet_source_readiness_result()` returns `status="BLOCKED"`, but it does not populate an `errors` array. `validate_room_source_readiness()` derives its blocking boolean from collected `errors`, not from a child source's `status`. Thus source-readiness alone is not a reliable PET production gate. Today this is masked by the earlier room-pruning and calculation-dispatch barriers.

**Status: operationally closed, but direct export fail-closed protection should be added before any upstream PET gate is opened.**

## 6. Preview isolation

The PET preview remains well isolated:

- dedicated PET preview state schema;
- explicit `production_eligible=false`;
- explicit `single_source_per_room=true`;
- PET-specific position is transient, separate from CT geometry source position;
- preview output contract is versioned;
- preview does not enter normal Results or reports.

**Status: strong isolation boundary.**

## 7. Physics and provenance readiness

The calculation side is already substantially frozen:

- approved F-18/Ga-68 radionuclide dataset;
- approved 511 keV attenuation dataset;
- fail-closed approved-dataset loading;
- frozen PET physics contract version;
- frozen isotropic solver contract version;
- frozen calculation-input provenance manifest binding exact datasets and contract versions;
- deterministic request/replay fixtures and CLI regression hashes.

**Status: suitable foundation for controlled production integration.**

## Validation run during audit

`python -m pytest -q -m "not integration"`

Result: **508 passed, 3 skipped, 5 deselected**.

`python -m tools.pet_cli_regression ./tests/fixtures/pet_requests/pet_cli_regression_manifest.json`

Result: **PASS** for both frozen F-18 and Ga-68 fixtures with replay verification.

## Recommended opening order

### First: normal project schema persistence only

Open the project-schema boundary first, while keeping all other production gates closed.

The first production-integration step should introduce a versioned single-source PET room/source representation into the working-project schema, including PET position and the provenance-manifest identity needed to replay the calculation. Loading must reject unsupported PET schema versions and incompatible provenance rather than silently pruning or coercing them.

At the end of that step:

- PET rooms can be saved and reloaded losslessly;
- PET remains absent from `production_modality_names()`;
- `pet_patient` remains calculation-blocked in the production engine;
- normal Results remain PET-free;
- report/export remains PET-blocked.

### Second: explicit production-readiness/export gate

Before dispatch is opened, make non-production PET status an explicit source-readiness/export blocking error and add end-to-end tests proving PDF/CSV/final certification cannot proceed through the normal pipeline while PET dispatch is still locked.

### Third: production calculation dispatch

Only after persistence and output safety gates are explicit should `pet_patient` be routed from the normal project source representation to the already-frozen PET calculation service.

### Fourth: normal Results

Once dispatch output is canonical and replay-protected, map PET barrier results into the normal Results/barrier schedule payload.

### Fifth: reports

Open reports last, after the normal Results payload is frozen and validated. This minimises the chance that report code becomes a second PET calculation implementation.

## Decision

**Open the project-schema persistence boundary first.**

Do not make PET production selectable yet. The safest next change is a persistence-only integration that proves a single PET source per room can survive normal save/load with its position and provenance identity intact while dispatch, Results and reports remain deliberately blocked.
