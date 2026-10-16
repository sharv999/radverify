# PET Validation Status — AAPM TG-108

**Date:** 17 August 2026  
**Status:** VALIDATED — NON-PRODUCTION PET CALCULATION MODES  
**Regression baseline:** 604 passed, 3 skipped

## Validation summary

- **PET Imaging Room mode — validated against AAPM TG-108 Example 2**
- **PET Uptake Room mode — validated against AAPM TG-108 Example 5**

## PET Imaging Room mode

### Reference
AAPM Task Group 108, Example 2.

### Validation case
- Radionuclide: F-18
- Administered activity: 555 MBq/patient
- Patient workload: 40 patients/week
- Uptake time: 1.0 h
- Imaging time: 0.5 h
- Voiding factor: 0.85
- Barrier distance: 3.0 m

### Radshield result
- Unshielded weekly dose at 3.0 m: approximately **60.15 µSv/week**

AAPM TG-108 Example 2 reports approximately **59.7 µSv/week** using rounded intermediate decay factors. Radshield uses the exact exponential decay calculation, including decay from administration to imaging start and decay during the imaging interval.

### Result
**PASS — PET Imaging Room mode validated against AAPM TG-108 Example 2.**

## PET Uptake Room mode

### Reference
AAPM Task Group 108, Example 5.

### Validation case
- Radionuclide: F-18
- Administered activity: 555 MBq/patient
- Patient workload: 40 patients/week
- Uptake time: 1.0 h
- Barrier distance: 3.6 m
- Existing concrete: 100 mm
- Design goal: 20 µSv/week

### Radshield result
- Unshielded weekly dose at 3.6 m: **131.18 µSv/week**

AAPM TG-108 Example 5 reports approximately **131 µSv/week**.

### Result
**PASS — PET Uptake Room mode validated against AAPM TG-108 Example 5.**

## Physics model boundaries

### Imaging Room mode
The calculation sequence is:

1. Administered activity.
2. Physical decay through the uptake time to imaging start.
3. Application of the voiding factor.
4. Physical decay integrated over the imaging duration.
5. Source-to-barrier inverse-square scaling.
6. Occupancy, design-goal and shielding calculations.

The calculated decay factor is derived from radionuclide half-life and uptake time and is read-only.

### Uptake Room mode
The calculation sequence is:

1. Administered activity.
2. Physical decay integrated from administration through the uptake interval.
3. Source-to-barrier inverse-square scaling.
4. Occupancy, design-goal and shielding calculations.

Imaging time and voiding factor are not used in Uptake Room mode.

## Validation conclusion

The current PET calculation implementation has two independently validated room modes:

- **Imaging Room:** validated against AAPM TG-108 Example 2.
- **Uptake Room:** validated against AAPM TG-108 Example 5.

These validations support the numerical correctness of the current PET calculation paths for the tested F-18 cases. PET remains subject to the application's existing non-production report/export/certification boundaries until separately approved for production use.
