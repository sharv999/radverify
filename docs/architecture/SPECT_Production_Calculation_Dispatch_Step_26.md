# SPECT Production Calculation Dispatch — Step 26

Date: 2026-08-23  
Scope: first isolated production-eligible SPECT calculation entry point only.

## Decision

Step 26 opens one headless production calculation entry point after the Step 20–25
controls are satisfied. It does **not** promote SPECT into the desktop production
modality registry and does not connect SPECT to Results, reports, PDF/CSV export,
or certification.

## Entry contract

`dispatch_spect_production_calculation(state, barrier_requests)` accepts:

- validated Step 23 `SpectWorkingProjectState`;
- validated ordered Step 5 barrier requests.

The Step 24 gate verifies the frozen physics/replay/persistence foundations and
the approved Step 25 low-transmission policy before execution.

The calculation uses the Step 20 frozen Tc-99m practical-transmission dataset and
the existing deterministic Step 5 calculation substrate. The returned Step 26
wrapper is `production_eligible=True`; the embedded historical Step 5 schedule
remains `production_eligible=False` to preserve its frozen contract.

## Low-transmission fail-closed rule

After calculation, the approved Step 25 policy is applied to every barrier. If
any barrier has required transmission <= 0.01 or otherwise requires
geometry-specific review, Step 26 raises
`SpectProductionPolicyReviewRequiredError`. No automatic production result is
returned for that request.

## Boundaries intentionally still closed

- `SPECT` remains absent from `production_modality_names()`.
- `spect_patient` desktop source readiness remains explicitly blocked.
- Step 22 normal output blocking remains active.
- Results integration remains disabled.
- Report integration remains disabled.
- PDF/CSV export and certification remain disabled.

Those are separate later production increments.
