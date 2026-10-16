# PET/SPECT Step 41 — Production Report Qualification

Status: **QUALIFIED / OUTPUT STILL CLOSED**

Step 41 qualifies the already-integrated PET/SPECT report-facing path without enabling issued output.

Qualification evidence is locked by regression tests for both modalities:

- working-project save → reopen → deterministic production Results replay;
- equality of post-reopen canonical Results with the Step 39/40 report-adapter result payload;
- representative known-answer PET and SPECT barrier cases;
- ReportLab rendering of the canonical preliminary report payload with content extraction/visual-structure checks;
- explicit confirmation that normal PDF export, machine export, certification, and signatures remain closed.

## Representative frozen qualification cases

PET: F-18, 250 MBq, 10 patients/week, one-hour uptake exposure, North wall at 4 m, T=0.25, P=20 µSv/week, 5 mm Pb.

SPECT: Tc-99m, 600 MBq, 20 patients/week, 0.5 h imaging interval, North wall at 3 m, T=0.25, P=10 µSv/week, 1 mm Pb.

These cases are qualification regression fixtures, not universal design defaults.

## Decision

**GO:** production report qualification for the current PET/SPECT canonical Results → report-payload boundary.

**NO-GO:** issued PDF, machine export, certification, and signatures. Opening any of those requires a separate explicit production-output enablement gate.
