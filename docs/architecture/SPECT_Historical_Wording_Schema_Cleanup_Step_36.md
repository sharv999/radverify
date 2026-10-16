# SPECT Historical Wording / Schema Cleanup — Step 36

Step 36 is a cleanup-only increment following the Step 35 final release gate. It does not open a new product surface.

## Changes

1. Runtime wording in `modalities/spect.py` now describes the actual controlled production-host scope: durable working state, gated production calculation, and in-app Results are enabled; issued PDF/export/certification remain closed.
2. New durable SPECT working-state saves use schema v2 with explicit current-state flags:
   - `production_host_enabled = true`
   - `production_calculation_enabled = true`
   - `issued_output_enabled = false`
3. Legacy v1 working-state payloads remain readable and are migrated in memory to the current v2 representation when re-saved.
4. Earlier Step 19-24 architecture documents that contain historical NO-GO/non-production statements are explicitly marked as historical snapshots.
5. `SPECT_Current_Status_After_Step_36.md` is the authoritative current-status pointer.
6. The Step 35 cleanup-debt list is now empty.

## Release boundary

This cleanup does **not** enable issued SPECT PDF generation, machine export, certification, or signatures. Those boundaries remain closed exactly as established by Steps 22, 32, 33, 34, and 35.
