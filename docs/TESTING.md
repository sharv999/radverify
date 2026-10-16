# Testing

This project uses `pytest` for lightweight regression testing of the radiation shielding app.

The current tests focus on safety-critical CT ksec behaviour, source synchronisation, reporting basis, legacy CSV quarantine, and barrier calculation smoke checks.

## Install pytest

From the project root:

```powershell
python -m pip install pytest
```

Check installation:

```powershell
python -m pytest --version
```

## Run all tests

From the project root:

```powershell
python -m pytest tests
```

## Run individual test files

```powershell
python -m pytest tests/test_ct_ksec_workflow.py
python -m pytest tests/test_source_normalization.py
python -m pytest tests/test_project_sources.py
python -m pytest tests/test_report_ksec_basis.py
python -m pytest tests/test_legacy_csv_quarantine.py
python -m pytest tests/test_barrier_smoke.py
python -m pytest -q
python -m tools.pet_cli_regression .\tests\fixtures\pet_requests\pet_cli_regression_manifest.json

```

## Current test coverage

| Test file | Purpose |
|---|---|
| `test_ct_ksec_workflow.py` | CT scanner database ksec, NULL ksec, manual override, audit state |
| `test_source_normalization.py` | Ensures normalisation does not wipe scanner/ksec/audit fields |
| `test_project_sources.py` | Protects `project.sources` as the source of truth |
| `test_report_ksec_basis.py` | Ensures report-facing ksec basis is correct |
| `test_legacy_csv_quarantine.py` | Prevents old CSV/default ksec pathways from returning |
| `test_barrier_smoke.py` | Broad barrier calculation smoke tests |


## Expected result

A healthy run should end with all tests passing, for example:

```text
==================  all tests passed  ==================
```

The exact number of tests may change as the suite grows.

## Safety-critical behaviours protected

The test suite should catch regressions where:

- a NULL scanner ksec is silently replaced by a conservative/default value
- manual ksec override stops working
- manual ksec audit fields are lost
- Geometry, Results, QA, or report logic diverge on ksec basis
- stale `room.sources` overwrites authoritative `project.sources`
- legacy CSV ksec paths start returning values again
- barrier calculations stop producing expected result structures

## VS Code test discovery

Open the Command Palette:

```text
Ctrl + Shift + P
```

Then run:

```text
Python: Configure Tests
```

Choose:

```text
pytest
```

Then choose:

```text
tests
```

The Testing beaker icon in the left sidebar can then run individual tests or the full suite.

## Recommended workflow before committing

Run:

```powershell
python -m pytest tests
```

Then commit only if all tests pass:

```powershell
git add tests
git commit -m "Add or update regression tests"
git push
```

## PET headless validation gate

The PET headless calculation path is frozen at baseline `pet-headless-v1` before any PET UI or production-report work begins.

Run both commands from the project root for every change that touches PET source-domain models, attenuation data, isotropic barrier solving, serialization, replay, services, CLI tools, fixtures, or regression manifests:

```powershell
python -m pytest -q
python -m tools.pet_cli_regression .\tests\fixtures\pet_requests\pet_cli_regression_manifest.json
```

A PET change is acceptable only when:

- the full pytest suite passes;
- both curated F-18 and Ga-68 regression fixtures pass;
- the expected cross-platform output digests are unchanged, unless an intentional physics or contract revision has been reviewed;
- deterministic replay remains verified; and
- PET remains unavailable as a production modality and excluded from production project serialization, shielding dispatch, and report generation.

### Frozen PET headless baseline

The machine-readable freeze marker is defined in:

```text
serialization/pet_headless_freeze.py
```

It records the approved contract-version baseline and the two validation-gate commands. The accompanying tests prevent silent contract-version drift or accidental imports into UI and production-output modules.

Do not connect the frozen PET headless calculation path to `app.py`, `services/project_serializer.py`, `engine/shielding_engine.py`, or any report module while the freeze is active. The isolated preview panel may call the PET service through its dedicated UI boundary.

An explicit unfreeze requires all of the following:

1. a documented reason for enabling the next PET layer;
2. deliberate contract-version updates where behaviour or schema changes;
3. reviewed updates to known-answer tests, curated fixtures, and manifest digests where applicable;
4. successful completion of both PET validation-gate commands; and
5. a separate reviewed change that removes or revises the freeze guard.

## PET UI preview phase

The PET UI integration remains intentionally limited to the **PET Development
Preview** panel on the Sources tab. The current baseline is
`pet-ui-preview-v5`.

The panel validates F-18/Ga-68 patient workload inputs, calculates the
unshielded weekly dose at 1 m, and permits one non-production barrier-request
preview using the frozen PET calculation service. Each independent barrier preview row accepts:

- attenuation material,
- source-to-barrier distance,
- occupancy factor,
- weekly design goal, and
- optional provided material thickness.

It displays the required TVL count, required thickness and, when a provided
thickness is entered, PASS/FAIL and transmitted weekly dose. The calculation is
replay verified before it is displayed.

Step 4 permits save/load only through a separate `*.petpreview.json` file using `serialization/pet_preview_state.py`. This file is explicitly non-production and is not part of the normal Radshield project schema.

Step 5 adds a read-only Geometry-tab overlay. It places a purple PET patient-source marker and 1 m contour at the current room source coordinates, draws dashed preview wall results when barrier names map clearly to N/E/S/W walls, and lists all preview barriers in a canvas legend. The overlay consumes only transient PET preview data and must never mutate `RoomGeometry`, project sources, production barriers, or report payloads.

The preview is not a production modality pathway. It must not:

- create or modify project sources,
- save PET source or barrier inputs in the working project (separate preview files only),
- enter production shielding dispatch,
- populate the production barrier schedule, or
- appear in PDF/report output.

The PET headless validation gate remains mandatory:

```powershell
python -m pytest -q
python -m tools.pet_cli_regression .\tests\fixtures\pet_requests\pet_cli_regression_manifest.json
```

Any later step that persists PET inputs, calculates all room barriers, modifies
the production barrier schedule, or exposes PET in reports requires a separate
reviewed integration change.

## PET preview UI terminology freeze

The non-production single-source PET preview field order, visible terminology,
units, defaults, and results-table headings are frozen in
`tabs/pet_preview_ui_contract.py`. Change that contract only as an explicit,
versioned PET UI revision. The contract remains outside the project schema,
production dispatch, normal Results tab, and reports.
