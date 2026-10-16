# PET Flight Test 02 — Ga-68

**Status:** PASS — COMPLETE
**Date:** 12 August 2026
**Mode:** Non-production PET development preview
**Regression baseline:** 592 passed, 3 skipped

## Objective

Independently validate Ga-68 radionuclide handling, decay integration, source-position response, barrier calculations, provenance and deterministic replay using a materially different workload and exposure schedule from the F-18 flight test.

## Test configuration

* Radionuclide: Ga-68
* Administered activity: 150 MBq/patient
* Patient workload: 12 patients/week
* Activity scaling factor: 0.85
* Exposure period 1:

  * Uptake
  * Start after administration: 0.25 h
  * Duration: 0.75 h
  * Presence factor: 1.0
* Exposure period 2:

  * Imaging
  * Start after administration: 1.0 h
  * Duration: 0.4 h
  * Presence factor: 0.6
* Source position:

  * 1.5 m from West wall
  * 3.5 m from South wall
  * 1.0 m AFFL

## Physics/provenance checks

* Ga-68 radionuclide selection: PASS
* Half-life displayed: 1.1285 h
* Patient dose-rate constant displayed: 0.085 µSv·h⁻¹·MBq⁻¹ at 1 m
* Approved radionuclide dataset provenance displayed: PASS
* Approved 511 keV attenuation dataset provenance displayed: PASS
* PET physics contract version displayed: PASS
* PET solver contract version displayed: PASS
* Deterministic replay verified: Yes

## Numerical behaviour observed

The decay-integrated weekly dose at 1 m was approximately:

**82.005 µSv/week**

Observed inverse-square barrier response was consistent with the source position, including approximately:

* 1.0 m → 82.005 µSv/week
* 1.5 m → 36.447 µSv/week
* 2.5 m → 13.121 µSv/week
* 3.5 m → 6.694 µSv/week
* 2.6 m → 12.131 µSv/week

## Checks completed

* Ga-68 decay integration: PASS
* Activity/workload scaling: PASS
* Presence-factor handling: PASS
* Asymmetric source-position geometry: PASS
* Source-to-barrier distance calculation: PASS
* Inverse-square dose response: PASS
* Wall/floor/ceiling barrier calculations: PASS
* Required shielding calculation: PASS
* PASS/FAIL behaviour: PASS
* Read-only barrier-results preview: PASS
* Read-only PET report preview: PASS
* Provenance consistency: PASS
* Deterministic replay: PASS
* Independent radionuclide behaviour relative to F-18: PASS
* Issueable output remains blocked: PASS

## Result

**PASS — PET Flight Test 02 complete.**

The Ga-68 workflow independently demonstrated correct radionuclide-specific decay integration, source-position response, barrier calculations, provenance and deterministic replay.

Together with PET Flight Test 01, this provides interactive validation of the current non-production PET calculation component for both F-18 and Ga-68.

This result does not constitute production approval or enable issueable PDF, CSV/JSON, certification or normal report generation.
