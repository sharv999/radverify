# SPECT Step 30 — Report section/view-model and wording freeze

Step 30 freezes deterministic, presentation-ready SPECT report-section data without opening document generation.

## Frozen wording boundary

The view model uses the headings `SPECT shielding assessment — non-issueable preview`, `Tc-99m source summary`, `SPECT barrier shielding results`, and `Calculation provenance`. It labels the Step 25 decision as **Assessment status**, not certification or regulatory compliance.

The mandatory warnings state that the payload is non-issueable, PDF/report/export/certification integration remains blocked, Step 25 engineering-review cases are excluded from automatic production results, and non-reportable transmitted-dose values are omitted.

## Closed integrations

No Step 30 module renders or writes a document. `reports/`, `reports/output_pipeline.py`, machine export, certification, and signatures remain disconnected. A later step must explicitly open any report-rendering path.
