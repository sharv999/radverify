> **Historical status note (Step 39):** The PET ultralow-transmission policy blocker identified below was resolved and frozen in Step 39. The normal report-builder/generic-recalculation blockers remain open.

# Step 38 — Combined PET/SPECT Production Output Readiness Audit

## Decision

This is an **audit-only** step. It does not enable PDF, export, certification, or signature routing.

- PET calculation production ready: **YES**
- SPECT calculation production ready: **YES**
- PET/SPECT ordinary issued-report payload ready: **NO**
- Issued PDF ready: **NO**
- Machine export ready: **NO**
- Certification ready: **NO**
- Production output enablement: **NO-GO**

The completed PET and SPECT production-host scopes remain valid: durable working-project persistence, gated production calculation, and in-app Results. Their existing non-issueable report contracts and preview renderers are also validated foundations.

## Hard blockers found

### 1. Normal report payload bypasses the PET/SPECT Results source of truth

`reports/results_payload_builder.py` still calls the generic `compute_room_barrier_table()` directly. The production UI Results path instead uses the validated PET and SPECT modality adapters through `app.get_room_results_model()`.

An issueable PET/SPECT report must not recalculate through the generic engine or maintain a second calculation path. The report payload must consume only the already-validated modality Results/report contracts.

### 2. Canonical report barrier schedule can fall back to generic recalculation

`reports/barrier_schedule.py` can fall back to `app.get_room_barrier_results(room)` and then `calc_barrier_result(...)` when a live row is absent. That behavior remains appropriate for the existing legacy/CT path, but it is not acceptable as a hidden PET/SPECT production-report fallback.

The future PET/SPECT output adapter must fail closed instead of silently recalculating through these generic paths.

### 3. PET ultralow-transmission acceptance policy is not yet explicit

SPECT has the approved Step 25 policy that blocks automatic acceptance when required transmission is <=1% and requires geometry-specific medical-physics review.

PET currently has approved/frozen attenuation data and replay-verified production calculation, but there is no explicit production policy boundary equivalent to SPECT Step 25 for interpretation of ultralow transmission results. Before an issueable PET shielding assessment can rely on those results, the project must explicitly decide whether such a policy is required and, if so, freeze it with tests and provenance.

### 4. Issued-output switches remain intentionally closed

Both PET and SPECT PDF integration gates remain disabled. Machine export, certification, and signatures also remain closed. This is the correct state at Step 38 and is not treated as a regression; those switches may only change after the report-data blockers above are resolved and the generated output is validated.

## Next boundary

**Step 39 — Common PET/SPECT issued-report payload adapter (still non-issueable).**

The adapter should:

1. consume only the validated PET/SPECT production Results and frozen source-summary/report contracts;
2. preserve every policy/provenance field needed for independent review;
3. fail closed on missing, mismatched, unsupported, or non-reportable data;
4. never fall back to the generic shielding calculation path;
5. remain non-issueable while the PET ultralow-transmission policy decision is resolved;
6. leave normal PDF, machine export, certification, and signatures closed.

Only after that adapter and the PET policy boundary are frozen should a later step consider enabling an issueable **Preliminary Radiation Shielding Assessment** PDF.
