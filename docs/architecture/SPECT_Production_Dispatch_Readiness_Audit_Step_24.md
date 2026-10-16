# SPECT Step 24 — Production-Dispatch Readiness Audit and Explicit Enablement Gate

> **Historical snapshot:** This document records the state at its named step. Current SPECT host/release status is defined by Step 35/36 release-gate documentation; older NO-GO or non-production wording below is intentionally preserved as historical evidence.


Date: 2026-08-23  
Scope: audit and fail-closed dispatch gate only. No production SPECT calculation entry point is enabled by this step.

## Decision

**NO-GO for production SPECT dispatch.**

Steps 20–23 now form a coherent and reproducible foundation:

1. **Step 20 physics freeze — PASS**  
   The Tc-99m source and practical-transmission datasets are approved/frozen and hash-verified.
2. **Step 21 canonical request/replay — PASS**  
   Two pinned practical calculation scenarios replay deterministically against the Step 20 freeze.
3. **Step 22 source/output blocker — PASS**  
   SPECT remains fail-closed for desktop calculations and all normal output paths.
4. **Step 23 working-project persistence — PASS**  
   Durable source/workload state can reconstruct the Step 21 canonical request without persisting preview-only geometry or opening production dispatch.

## Remaining production blocker

The practical transmission model intentionally marks target transmission at or below 1% as requiring room-scatter review. The current model still returns a calculated thickness in this region, and Step 21 freezes a regression case that demonstrates the caution path. No explicit production policy has yet been approved for this condition.

Before SPECT production dispatch can be enabled, a later step must define and test one of the following fail-closed policies (or another documented equivalent):

- hard-block calculations in the caution region;
- require an explicit qualified-physicist override/review state; or
- use a separately validated production model covering the low-transmission/room-scatter regime.

Step 24 therefore exposes an explicit gate with two independent closed conditions:

- `SPECT_LOW_TRANSMISSION_PRODUCTION_POLICY_APPROVED = False`
- `SPECT_PRODUCTION_DISPATCH_ENABLED = False`

The production registry remains unchanged and SPECT remains absent from `production_modality_names()`.

## Gate rule

Any future production SPECT calculation entry point must first call the Step 24 gate. The gate verifies the Step 20 physics freeze, Step 21 deterministic replay manifest, Step 22 fail-closed blocker, and Step 23 working-state/request reconstruction before considering production-specific conditions.

Step 24 itself never invokes the practical calculation engine through a production path.

## Next recommended increment

**Step 25 — low-transmission production policy + controlled dispatch enablement.**

That step should resolve the <=1% room-scatter caution policy first, update the gate regression tests, and only then deliberately enable one production calculation entry point. Results/report integration should remain later steps.
