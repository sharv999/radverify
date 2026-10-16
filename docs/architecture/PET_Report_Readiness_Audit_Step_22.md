# PET Report-Readiness Boundary Audit — Step 22

## Purpose

This audit defines the exact canonical PET Results fields that may cross into a future report payload. It does **not** open PET PDF, CSV/JSON, certification, report-payload, or issueable-output generation.

The frozen machine-readable boundary is implemented in:

```text
services/pet_report_readiness_contract.py
```

Contract identity:

```text
PET_REPORT_READINESS_CONTRACT_VERSION = 1
PET_REPORT_READINESS_BASELINE = "pet-report-readiness-v1-closed"
PET_REPORT_INTEGRATION_OPEN = False
```

## Current boundary status

The following are currently open:

- persisted PET source state in the normal working-project schema;
- canonical PET calculation dispatch from that persisted state;
- canonical PET barrier results in the normal in-app Results model.

The following remain closed:

- `reports/results_payload_builder.py` PET integration;
- canonical report barrier schedule integration;
- PDF generation;
- CSV/JSON machine-readable export;
- certification and signature;
- issueable final report generation.

The Step 17 persisted-PET readiness/export blocker remains the controlling issueability gate.

## Exact permitted canonical PET Results fields

A future report adapter may copy only the following fields from each canonical PET Results row, in this order:

### Result identity

1. `results_model_contract_version`
2. `results_source`
3. `source_type`
4. `barrier_name`
5. `solver_mode`
6. `material`

### Barrier calculation inputs and results

7. `distance_m`
8. `occupancy_factor`
9. `design_goal_uSv_per_week`
10. `unshielded_weekly_dose_uSv`
11. `occupied_unshielded_weekly_dose_uSv`
12. `barrier_transmission_factor_B`
13. `required_tvl_count`
14. `required_thickness_mm`
15. `provided_thickness_mm`
16. `provided_transmission`
17. `transmitted_dose_uSv_per_week`
18. `margin_mm`
19. `compliance_status`
20. `calculation_reasoning`

### Provenance and replay integrity

21. `provenance_manifest_id`
22. `provenance_manifest_revision`
23. `radionuclide_dataset_id`
24. `radionuclide_dataset_revision`
25. `radionuclide_records_sha256`
26. `attenuation_dataset_id`
27. `attenuation_dataset_revision`
28. `attenuation_records_sha256`
29. `physics_contract_version`
30. `solver_contract_version`
31. `replay_verified`

All 31 fields are required for the first PET report adapter. A partial row must fail closed rather than produce a weakly provenanced report schedule.

## Fields prohibited from direct report transfer

The following current Results fields must not be copied directly into a report payload:

- `results_presentation_contract_version`
- `results_presentation_baseline`
- `required_lead_mm`
- `required_concrete_mm`
- `source_contributions`
- `dominant_source`
- `notes`

Reasons:

- presentation-contract fields belong to the desktop UI, not the report schema;
- material-specific convenience aliases are redundant with `material` and `required_thickness_mm`;
- source/dominance strings are currently fixed display conveniences rather than a report-source contract;
- the current `notes` value contains the in-app-only warning and must not become report narrative.

## Source-level information not available from Results rows

The current canonical PET barrier Results rows do **not** contain the complete source narrative required for a report. A later, separate validated source-summary adapter must provide:

- radionuclide;
- administered activity per patient;
- patients per week;
- activity scaling factor;
- exposure-period names, start times, durations, and activity-retention factors;
- PET distance from West wall;
- PET distance from South wall;
- PET source height AFFL.

Report code must not infer these values from barrier results, calculation reasoning, UI text, or persisted JSON fragments.

## Error and fail-closed requirements

A future PET report adapter must fail closed when:

- any required Results field is missing;
- `results_source` is not `persisted_pet_single_source`;
- `source_type` is not `pet_patient`;
- deterministic replay is not verified;
- provenance manifest, radionuclide dataset, attenuation dataset, physics contract, or solver contract identity differs from the frozen production inputs;
- the number or names of PET result rows do not match the room barrier inventory;
- the Step 17 readiness/export blocker is still active.

No PET calculation error may silently fall back to CT results or an empty PASS schedule.

## Verification of closed output boundaries

At the completion of this audit:

- no module under `reports/` imports `pet_results_model`;
- no module under `reports/` imports `pet_results_presentation_contract`;
- no module under `reports/` imports `pet_report_readiness_contract`;
- the output pipeline still builds its payload through the existing production report path;
- persisted PET state still produces a blocking source-readiness result;
- machine export and certification remain unavailable.

## Recommended next step

Implement a **non-issueable PET report-payload adapter test harness** that maps only the 31 permitted fields into an isolated payload fixture. Do not connect that adapter to PDF, CSV/JSON, certification, or `reports/output_pipeline.py` until its schema and known-answer snapshots are reviewed and frozen.
