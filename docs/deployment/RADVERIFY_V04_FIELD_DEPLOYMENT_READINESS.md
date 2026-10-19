# RadVerify V0.4 — Field Deployment Readiness Audit

**Release checkpoint:** V0.4 Step 4, supervised field prototype only.

## Decision

A green automated audit is **not** field release approval. V0.4 may be considered for a **supervised pilot** only once all manual gates M01–M10 below are documented and accepted by the accountable medical physicist. Client-facing PDFs remain **DRAFT / NOT A COMPLIANCE CERTIFICATE**.

## Automated assessment

From the RadVerify project root on the **target Windows laptop**, with its intended Python interpreter active:

```powershell
python -m radverify.deployment --output ".\field_audits\radverify_field_readiness_audit.md"
```

Create `field_audits` first (`New-Item -ItemType Directory -Force field_audits`) or use the supplied `RUN_FIELD_READINESS_AUDIT.bat` to create it and run the preflight. It produces a Markdown checklist and matching JSON result. Exit code **0** means automated tests passed **only**. Exit code **1** means an automated check failed. Both leave the manual release status **NOT CLEARED**.

Run the full RadVerify release-test set after applying the patch:

```powershell
python -m pytest -q tests/test_radverify_v01.py tests/test_radverify_v02_step1.py tests/test_radverify_v02_step2_radtwin.py tests/test_radverify_v03_step1_design_asbuilt.py tests/test_radverify_v03_step2_evidence.py tests/test_radverify_v03_step3_measurements.py tests/test_radverify_v03_step4_summary.py tests/test_radverify_v04_step1_reporting.py tests/test_radverify_v04_step2_packaging.py tests/test_radverify_v04_step3_restoration.py tests/test_radverify_v04_step4_field_readiness.py
```

The new automated probes A01–A08 cover runtime imports/Tcl, atomic native-project persistence, Digital Twin design/as-built isolation, portable package export + checksum + repeat restoration, and rejection of corrupted packages and unsupported project JSON. They operate on **synthetic** data only.

## Manual field acceptance record

| ID | Check on target field laptop | Pass / Fail / N/A | Evidence and operator initials |
|---|---|---|---|
| M01 | Launch `RUN_RADVERIFY.bat` without VS Code or an internet connection; inspect 100% and 125% display scaling | | |
| M02 | Edit and save; test Cancel/Save/Discard on close; simulate interrupted program on a **disposable** file; verify documented backup procedure | | |
| M03 | Survey a real asymmetric room; verify N/E/S/W wall directions, floor/ceiling, openings, room dimensions and source location | | |
| M04 | Capture real photos/documents; remove or alter a test evidence file to confirm warnings; protect confidential material | | |
| M05 | Verify instrument serial/ID, calibration currency, background subtraction, date/time and measurement history against field notes | | |
| M06 | Print or inspect the report PDF at A4 scale; check vector plan, units, clipping, legibility, completeness and DRAFT status | | |
| M07 | Export package to a second Windows machine, verify archive, restore twice, reopen evidence and re-export | | |
| M08 | Round-trip RadShield design → RadVerify inspection → RadShield reassessment; review shielding workload assumptions separately | | |
| M09 | Confirm security, folder backup, retention, incident response and provenance controls; ZIP manifest is unsigned | | |
| M10 | Obtain clinical/radiation-physics review, operational authorisation, acceptance record and procedure training | | |

## Known limits and residual risks

- **No periodic autosave or power-loss recovery.** Project saves are now atomic, protecting the prior saved file from partially written JSON. Changes made *since the last save* can still be lost in a crash. Set a field policy to save regularly, and use secure backups.
- **Not a standalone executable.** RadVerify currently requires a working Python/Tk installation and Python dependencies. The `.bat` launcher removes the need for VS Code, **not** the need for the runtime.
- **Evidence is stored in the field ZIP**, but may contain sensitive information. Use encrypted transfer/storage and check records for patient identifiers.
- **SHA-256 integrity does not authenticate the sender**; a complete forgery of archive + unsigned manifest is out of scope.
- **Measurements and observed Pass/Review/Fail states are recorded**, not independently verified against legal or clinical criteria by the software.
- **PDF is a draft**. It cannot be issued as a signed radiation shielding compliance certificate without documented professional review.
- No live RadStatus API is used; current interface is exported JSON only.
- All automated checks are based on synthetic data and do not replace controlled field acceptance.

## Release sign-off

Target device / OS / Python / RadVerify commit: __________________________________

Automated audit file and SHA-256: ______________________________________________

Evidence for any exceptions and risk acceptance: _________________________________

Field operator / date: _________________________________________________________

Accountable medical physicist / date: ___________________________________________

**Release decision:** [ ] NOT CLEARED  [ ] APPROVED FOR SUPERVISED PILOT  [ ] REJECTED
