# SPECT Step 35 — Final Release-Gate / Cleanup Audit

**Date:** 2026-08-24
**Scope:** controlled SPECT production-host release audit only.
**Issued PDF, machine export and certification remain closed.**

## Executive decision

**GO — controlled production-host scope**

The Step 35 audit finds the SPECT path ready for the production-host scope already opened in Step 34:

- normal registry-driven SPECT room hosting;
- durable Step 23 working-project source state;
- frozen/gated Step 26 production calculation dispatch;
- Step 27 in-app production Results;
- Step 25 low-transmission policy enforcement.

**NO-GO — issued-output scope**

The following remain intentionally disabled:

- issued/final SPECT PDF routing;
- machine-readable SPECT export;
- certification/signature;
- use of the Step 33 PDF preview as an issueable document.

This split decision is deliberate. Step 35 does not widen the product surface.

## Release checks

1. **Production registry — PASS**
   `SPECT` is a production-host modality and owns the locked `spect_patient` source.

2. **Host orchestration — PASS**
   `app.py` remains registry-driven. No SPECT-specific room-admission branch is required.

3. **Working-project persistence — PASS**
   Step 23 durable working state remains schema v1 and is validated on load.

4. **Production calculation — PASS**
   Step 20 frozen physics, Step 21 replay, Step 24 readiness, Step 25 policy and Step 26 dispatch align.

5. **In-app Results — PASS**
   Step 27 remains the production Results boundary; its output is not an issued-report payload.

6. **Low-transmission policy — PASS**
   Required transmission at or below 0.01 remains fail-closed for automatic production assessment and requires geometry-specific review.

7. **Legacy generic calculator — CLOSED / PASS**
   `spect_patient` is still blocked from the generic source calculator. Step 26 remains the only production SPECT calculation path.

8. **Issued output — CLOSED / PASS**
   `output_blocking=True` continues to deny normal PDF, CSV/machine export and certification.

9. **Step 33 PDF preview — NON-ISSUEABLE / PASS**
   The isolated PDF renderer remains preview-only and output-ineligible.

## Cleanup debt

The audit records the following **non-blocking** cleanup debt:

- `modalities/spect.py` still contains historical module/report wording such as “non-production”, “coming-soon”, and “desktop calculations remain blocked”.
- `serialization/spect_working_project_state.py` retains historical `production_eligible=False` / `calculation_dispatch_enabled=False` flags in the durable-input envelope. These flags describe the envelope itself, not current host eligibility.
- Earlier architecture documents are intentionally historical and should not be interpreted as current registry state.

These items should be cleaned only when a later step owns the relevant wording/schema migration. They are not a reason to reopen or weaken the issued-output gates.

## Release boundary

The approved Step 35 release scope is:

> **SPECT working-project persistence + gated production calculation + in-app Results.**

It is **not** approval for an issued shielding report or certificate.

## Exit criteria

Step 35 is complete when:

- all release-gate checks pass;
- `python -m tools.spect_release_gate` reports controlled-host `GO`;
- issued-output release remains `NO-GO`;
- the full regression suite remains green on the Windows development environment.
