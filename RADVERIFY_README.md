# RadVerify — V0.3 Step 4 Room Verification Summary Prototype

RadVerify is a field-verification application built from the RadShield room/floor-plan foundation. V0.2 Step 2 introduces the shared **Radiation Room Digital Twin** interchange contract while retaining the V0.2 Step 1 floor-plan-centred workflow.

## Run

```powershell
python app.py
```

The original RadShield launcher from the supplied snapshot has been preserved as:

```text
radshield_app_reference.py
```


## V0.3 Step 4 — Room-level verification / compliance readiness summary

- **New Room Summary tab** — provides a derived room-level view across barriers, evidence and measurements.
- **Overall room state** — `Verified`, `Review required`, `Failed` or `Incomplete`, with Fail/Review outcomes kept distinct from missing data.
- **RadStatus readiness** — a separate data-completeness gate; a fully documented Review/Fail package can still be ready for RadStatus hand-off.
- **Barrier completeness** — counts Pass / Review / Fail / Not inspected / N/A and tracks whether as-built construction has been recorded.
- **Evidence completeness/integrity** — reports evidence coverage and linked-file integrity issues without treating reference-only evidence as missing.
- **Measurement completeness** — reports spatial points, readings, assessment status and current calibration count.
- **Outstanding-items register** — consolidated Fail / Review / Incomplete items identify exactly what needs attention.
- **Interchange + RadStatus** — the derived `verification_summary` is included in both the draft RadStatus payload and `*.radtwin.json` as optional informational metadata; source barrier/measurement records remain authoritative.
- **No automatic regulatory certification** — the dashboard is explicitly a workflow/readiness summary, not an independent compliance determination.

## V0.3 Step 3 — Measurement workflow upgrade

- **Spatial point vs measurement event** — a floor-plan point is a durable survey location; multiple dated measurement records can now be stored against it.
- **Instrument traceability** — make/model, asset ID, serial number, calibration date, due date and certificate/reference are captured and snapshotted into each measurement record.
- **Calibration status** — the UI reports Current / Expired / Not recorded / Invalid date against the measurement date.
- **Field conditions** — each reading can document source/room conditions independently of the point location.
- **Gross / background / corrected** — corrected dose rate is calculated automatically and the latest record remains mirrored into the legacy single-reading fields for backwards compatibility.
- **Measurement history** — add, edit and delete historical records without losing the spatial point; the main table shows latest result and history count.
- **Digital Twin + RadStatus persistence** — instrument metadata and full measurement history travel in both native RadVerify JSON and `*.radtwin.json`.

## V0.3 Step 2 — Evidence capture

- **Multiple evidence records per barrier/opening** — photos, drawings, documents, measurements and non-file references can be linked directly to the selected inspection item.
- **Field metadata** — each evidence item carries an ID, type, reference, inspection date, inspector and description.
- **Linked files** — RadVerify stores the source file path and can reopen the linked file from the inspection workspace. Files are referenced rather than embedded in the JSON at this prototype stage.
- **Integrity fingerprint** — attached files receive a SHA-256 hash at capture/edit time; the UI can re-check whether the linked file is unchanged, missing or modified.
- **Digital Twin persistence** — structured evidence travels in `barriers[*].verification.evidence` while the existing `evidence_ref` remains as a backwards-compatible primary reference.
- **RadStatus hand-off** — structured evidence metadata is also included in the draft RadStatus payload.


## V0.3 Step 1 — Design vs As-Built Barrier Inspection

- **Design is immutable reference data** — RadShield/Digital Twin design construction and Pb equivalence are shown read-only in RadVerify.
- **As-built is a separate field layer** — observed construction and Pb equivalence are entered independently without overwriting design intent.
- **Three-part inspection workspace** — selected barrier shows DESIGN, AS-BUILT and VERIFICATION panels together.
- **Difference visibility** — the barrier table and detail editor show whether the field observation matches or differs from the design, including Pb thickness delta when available.
- **Floor-plan workflow retained** — Open inspection from the Floor Plan now takes the user directly to the selected barrier in the Design vs As-Built workspace.
- **Interchange contract unchanged** — the existing `radiation-room-digital-twin-0.1` design/as-built/verification layers remain the persistence boundary.

## V0.2 Step 2 — Radiation Room Digital Twin

- **Portable room file** — File → Export Radiation Room Digital Twin… writes a neutral `*.radtwin.json` record.
- **Twin import** — File → Import Radiation Room Digital Twin… reconstructs a new unsaved RadVerify working project from the room twin.
- **Shared schema** — schema identifier `radiation-room-digital-twin-0.1` is documented and accompanied by a machine-readable JSON Schema and example twin under `docs/radtwin/`.
- **Stable coordinate convention** — south-west floor corner origin; +x west→east; +y south→north; +z upwards from FFL.
- **Design vs as-built separation** — every barrier carries distinct design specification, as-built construction and verification state.
- **RadShield compatibility contract** — `radverify.radtwin.radtwin_to_radshield_geometry()` maps the twin to the existing RadShield `RoomGeometry` JSON shape without invoking shielding physics.
- **Product separation retained** — native `*.radverify.json` remains the editable RadVerify project file; `*.radtwin.json` is only the shared interchange record.

