# SPECT Physics Dataset Approval / Freeze — Step 20

> **Historical snapshot:** This document records the state at its named step. Current SPECT host/release status is defined by Step 35/36 release-gate documentation; older NO-GO or non-production wording below is intentionally preserved as historical evidence.


Date: 2026-08-23  
Scope: physics-input approval and freeze only. SPECT remains non-production.

## Decision

The Tc-99m source physics dataset and the Tc-99m practical broad-beam transmission dataset are accepted as the frozen physics inputs for the existing non-production SPECT headless/preview calculation stack.

This approval does **not** enable SPECT in normal project creation, production calculation dispatch, Results, or reports.

## Tc-99m source model

The frozen source dataset is:

- `data/spect/spect_radionuclide_physics_approved_frozen.json`
- dataset ID `spect-radionuclide-physics-tc99m-source-model`
- revision `2026-08-23-step20-1`
- status `physics_approved_frozen_nonproduction`

The retained half-life is 6.0067 h.

The retained point-source dose-rate constant is 0.0206 µSv·h⁻¹·MBq⁻¹ at 1 m.

### Independent source check

Oumano et al. (2025), Table 4, citing Smith & Stabin (2012), reports for Tc-99m:

- gamma/exposure constant: 0.795 R·mCi⁻¹·h⁻¹ at 1 cm;
- f-factor: 0.959 cGy/R.

Conversion:

`0.795 × 0.959 × 10000 / 100^2 / 37 = 0.0206055`

giving 0.0206055 µGy·h⁻¹·MBq⁻¹ at 1 m, rounded to 0.0206. For photons, radiation weighting factor is 1, so the numerical value is used as 0.0206 µSv·h⁻¹·MBq⁻¹ in the current point-source shielding model.

This is an **unattenuated point-source constant**. It is not represented as a measured patient dose-rate constant and does not embed patient self-attenuation.

Primary shielding reference:

Oumano M, Wendt R, Botti J, et al. *Shielding resources for four common radiopharmaceuticals utilized for imaging and therapy: Tc-99m, F-18, I-131, and Lu-177.* J Appl Clin Med Phys. 2025;26:e70084. DOI 10.1002/acm2.70084.

Half-life basis remains consistent with evaluated Tc-99m decay data (6.0067 h).

## Practical transmission model

The frozen practical dataset is:

- `data/spect/spect_tc99m_practical_transmission_approved_frozen.json`
- dataset ID `spect-tc99m-practical-transmission-oumano-2025-frozen`
- revision `2026-08-23-step20-1`
- status `physics_approved_frozen_nonproduction`

The Tc-99m Archer parameters were checked against Oumano et al. Table 2 and the published fractional layers against Table 3.

The existing scope limits remain part of the frozen contract:

- room-scatter caution threshold: transmission <= 0.01;
- source-model minimum simulated transmission: 0.001;
- values below 0.001 remain extrapolations and are **not** production acceptance results.

The Step 19 recommendation to define a production hard-block/review policy for these low-transmission regions therefore remains open.

## Narrow-beam attenuation reference

`spect_tc99m_attenuation_development.json` is intentionally **not promoted** by Step 20. It remains a NIST XCOM narrow-beam reference dataset and is not the practical SPECT shielding model.

## Freeze controls

`data/spect/spect_physics_approval_manifest.json` pins:

- approved dataset identities;
- revisions;
- records SHA-256 digests;
- whole-file SHA-256 digests;
- explicit `production_enabled=false`.

The strict loaders also pin dataset identity, revision, approval state, and records digest. An edited and re-hashed copy therefore cannot become the accepted Step 20 input merely by being internally self-consistent.

Verification command:

`python -m tools.spect_physics_dataset_approval`

A successful result must report both active datasets as `APPROVED / LOCKED / VERIFIED` and `SPECT production enabled: NO`.

## Remaining production blockers

Step 20 closes the Step 19 physics-dataset approval/freeze blocker only. It does not close:

1. low-transmission production acceptance policy;
2. canonical practical SPECT request/replay freeze;
3. source-readiness/export fail-closed gap;
4. production working-project persistence;
5. production calculation dispatch;
6. Results integration;
7. report integration.

The next recommended increment is **SPECT Step 21 — canonical practical calculation request and replay manifest**.
