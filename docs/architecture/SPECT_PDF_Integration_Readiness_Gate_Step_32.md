# SPECT Step 32 — PDF Integration Readiness Gate

Date: 2026-08-23

## Scope

Step 32 is an audit/gate increment only. It does **not** enable issued SPECT
PDF generation, `reports/output_pipeline.py`, machine-readable export,
certification, signatures, or report routing.

## Frozen prerequisites

The gate verifies that the report preparation chain remains frozen:

1. **Step 28** — 30-field SPECT Results allowlist remains
   `SPECT_REPORT_INTEGRATION_OPEN = False`.
2. **Step 29** — source-summary and barrier report-payload harnesses remain
   non-issueable.
3. **Step 30** — report section/view-model wording boundary remains frozen and
   non-issueable.
4. **Step 31** — plain-text preview remains deterministic, pure, and
   disconnected from issueable output paths.

These prerequisites establish that a future PDF adapter has a stable upstream
contract. They do not make the current PDF pipeline safe to consume SPECT.

## Step 32 decision

Current decision:

- Validated report foundations: **YES**
- PDF integration switch enabled: **NO**
- PDF integration ready: **NO**
- Issued SPECT PDF: **NO**
- Machine export: **NO**
- Certification/signature: **NO**

The explicit gate remains fail-closed via
`require_spect_pdf_integration_enabled()`.

## Existing hard output boundary

Step 22 remains authoritative for the normal application output path.
Persisted SPECT project state continues to block normal PDF/CSV/certification.
Step 32 does not weaken or bypass that gate.

## Why the gate remains closed

The next safe increment is a dedicated **non-issueable PDF preview adapter**.
That adapter must:

- consume only the frozen Step 30 view-model;
- preserve Step 25 `Not reported` semantics;
- carry unmistakable non-issueable watermark/wording;
- be isolated from the normal report payload and certification paths;
- be regression-tested for deterministic content and layout boundary;
- remain incapable of machine export or signature/certification.

Only after that adapter is proven should a later step consider opening any
SPECT PDF integration switch.

## Step 32 conclusion

**NO-GO for issued SPECT PDF integration.**

The report foundations are ready for a controlled non-issueable PDF preview
experiment, but the application PDF/output pipeline remains closed.
