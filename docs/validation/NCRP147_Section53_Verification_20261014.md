# NCRP 147 Section 5.3 — Radshield physics verification

Date: 2026-10-14
Source: uploaded radshield_current_source(20261014-110621).zip
Scope: engine/xray_ncrp147_fig52.py and tests/test_xray_xr08b_fig52_physics.py

## Executed reference-scenario calculations

| Scenario | Material | Design goal (mGy/week) | Engine required (mm) | Published reference (mm) |
|---|---|---:|---:|---:|
| Floor under table | Concrete | 0.020 | 35.15774 | ~35 |
| Ceiling | Concrete | 0.020 | 43.93476 | ~44 |
| Chest Bucky | Pb | 0.100 | 0.48366 | ~0.45 |
| Darkroom | Pb | 0.025 | 0.52128 | ~0.53 |
| Cross-table | Pb | 0.020 | 0.67566 | ~0.78 |
| Control wall | Pb | 0.100 | 0.26351 | ~0.27 |

These reference numbers are from the previously identified Section 5.3 benchmarks. This execution did not independently re-read the standard pages; treat published values as pending source-page reconciliation.

## Critical distinction: individual maximum vs combined transmission

The representative floor and chest Bucky scenarios use combination='governing_max'. At the returned thicknesses, summing all modeled components yields:

| Scenario | Sum at governing-max thickness (mGy/week) | Goal | Joint sum thickness (mm) |
|---|---:|---:|---:|
| Floor | 0.03836090 | 0.020 | 48.24124 |
| Chest Bucky | 0.16340324 | 0.100 | 0.65776 |

This does not by itself invalidate the NCRP published procedure; whether the standard expects combined dose at those positions needs careful interpretation. Do not silently change the engine to joint mode.

## Tests

`python -m pytest -q tests/test_xray_xr08b_fig52_physics.py` -> 12 passed in 0.19 s.

These tests include a cross-table assertion expecting ~0.68 mm rather than the published ~0.78 mm; therefore green tests are not a full NCRP reference qualification.

## Required next qualification tasks

1. Reconcile exact standard page/equation/source terms for cross-table and floor/chest combined-dose conventions.
2. Build independently sourced fixed expected-results data (do not generate expected results from engine under test).
3. Verify representative engine vs project-geometry adapter vs UI schedule vs PDF, including distances, pre-shielding and design goals.
4. Confirm REVIEW status rationale separately from numerical dose/thickness acceptance.
5. Keep production physics unchanged until reference reconciliation and regression tests are complete.
