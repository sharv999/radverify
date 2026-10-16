# SPECT Report-Readiness Boundary Audit — Step 28

## Purpose

This audit freezes the exact Step 27 SPECT Results fields that may cross into a **future** report-payload adapter. It does **not** open SPECT PDF/report generation, CSV/JSON export, certification, signature, or issueable-output generation.

The machine-readable audit boundary is implemented in:

```text
services/spect_report_readiness_contract.py
```

Contract identity:

```text
SPECT_REPORT_READINESS_CONTRACT_VERSION = 1
SPECT_REPORT_READINESS_BASELINE = "spect-report-readiness-v1-closed"
SPECT_REPORT_INTEGRATION_OPEN = False
```

## Current boundary status

The following are now open:

- Step 20 approved/frozen Tc-99m source and practical-transmission physics;
- Step 21 canonical request and deterministic replay;
- Step 23 durable SPECT working-project source state;
- Step 26 isolated production calculation dispatch;
- Step 27 production in-app Results payload and presentation.

The following remain deliberately closed:

- `reports/results_payload_builder.py` SPECT integration;
- canonical report barrier-schedule integration for SPECT;
- PDF generation;
- CSV/JSON machine-readable output;
- certification/signature;
- issueable final SPECT report generation.

The Step 22 source-readiness/output blocker remains the controlling output gate.

## Exact permitted Step 27 Results fields

A future report adapter may consume only these 30 fields from each canonical Step 27 SPECT Results row, in this order.

### Result identity

1. `results_model_contract_version`
2. `results_source`
3. `source_type`
4. `barrier_name`
5. `barrier_id`
6. `solver_mode`
7. `material`
8. `material_key`

### Barrier inputs and calculated/assessed results

9. `distance_m`
10. `occupancy_factor`
11. `design_goal_uSv_per_week`
12. `unshielded_weekly_dose_uSv`
13. `occupied_unshielded_weekly_dose_uSv`
14. `barrier_transmission_factor_B`
15. `required_thickness_mm`
16. `provided_thickness_mm`
17. `provided_transmission`
18. `transmitted_dose_uSv_per_week`
19. `transmitted_dose_reportable`
20. `compliance_status`
21. `margin_mm`
22. `calculation_reasoning`

### Production-policy and provenance integrity

23. `production_eligible`
24. `request_sha256`
25. `physics_freeze`
26. `policy_version`
27. `policy_status`
28. `policy_decision_basis`
29. `practical_record_id`
30. `practical_provenance`

All 30 fields are required for the first SPECT report adapter. Missing fields must fail closed.

## Fields prohibited from direct report transfer

The following current Results fields must not be copied directly into report content:

- `results_presentation_contract_version`
- `results_presentation_baseline`
- `required_lead_mm`
- `required_concrete_mm`
- `source_contributions`
- `dominant_source`
- `notes`
- `output_eligible`
- `report_integration_enabled`
- `certification_enabled`

The presentation fields and convenience aliases belong to the desktop Results view. The `notes` value explicitly says the payload is in-app only. The three output/certification flags are **closed-gate controls**, not report narrative, and must remain `False` throughout Step 28.

## Low-transmission reporting rule

Step 25 is part of the report boundary, not merely a calculation detail.

A future report adapter must:

- use Step 25 `compliance_status` as the production assessment status;
- preserve `transmitted_dose_reportable`;
- omit/suppress `transmitted_dose_uSv_per_week` whenever `transmitted_dose_reportable` is `False`;
- never reconstruct or estimate an ultralow transmitted dose from `provided_transmission`;
- fail closed if Step 26 refused automatic production dispatch because geometry-specific review was required.

Thus a future report may state that provided thickness meets the supported required-thickness criterion when Step 25 permits that conclusion, but it must not claim an ultralow total room dose unsupported by the one-dimensional model.

## Source-level information not available from Results rows

The barrier Results rows do not contain the complete source narrative required for a report. A separate validated SPECT source-summary adapter is still required for:

- radionuclide;
- administered activity (MBq);
- patients per week;
- imaging duration (h);
- saved source X position in the room;
- saved source Y position in the room.

These values must come from validated Step 23 working state and normal saved room geometry. Report code must not infer them from preview state, UI text, barrier names, calculation reasoning, or `.spectpreview.json` files.

## Provenance requirements still to be frozen for reporting

The Step 27 Results row contains `request_sha256`, `physics_freeze`, Step 25 policy identity, and practical-record provenance. Before report integration opens, a dedicated report adapter must freeze the exact report-facing representation of those nested provenance objects rather than allowing arbitrary dictionary transfer into an issueable payload.

The report adapter must also verify that:

- `results_source == "spect_step26_production_dispatch"`;
- `source_type == "spect_patient"`;
- `production_eligible is True`;
- the Step 20 physics freeze matches the installed approved freeze;
- Step 25 policy status/version match the approved production policy;
- the request SHA-256 is present and valid;
- the number and identity of Results rows match the room barrier inventory;
- every transmitted dose shown in the report is explicitly reportable under Step 25.

## Openings, sub-barriers, and geometry

Step 27 production Results currently map the room barrier inventory used by the Step 26 production adapter. Step 28 does not authorize report code to invent SPECT opening/sub-barrier calculations or to infer shielding for an opening that is not represented by a canonical production Results row.

Room layout graphics may later use normal saved `RoomGeometry`, but preview-only SPECT geometry must never cross into an issueable report.

## Verification of closed output boundaries

At Step 28 completion:

- no module under `reports/` imports `spect_results_model`;
- no module under `reports/` imports `spect_results_presentation_contract`;
- no module under `reports/` imports `spect_report_readiness_contract`;
- `reports/results_payload_builder.py` has no SPECT Results adapter integration;
- the Step 22 SPECT source-readiness/output blocker remains active;
- PDF/CSV/certification remain unavailable for persisted SPECT working state;
- Step 28 introduces no report-generation code.

## Audit conclusion

**NO-GO for opening SPECT PDF/report generation in Step 28.**

The Step 27 calculation/Results boundary is suitable to freeze as the input to a future report adapter, but report integration still requires a separate source-summary contract and an isolated non-issueable report-payload harness with frozen provenance mapping and known-answer snapshots.

## Recommended next step

Implement **SPECT Step 29 — non-issueable report-payload adapter harness**. It should map only the 30 permitted Results fields plus a separately validated source-summary contract into an isolated payload fixture. Do not connect it to `reports/output_pipeline.py`, PDF rendering, CSV/JSON export, certification, or issueable output until that payload contract is reviewed and frozen.