## V0.2 Step 1 — Floor Plan workflow centre

- **Barrier selection from the plan** — click N/E/S/W walls, doors or viewing panels to select the linked Barrier Inspection record.
- **Direct inspection actions** — the Floor Plan sidebar shows the selected barrier and supports Open inspection, Pass, Review, Fail and Not inspected without leaving the plan.
- **Floor and ceiling selection** — click the Floor / Ceiling labels on the plan (or use the sidebar selectors) to keep non-planar barriers in the same workflow.
- **Bidirectional linkage** — selecting a barrier in the Barrier Inspection table highlights it on the Floor Plan, and vice versa.
- **Measurement placement mode** — select Place measurement point, then click inside the room to create a linked survey point and open its measurement record.
- **Measurement selection linkage** — clicking an existing measurement marker selects the corresponding Measurement Points record; the table can also return the selection to the Floor Plan.
- **Selection highlighting** — the active wall/opening/floor/ceiling/measurement is visibly highlighted on the plan.
- **Compact opening management** — openings remain editable from the Floor Plan via a dedicated Add opening dialog and linked opening list.

The persisted project schema remains `radverify-0.1`; V0.2 Step 1 changes interaction only, not the saved data contract.

## V0.1 scope

1. **Room Details** — project/site/room metadata and dimensions.
2. **Floor Plan** — reuses the RadShield `GeometryCanvas`; openings can be added/removed and inspection status is shown spatially.
3. **Barrier Inspection** — wall, floor, ceiling and opening records with expected/observed construction, Pb equivalence, evidence reference, notes and Pass/Review/Fail status.
4. **Measurement Points** — spatial survey points with coordinates, height, instrument, gross/background/corrected dose-rate readings and assessment status. Points can be placed directly from the Floor Plan.

## Persistence

Projects are saved as human-readable `*.radverify.json` files. The project schema is `radverify-0.1`.

Each saved project also contains a draft `radstatus_payload`, and the File menu provides **Export RadStatus payload…** as a clean future integration boundary.

## Deliberate V0.1 exclusions

- No shielding calculation is performed by RadVerify.
- No RadShield physics code is modified or invoked by the field-verification workflow.
- No report/PDF generation yet.
- Evidence files are linked rather than embedded or copied into a managed evidence package; packaging is a later step.
- RadStatus interface is a draft JSON payload only; no live API connection yet.

## V0.4 Step 1 - Draft field verification PDF

- **File > Export draft verification report (PDF)...** and **Export verification PDF...** in the top toolbar produce a multipage PDF report directly from the current RadVerify project (no intermediate RadShield calculation).
- Includes room identity, derived Room Summary, a **vector floor-plan schematic** showing named walls/openings, source location and measurement-point markers, barrier design/as-built schedule, notes, evidence register with on-demand file-integrity status, all measurement history and outstanding issues.
- Report is conspicuously marked **DRAFT - NOT A COMPLIANCE CERTIFICATE**. Recorded Pass/Review/Fail values are not independently assessed against regulatory limits. Uninspected/missing records are displayed rather than inferred as passing.
- Evidence files are referenced in the register **but not embedded**. Keep and transmit them separately. The full local path is not printed in the client PDF.
- PDF generation is independent of the Tk GUI in `radverify/reporting.py` and can be tested headlessly. A failed PDF export does not overwrite an existing PDF.
- The report does not substitute for an authorised medical physicist's assessment, QA review, sign-off or applicable regulatory requirements.

## V0.4 Step 2 — Portable field evidence package

- **Export field package ZIP…** in the toolbar and File menu creates a single archive with `project/room.radverify.json`, `twin/room.radtwin.json`, the draft PDF, and linked evidence under `evidence/`.
- Evidence file paths in both JSON exports are *relative to the JSON file*; when opening an extracted project/twin, RadVerify resolves them relative to its location (not the current terminal directory). The current open project and original linked files remain unchanged.
- Every ZIP member except the manifest has a SHA-256 and byte count in `manifest.json`; `python -m radverify.packaging path/to/archive.zip` checks the inventory without extraction.
- Packaging rejects missing/unreadable evidence, evidence with no recorded hash, or any file whose content does not match its recorded hash. Reference-only evidence remains metadata, explicitly listed as such.
- Export is atomic: an unsuccessful build leaves any existing destination ZIP untouched.
- **Important:** Checksums are for transport integrity, not tamperproof provenance or authentication; a malicious actor can replace both the contents and the unsigned manifest. The ZIP and report are **not compliance certification**.
- To use the exported archive: extract it completely, then open `project/room.radverify.json` in RadVerify; do not open the JSON directly inside the ZIP.

