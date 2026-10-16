# RadVerify — V0.2 Step 1 Field Prototype

RadVerify is a field-verification fork of the current RadShield desktop project. V0.2 Step 1 makes the Floor Plan the operational centre of the field workflow.

## Run

```powershell
python app.py
```

The original RadShield launcher from the supplied snapshot has been preserved as:

```text
radshield_app_reference.py
```


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
- No photos/attachments database yet; `evidence_ref` is text in V0.1.
- RadStatus interface is a draft JSON payload only; no live API connection yet.
