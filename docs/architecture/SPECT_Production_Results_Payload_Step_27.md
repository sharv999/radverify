# SPECT Production Results Payload — Step 27

Date: 2026-08-23  
Scope: in-app Results payload/presentation only.

## Decision

Step 27 opens the ordinary in-app Results surface to successful Step 26 SPECT
production calculations. It does not open PDF/report generation, machine-readable
export, or certification.

The Step 26 result contract is not rewritten. `results_integration_enabled=False`
remains a historical Step 26 boundary. Step 27 is a separate adapter that consumes
only a successful Step 26 production result and converts it to the established
live Results-row vocabulary.

## Calculation chain

`Step 23 working state -> room barriers -> Step 26 production dispatch -> Step 25 policy decisions -> Step 27 Results payload`

Step 27 performs no shielding physics. PASS/FAIL is taken from the approved Step 25
production policy decision. When Step 25 says a modeled provided-transmission dose
is not production-reportable, Step 27 stores `transmitted_dose_uSv_per_week=None`
rather than presenting the ultralow modeled value as evidence.

## Open surfaces

- in-app Results text/payload: OPEN
- production calculation dispatch: OPEN via Step 26 only

## Closed surfaces

- PDF/report payload generation: CLOSED
- JSON/CSV output generation: CLOSED
- certification: CLOSED
- normal desktop SPECT source/export path: BLOCKED by Step 22

## Production invariant

A Step 27 Results payload may only be created from a successful Step 26 production
wrapper. A request that requires Step 25 geometry-specific review fails before any
Step 27 production Results payload exists.
