# Step 42 — PET/SPECT Preliminary Shielding Assessment PDF enablement

## Decision

**GO for issueable Preliminary Shielding Assessment PDF for PET/SPECT-only projects.**

This is not a final/certified shielding report gate. Machine-readable exports,
certification and signatures remain closed.

## Preconditions

Step 42 authorizes PDF issuance only when:

- Step 41 production report qualification remains complete;
- every room is PET or SPECT and carries the Step 40 canonical report route;
- no room/report payload error exists;
- every assessed room and barrier is PASS (zero REVIEW and zero FAIL);
- payload calculation-integrity is non-blocking;
- no unexpected source-readiness blocker remains; and
- the request is not Final/Certified/Issued/Approved.

The authorization is applied after the normal Step 40/41 payload is built. This
preserves the non-issueable qualification boundary as a reproducible substrate.

## Enabled scope

- Normal ReportLab PDF generation: **ENABLED for Preliminary PET/SPECT**.
- Report status: **Preliminary — Issueable**.
- Final/certified PDF: **DISABLED**.
- JSON/CSV machine export: **DISABLED**.
- Certification: **DISABLED**.
- Signatures: **DISABLED**.

The generated document must state that it is a preliminary shielding assessment
and not a certificate of shielding compliance.
