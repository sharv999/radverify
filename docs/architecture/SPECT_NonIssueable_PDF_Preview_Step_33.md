# SPECT Step 33 - isolated non-issueable PDF preview

Date: 2026-08-23
Scope: PDF preview rendering only. No issued-report, export or certification enablement.

## Decision

Step 33 adds an isolated ReportLab renderer downstream of the frozen Step 30/31 report-preview boundary. The renderer returns **in-memory PDF bytes** only and is explicitly **NON-ISSUEABLE**.

The Step 32 PDF integration switch remains closed. Step 33 does not connect SPECT to issued-report routing.

## Frozen boundary

Input is the validated Step 30 report section/view-model. Step 33 additionally invokes the frozen Step 31 plain-text preview validator so malformed, drifted, multiline, or issueable content cannot bypass the prior preview boundary.

The PDF preview contains:

- prominent NON-ISSUEABLE header, warning block, watermark and footer;
- Tc-99m source summary;
- per-barrier assessment details;
- Step 25 `Not reported` behavior where transmitted dose is not production-reportable;
- calculation provenance;
- deterministic Step 33 preview contract metadata.

The renderer returns a frozen wrapper with:

- `non_issueable = true`;
- `output_eligible = false`;
- `issued_pdf_enabled = false`;
- `certification_enabled = false`.

## Explicitly still closed

Step 33 does not modify or integrate with:

- the normal PDF output pipeline;
- machine-readable export;
- report certification or signatures;
- issued-report routing;
- normal SPECT export eligibility.

**Step 22 remains authoritative** for normal SPECT PDF/export blocking. The presence of an isolated preview PDF renderer does not make an issued SPECT PDF permissible.

## Readiness outcome

The Step 28-33 chain can now be visually inspected as a real PDF without opening the issueable report boundary. The next step should be an explicit issued-PDF integration audit/gate; it must not infer permission merely from the existence of this preview renderer.
