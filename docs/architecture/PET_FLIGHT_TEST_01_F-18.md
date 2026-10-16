# PET Flight Test 01 — F-18

**Status:** PASS — COMPLETE
**Date:** 12 August 2026
**Mode:** Non-production PET development preview
**Regression baseline:** 592 passed, 3 skipped

## Objective

Validate the interactive F-18 PET shielding workflow from source/workload entry through geometry response, canonical barrier calculations, shielding PASS/FAIL behaviour, persistence, provenance and non-issueable report preview.

## Test configuration

* Radionuclide: F-18
* Administered activity: 250 MBq/patient
* Patient workload: 30 patients/week
* Activity scaling factor: 1.0
* Exposure period 1:

  * Uptake
  * Start: 0 h
  * Duration: 1.0 h
  * Presence factor: 1.0
* Exposure period 2:

  * Imaging
  * Start: 1.0 h
  * Duration: 0.5 h
  * Presence factor: 1.0
* Single persisted PET patient/source position used for all exposure periods.

## Checks completed

* PET source/workload entry: PASS
* F-18 radionuclide selection and provenance: PASS
* PET source-position geometry overlay: PASS
* Source-to-barrier distance response: PASS
* Inverse-square dose response: PASS
* Required shielding calculation: PASS
* Provided-thickness margin calculation: PASS
* PASS/FAIL transition after barrier-thickness edits: PASS
* Geometry edits refresh PET barrier results immediately: PASS
* Read-only PET Barrier Results Preview: PASS
* Read-only non-issueable PET report preview: PASS
* Main project Save/Open persistence: PASS
* PET development preview Save/Load persistence: PASS
* Barrier material/thickness/occupancy/design-goal round trip: PASS
* Provenance display: PASS
* Deterministic replay verification: PASS
* Production calculation/export/certification/report paths remain blocked: PASS

## Defects identified and corrected during flight test

1. PET panel inaccessible below Sources-tab viewport.

   * Corrected by making the Sources right-hand pane vertically scrollable.

2. PET canonical barrier results not readily visible for interactive testing.

   * Corrected by adding a read-only PET Barrier Results Preview.

3. Geometry barrier edits did not immediately refresh PET results.

   * Corrected by adding refresh hooks to Geometry update paths.

4. PET preview snapshot opened through normal project Open produced an ambiguous schema error.

   * Corrected by explicitly distinguishing PET preview snapshots from normal working projects.

5. Saved PET preview barrier inputs were not restored on reload.

   * Corrected so saved barrier material, provided thickness, occupancy and design goal round-trip correctly.

## Result

**PASS — PET Flight Test 01 complete.**

The F-18 non-production PET calculation workflow demonstrated correct interactive geometry response, barrier calculation behaviour, persistence, provenance, deterministic replay and fail-closed production boundaries.

This result does not constitute production approval or enable issueable PDF, CSV/JSON, certification or normal report generation.
