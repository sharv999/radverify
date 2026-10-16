# SPECT Step 37 — Architecture Completion for Current Production-Host Scope

**Status:** COMPLETE
**Scope:** SPECT working-project persistence + gated production calculation + in-app Results.
**Issued PDF, machine export, certification, and signatures remain outside this completed scope.**

## Completion decision

SPECT is formally considered **architecturally complete for the current production-host scope**.

This closes the architecture sequence that established:

- registry-driven SPECT room hosting;
- approved and frozen Tc-99m physics inputs;
- deterministic canonical request/replay;
- fail-closed source/output readiness;
- durable working-project persistence;
- approved low-transmission production policy;
- gated production calculation dispatch;
- in-app production Results;
- non-issueable report payload, text preview, and PDF preview boundaries;
- controlled host integration without SPECT-specific branching in `app.py`;
- historical wording/schema cleanup.

## Frozen completion boundary

The completed product surface is:

> **SPECT working-project persistence + gated production calculation + in-app Results.**

The following are explicitly **not** included in this completion declaration:

- issued/final SPECT PDF routing;
- machine-readable SPECT export;
- certification or signature workflows;
- use of the Step 33 preview PDF as an issueable document.

Opening any of those surfaces requires a separate future release-gate decision and must not be inferred from Step 37.

## Completion invariants

Step 37 remains valid only while all of the following remain true:

1. Step 35/36 controlled production-host release is `GO`.
2. SPECT remains admitted through the production modality registry.
3. Durable working state remains `radshield_spect_working_source_v2`.
4. Step 36 cleanup debt remains empty.
5. Issued PDF/export/certification remain closed.

The machine-readable gate is:

```text
services.spect_architecture_completion
```

and the CLI check is:

```text
python -m tools.spect_architecture_completion
```

## Maintenance rule

Future SPECT work should be treated as a **new scope expansion**, not continuation of the current architecture build. Any change that opens issued output, expands radionuclide/material scope, changes the low-transmission policy, or bypasses the frozen production dispatch/results contracts requires its own explicit readiness gate.
