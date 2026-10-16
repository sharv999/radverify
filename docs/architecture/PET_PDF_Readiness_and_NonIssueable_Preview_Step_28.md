# PET Step 28 — PDF integration readiness + non-issueable PDF preview

## Decision

- Validated report foundations: **YES**
- PDF integration switch enabled: **NO**
- Production-host calculation and in-app Results: **YES**
- **NO-GO for issued PET PDF integration.**

Step 28 adds an isolated non-issueable PDF preview for the already-frozen PET report view-model. It returns deterministic in-memory PDF bytes only and does not write files or connect PET to normal report/output routing.

## Frozen foundations verified

The Step 28 readiness gate verifies that:

1. Step 27 production-host integration remains ready while issued output remains closed.
2. The 31-field PET Results report allowlist remains frozen.
3. The source-summary, barrier-payload and combined-envelope harnesses remain non-issueable.
4. The deterministic PET report section/view-model and plain-text preview remain frozen and disconnected.

## Isolated preview boundary

`services.pet_report_pdf_preview` consumes only the frozen PET report-section view model. Before rendering it re-validates that model through the existing plain-text preview boundary. The preview includes the PET source summary, exposure periods, barrier results and provenance, with explicit non-issueable warnings, watermarking and footer language.

The preview is intentionally:

- in-memory only;
- deterministic;
- non-issueable;
- output-ineligible;
- disconnected from `reports`, normal PDF routing, machine export, certification and signatures.

## Output boundary

Issued PDF, machine export, certification and signatures remain closed. The Step 28 readiness switch is deliberately `False`, and the explicit PDF integration gate fails closed.

Any future issued-PDF work requires a separate scoped change and must not infer permission from the existence of this preview renderer.
