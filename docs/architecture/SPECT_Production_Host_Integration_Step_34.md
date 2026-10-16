# SPECT Step 34 — Controlled Production Host Integration

## Decision

Step 34 enables SPECT as a normal **production host modality** for:

- room creation/retention through the modality registry;
- locked `spect_patient` source inventory;
- Step 23 durable working-project source state;
- Step 26 gated production calculation dispatch;
- Step 27 in-app Results.

This is intentionally **not** an issued-output enablement step.

## Host integration model

`app.py` remains modality-neutral. It already derives active room types and locked
source inventories from the modality registry, so SPECT enters the host by
changing the SPECT plugin's registry eligibility rather than adding SPECT-specific
branches to `app.py`.

The legacy generic source calculator remains blocked for `spect_patient`. All
production SPECT calculation must continue through the Step 26 dispatch boundary.

## Output boundary remains closed

Step 34 preserves the explicit hard gate on normal output:

- issued PDF: **closed**;
- machine-readable export: **closed**;
- certification/signature: **closed**;
- Step 33 PDF preview: **non-issueable and isolated**.

The SPECT source-readiness contract is therefore nonblocking for host
calculation/Results but retains `output_blocking=True` so normal output cannot be
reached accidentally.

## Definition of done

Step 34 is complete when SPECT is registry-selectable and preserved by the normal
host, Step 24/26 production calculation and Step 27 Results remain green, the
legacy generic source calculation route remains closed, and Step 32/33 issued
output gates remain closed.
