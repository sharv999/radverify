# SPECT Canonical Practical Calculation Request / Replay — Step 21

> **Historical snapshot:** This document records the state at its named step. Current SPECT host/release status is defined by Step 35/36 release-gate documentation; older NO-GO or non-production wording below is intentionally preserved as historical evidence.


Date: 2026-08-23  
Scope: deterministic headless request/replay freeze only. SPECT remains non-production.

## Purpose

Step 21 freezes a reproducible calculation boundary around the Step 20 approved/frozen Tc-99m source and practical-transmission physics. It does not enable SPECT project persistence, production calculation dispatch, Results, or reports.

## Canonical request boundary

A request contains only:

- explicit non-production schema/version markers;
- the exact Step 20 physics freeze identity and pinned source/practical dataset provenance;
- validated Tc-99m source workload inputs;
- ordered named barrier requests accepted by the Step 5 schedule contract.

Unknown fields, unsupported schema/version values, production eligibility, or mismatched physics freeze metadata fail closed.

## Deterministic result boundary

Replay executes the canonical request twice through the existing Step 5 schedule using the strict Step 20 frozen practical dataset. The normalized result payload records:

- canonical request SHA-256;
- exact Step 20 physics freeze metadata;
- source physics result;
- ordered practical barrier schedule;
- PASS/FAIL/NOT_ASSESSED counts;
- room-scatter and extrapolation flags;
- `replay_verified: true`.

The regression manifest hashes the complete result payload after platform-stable finite-float quantization to nine decimal places. This avoids false cross-platform digest changes from final floating-point bits while remaining far more precise than the UI display.

## Frozen regression fixtures

1. `spect-tc99m-standard-two-barrier-v1` — lead + normal-weight concrete.
2. `spect-tc99m-low-transmission-caution-v1` — lead + gypsum and an explicit room-scatter caution.

The manifest pins fixture identity, request path, material order, canonical output SHA-256, deterministic replay status, and the Step 20 freeze ID.

## Production boundary

Step 21 does **not** change the Step 19 NO-GO decision. Specifically:

- `SPECT` remains absent from production modalities;
- `spect_patient` remains calculation-blocked in the desktop workflow;
- the request/replay boundary is not imported by normal project serialization;
- Results and reports do not consume Step 21 artifacts;
- the low-transmission production policy remains unresolved.

The next production-readiness increment should address the explicit source-readiness/export blocker identified by Step 19 before opening any production persistence or dispatch path.
