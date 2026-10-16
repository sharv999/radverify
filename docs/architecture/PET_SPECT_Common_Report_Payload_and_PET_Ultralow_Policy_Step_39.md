# Step 39 — Common PET/SPECT report payload + PET ultralow-transmission policy

## Scope

Step 39 closes two blockers identified by the Step 38 production-output readiness audit without enabling issued output.

1. A **common PET/SPECT report-payload adapter** now consumes only the frozen modality source-summary and canonical in-app Results report contracts.
2. PET now has an **approved, locked ultralow-transmission report-acceptance policy**.

The normal report builder, issued PDF, machine export, certification, and signature routes remain closed for PET/SPECT.

## PET ultralow-transmission policy

RadShield freezes `B = 0.01` as the current PET automatic issueable-acceptance boundary.

- Required transmission `B <= 0.01`: **PHYSICIST_REVIEW_REQUIRED**; automatic issueable acceptance is blocked.
- Required transmission `B > 0.01`: provided thickness may be assessed against required thickness.
- If the provided barrier model predicts transmission `<= 0.01`, the thickness comparison may remain valid, but the numerical ultralow transmitted-dose value is **not reportable as issueable acceptance evidence**.

This threshold is a **RadShield software-validation/reporting boundary**, not a claim that AAPM TG-108 establishes a physical 1% validity limit. The current approved PET attenuation dataset is a reduced piecewise-TVL representation of TG-108 broad-beam 511 keV transmission information, so the application deliberately fails closed before relying on deeper extrapolation for automated issueable conclusions.

## Common report-payload boundary

`services/pet_spect_report_payload_adapter.py` accepts:

- modality (`PET` or `SPECT`);
- a source summary satisfying the frozen modality source-summary contract;
- canonical modality Results rows satisfying the frozen report-readiness contract.

It performs **no shielding calculation** and has no dependency on:

- `engine.shielding_engine`;
- generic report barrier recalculation;
- `app.py`;
- normal report/PDF routing;
- export;
- certification;
- signatures.

For PET, the locked Step 39 policy is applied before data crosses the common report-facing boundary. Review-required barriers fail closed. Non-reportable ultralow transmitted-dose values are suppressed.

For SPECT, the adapter preserves the already-approved Step 25 policy identity and transmitted-dose reportability semantics.

## Output status after Step 39

| Boundary | PET | SPECT |
|---|---|---|
| Production-host calculation | Enabled | Enabled |
| Durable working state | Enabled | Enabled |
| In-app Results | Enabled | Enabled |
| Common non-issueable report payload | Ready | Ready |
| Issued PDF | **Closed** | **Closed** |
| Machine export | **Closed** | **Closed** |
| Certification/signatures | **Closed** | **Closed** |

## Remaining blocker

The Step 38 finding about the ordinary report pipeline remains valid: `reports/results_payload_builder.py` still uses the generic shielding-engine path and `reports/barrier_schedule.py` still contains generic recalculation fallbacks.

The next boundary should therefore wire the Step 39 common adapter into the normal report payload builder through an explicit modality-neutral, fail-closed route. That integration must still leave issued PDF/export/certification switches closed until replay, payload-equivalence, and visual report validation are complete.
