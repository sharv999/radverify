# SPECT Step 31 — Non-issueable plain-text report preview

## Decision

Step 31 adds a deterministic plain-text renderer for the frozen Step 30 SPECT report section view-model. It is a preview harness only and does not open PDF/report generation, machine export, certification, signatures, or issueable output.

## Input boundary

The renderer accepts only the Step 30 view-model contract. It does not accept Step 27 Results rows, Step 29 harness payloads, project models, or calculation requests directly. This preserves the sequence:

Step 27 production Results → Step 29 non-issueable payload → Step 30 frozen view-model → Step 31 text preview.

## Fail-closed rules

Rendering is rejected if the Step 30 contract version or baseline changes, the view-model is not explicitly non-issueable and closed, frozen headings/warnings/field ordering drift, barrier rows are absent or altered, provenance ordering changes, or multiline content enters the renderer.

## Output status

The returned value is an in-memory string only. It carries a prominent NON-ISSUEABLE PREVIEW header and footer. The renderer performs no file I/O and is not imported by reports, output-pipeline, export, or certification modules.

## Production boundary

Step 31 does not authorize or create an issued report. A later step must separately review and explicitly open PDF/report integration.
