# SPECT Production Readiness — Step 22 Source-Readiness / Export Blocker

Date: 2026-08-23

## Scope

Step 22 closes the fail-open source-readiness/export gap identified in the Step 19 audit.
It does **not** enable SPECT production persistence, calculation dispatch, Results integration,
or report generation.

## Closed gap

Before Step 22 the SPECT-owned source validator returned `BLOCKED`, but did not expose
`blocking=True` or an `errors` list. The room/project readiness aggregator therefore could
return `PASS` for a room whose only SPECT patient source was explicitly blocked.

Step 22 makes the SPECT contract self-contained and fail-closed:

- `overall_status = BLOCKED`
- `blocking = true`
- `output_blocking = true`
- canonical `errors` containing `SPECT_CALCULATION_BLOCK_REASON`
- a failed `SPECT production eligibility` check

The generic room aggregator also synthesizes a blocking error if any future modality returns
a blocking/fail status without supplying its own error text.

## Normal output boundary

`output_blocking=true` is stronger than ordinary incomplete-source blocking. While this flag
is present, the central export gate refuses:

- Draft PDF
- Final PDF
- CSV/JSON machine-readable output
- certification/signature

This preserves the existing policy for ordinary incomplete production inputs (for example a
CT draft with unresolved source data may still be allowed as an explicitly incomplete Draft
PDF), while SPECT remains entirely outside the normal output workflow.

## Production status after Step 22

SPECT remains **NON-PRODUCTION**.

Step 22 closes one audit blocker only. It does not change the modality registry, normal project
schema, shielding-engine production dispatch, Results integration, or report integration.