## V0.4 Step 3 — Portable field package import and restoration

- **Import field package ZIP…** on the toolbar and File menu verifies a Step 2 archive, asks for a destination *parent folder*, and creates a **new** `*_restored` directory. It never overwrites an existing record.
- The integrity gate validates SHA-256 hashes, inventory, required project/twin/report files, evidence paths, the evidence index and Windows-safe ZIP paths. It refuses modified, truncated or unsafe archives. Extraction is staged into a temporary directory and completed only after verification; failures remove the staging directory.
- On successful import the restored native project opens in RadVerify, with evidence links resolved to files inside the restored folder. The saved project and twin JSON retain portable relative links, allowing the directory to be moved.
- **Restore via terminal**: `python -m radverify.packaging "C:\\path\\to\\survey.zip" --restore-to "C:\\path\\to\\new_survey_folder"` (the destination directory must not already exist). The existing command without `--restore-to` continues to verify without extraction.
- SHA-256 and the unsigned manifest detect accidental damage and uncoordinated modification, **not malicious replacement of the archive and its manifest**. Check the sender/provenance separately. The report remains a DRAFT, not certification.
- The manifest describes the **original exported snapshot**. After editing or saving a restored project, re-export a new field package to generate a current report and SHA-256 manifest. Do not treat the original manifest as a signature of subsequent changes.

## V0.4 Step 4 — Field deployment readiness audit

- **Help → Export field readiness audit…** generates a Markdown checklist and machine-readable JSON record. This audit uses synthetic data, never an open user project.
- `python -m radverify.deployment --output field_audits/radverify_field_readiness_audit.md` runs eight automated preflight gates and writes the same two files. The `RUN_FIELD_READINESS_AUDIT.bat` helper creates the output folder automatically.
- The gates check runtime import/Tcl, native JSON save/load, the design/as-built twin round trip, portable export/verify/repeat restore, and rejection of corrupt/unsupported files.
- **Safer persistence**: native project saves (and plain JSON exports) use an atomic sibling-file replacement so interrupted writes do not truncate an existing file; failed Save As no longer changes the active filename; failed project/twin imports do not replace in-memory data.
- **Manual gates** remain NOT RUN until a human conducts the field laptop, offline, evidence, asymmetric geometry, RadShield interop, report legibility, backup/security and professional review checks.
- **No automatic field release approval:** automated PASS never authorises a regulatory/compliance certificate, and this prototype has no periodic autosave or standalone installer.
- Full procedures and the sign-off template: `docs/deployment/RADVERIFY_V04_FIELD_DEPLOYMENT_READINESS.md`.

### Floor Plan room dimensions (field GUI refinement)

The **2 Floor Plan** tab now exposes the same three editable room dimensions as
**1 Room Details**, using RadShield-style **− / value / +** controls:
Length S–N, Width W–E and Height, in metres. Use **Enter** or move focus away
to commit typed values; **+ / −** nudges in **0.1 m** steps (minimum 0.5 m).
Room Details and Floor Plan share the canonical `RoomGeometry` object, so edits
redraw immediately and persist to native `.radverify.json`, `.radtwin.json`,
reports and field packages. Reducing room dimensions is rejected if an existing
opening or measurement point would end up outside the room (including height); reducing a dimension
may move the scanner/source centre inside the resized room, with a status
message. The Floor Plan sidebar scrolls on smaller field laptops.

### Opening type field refresh (V0.4 field GUI fix)

In **2 Floor Plan → Add opening…**, selecting **viewing_panel** rather than **door**
now refreshes the type-dependent material choices, suggested Pb equivalence,
opening width, autogenerated ID, and sill/head levels. Initial suggested values
are **door: 0.88 mm Pb** and **viewing panel: 2.2 mm Pb equivalent**, based on
RadShield's room defaults. Manually entered width, Pb equivalence, or custom IDs
are preserved when switching the type; suggested specifications are **not**
field-verified construction. The opening must fit the chosen wall and height.

### Floor Plan shielding labels — wall Pb equivalence

The four wall labels now distinguish **As-built Pb eq** (only the field-recorded
`observed_pb_mm`) from **Design Pb eq** (the imported/read-only
`expected_pb_mm`). Unknown as-built values display **not recorded**, never a
fallback from design or a Pass inspection status. Select a wall and choose
**Open inspection…** to record the as-built construction/Pb equivalence; the
floor-plan label and selected-barrier sidebar refresh when the inspection is
saved. These are recorded **Pb-equivalent shielding values**, not necessarily a
physical lead-sheet thickness measurement; material construction remains
recorded separately in Barrier Inspection. No shielding physics is changed.
