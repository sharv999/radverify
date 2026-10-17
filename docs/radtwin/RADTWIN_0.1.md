# Radiation Room Digital Twin — interchange schema 0.1

`*.radtwin.json` is the product-neutral interchange file for a radiation room.
It is deliberately separate from RadVerify's native `*.radverify.json` project
file and from RadShield's native project format.

## Purpose

The same room record can move through the lifecycle:

```text
RadShield design  ->  Radiation Room Digital Twin  ->  RadVerify as-built verification
                               |
                               +--------------------->  RadStatus compliance/status
```

A verified existing room can also flow back to RadShield as the starting
geometry for a refurbishment, equipment replacement, or reassessment.

## Coordinate convention

The coordinate system is fixed in schema 0.1:

- origin: south-west corner of the room at finished floor level (FFL)
- +x: west to east
- +y: south to north
- +z: upwards from FFL
- distances: metres unless an individual field states otherwise
- `dimensions_m.south_north` = RadShield/RadVerify `length_m`
- `dimensions_m.west_east` = RadShield/RadVerify `width_m`
- an N/S wall opening offset is its centre x-coordinate from the west wall
- an E/W wall opening offset is its centre y-coordinate from the south wall

## Separation of design and as-built state

A barrier carries two deliberately separate records:

- `design_specification`: intended/required construction
- `as_built`: observed or otherwise verified construction

`verification` records the inspection outcome, primary evidence reference, structured evidence records and notes. Each evidence record can carry type, human reference, linked file path, inspection date, inspector, description and SHA-256 file hash. Linked files are referenced rather than embedded in schema 0.1.
No consuming application should silently replace design intent with as-built
construction or vice versa.

## Main objects

- `room`: identity and site metadata
- `geometry`: dimensions, openings and fixed geometric features
- `equipment`: spatially located equipment; schema 0.1 identifies one primary
  radiation source for compatibility with the current RadShield room model
- `barriers`: design, as-built and verification state for walls, floor, ceiling
  and openings
- `inspection`: inspector/date/drawing/room notes
- `measurement_points`: spatial survey locations, instrument/calibration metadata, latest reading and append-only measurement history

## Measurement history

Schema 0.1 now permits richer measurement metadata without changing the schema identifier. Each spatial `measurement_point` may carry instrument identity, serial number, calibration dates/reference, field conditions and a `measurement_history` array. Each history record snapshots the instrument/calibration state and stores gross, background and corrected dose-rate readings, assessment status and notes. Legacy single-reading fields remain populated from the latest record for backwards compatibility with existing RadStatus/RadShield consumers.

## RadShield compatibility boundary

RadVerify provides `radtwin_to_radshield_geometry()` as an executable mapping
to the current RadShield `RoomGeometry.to_dict()` shape.  This proves that the
portable twin contains enough information to reconstruct the current RadShield
floor-plan geometry without importing RadVerify's native project format.

RadShield should implement its own importer against this schema rather than
depend on the RadVerify package at runtime.

## Versioning

Schema 0.1 is identified by:

```json
"schema": "radiation-room-digital-twin-0.1"
```

Breaking changes require a new schema identifier.  Product-specific project
schemas may evolve independently of the shared twin schema.
