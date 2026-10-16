# RadVerify — V0.1 Field Prototype

RadVerify V0.1 is a field-verification fork of the current RadShield desktop project.

## Run

```powershell
python app.py
```

The original RadShield launcher from the supplied snapshot has been preserved as:

```text
radshield_app_reference.py
```

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
