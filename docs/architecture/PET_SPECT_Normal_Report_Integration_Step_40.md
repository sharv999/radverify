# PET/SPECT Step 40 — Normal Report Payload Integration

## Decision

**GO for non-issueable normal report-payload integration.**

**NO-GO for issued PDF, machine export, certification, and signatures.**

Step 40 connects the validated PET/SPECT production Results boundary to the normal report payload builder through the Step 39 common adapter. It does not enable a new output surface.

## Routing boundary

For PET and SPECT rooms, the normal report payload builder now:

1. identifies the modality through the common room-report route;
2. obtains the already-validated in-app production Results model;
3. builds the frozen PET or SPECT source summary;
4. passes both through the Step 39 common non-issueable adapter;
5. supplies only the adapter's audited `result_payload` rows to the canonical barrier schedule;
6. calls the schedule with generic fallback disabled.

CT retains the established generic shielding-engine route.

## Fail-closed behaviour

PET/SPECT report-payload construction fails closed when:

- canonical modality Results are missing;
- result count/order differs from the room barrier schedule;
- Step 39 policy or provenance validation fails;
- a PET ultralow-transmission case requires physicist review;
- PET/SPECT openings are present without a validated modality-specific opening Results contract;
- the common adapter exposes an issueable/export/certification surface;
- any barrier would require generic recalculation fallback.

There is no PET/SPECT fallback to `compute_room_barrier_table()` or `calc_barrier_result()`.

## Output state after Step 40

| Boundary | State |
|---|---|
| PET production calculation | Ready |
| SPECT production calculation | Ready |
| Normal PET/SPECT report payload | Ready, non-issueable |
| Generic PET/SPECT report recalculation | Disabled/fail-closed |
| Issued PDF | Closed |
| Machine export | Closed |
| Certification/signatures | Closed |

## Next boundary

Validate representative PET/SPECT save → reopen → deterministic replay, normal-payload equivalence against in-app Results, and visual report rendering. Issued PDF must remain a separate explicit enablement decision.
