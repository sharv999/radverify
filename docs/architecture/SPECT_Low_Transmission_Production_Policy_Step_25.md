# SPECT Step 25 — Low-transmission / room-scatter production policy

Date: 2026-08-23

## Decision

Step 25 resolves the Step 24 policy blocker but does **not** enable SPECT production dispatch.

For the approved Tc-99m practical Archer model, RadShield adopts a production boundary at a required transmission of 0.01 (1%). The source publication reports that ceiling/floor scatter becomes increasingly important as barrier transmission decreases and dominates below about 0.01, severely limiting the usefulness of additional barrier thickness for predicting total dose in that regime.

### Policy rules

1. **Required transmission <= 0.01:** automatic production sizing and automatic PASS/FAIL acceptance are prohibited. The barrier requires a geometry-specific medical-physics/scatter assessment outside this one-dimensional Archer workflow.
2. **Required transmission > 0.01:** required thickness may be used for automatic production assessment.
3. When provided shielding is present above this boundary, production PASS/FAIL is based on `provided_thickness_mm >= required_thickness_mm` rather than on an ultralow modeled transmitted-dose value.
4. If the provided barrier's modeled transmission itself falls to <=0.01, the low numerical transmitted-dose estimate is **not reportable as production evidence**. Extra thickness may establish that the provided barrier is at least as thick as the required barrier, but RadShield does not claim that the one-dimensional model predicts the total room dose below the scatter floor.
5. Any source-model extrapolation remains geometry-specific review required.

## Source basis

Michael Oumano et al., *Shielding resources for four common radiopharmaceuticals utilized for imaging and therapy: Tc-99m, F-18, I-131, and Lu-177*, Journal of Applied Clinical Medical Physics 26(5), e70084 (2025), DOI 10.1002/acm2.70084.

The paper reports broad-beam Monte Carlo/Archer transmission data and shows that floor/ceiling scatter increasingly contributes as transmission approaches 0.01 and dominates below that region. The authors state that this effect severely limits the ability to shield for transmission below 1% with the barrier-only model.

## Production boundary after Step 25

- Step 20 frozen physics: PASS
- Step 21 canonical replay: PASS
- Step 22 source/output blocker: PASS
- Step 23 durable working state: PASS
- Step 25 low-transmission production policy: **PASS / approved**
- Production dispatch switch: **OFF**
- SPECT production modality registry: **unchanged / closed**

Step 25 therefore removes the low-transmission policy blocker identified in Step 24 while deliberately leaving production dispatch disabled for a separate explicit enablement decision.
