# Part 7 step 1: property intake, plan upload, plan reader with human review

Run: `make app-db` (tables + limited `app_rw` role), then `make app`, open port 8000 (mobile UI at `/`).

## What works
- Find a property by address; create its Property Record. Auto-estimates (all ESTIMATED, method stated) come from LINZ data: building count, footprints, address points. Storeys are never guessed. Bedrooms are only offered as a unit-count proxy when 2+ address points exist, with a "not a bedroom count" note.
- Every fact has value, source, confidence (ESTIMATED / DOCUMENTED / CONFIRMED) and a history row on each change. CSV export, and CSV import with dry run.
- Uploads: type is decided from file bytes (PDF, PNG, JPEG, DXF, IFC; raw scan meshes kept as reference only), 60 MB limit, sanitised names, never executed.
- Plan reader:
  - **DXF**: parsed directly and deterministically (rooms, labels, doors, corridor width). Drawing units set the scale; a DXF without units gives blank measurements until you declare units.
  - **PDF/image**: manual tracing on the phone, or the vision reader. The vision reader is blocked until `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` are set (the API returns 503, untested against the real model).
  - Calibration: two-point (with residual shown) or stated scale on PDF. No scale, no areas or widths.
  - Human review gate: edits are logged; every room needs a type; only a human-confirmed extraction writes CONFIRMED facts, and only for the levels confirmed. Measured facts (corridor width, door width, net room area) need a calibrated level. Re-open creates a new version.

## Known limits
- Corridor width is the short side of the minimum rotated rectangle: approximate for L-shaped corridors.
- A DXF label containing both "bedroom" and "ensuite" is typed ensuite with a warning; review it.
- IFC is accepted and stored but not parsed.
- Door widths from block size are approximate; attribute widths are used when present.

## Tests
`tests/test_property_record.py`: synthetic ground-truth DXF (areas, corridor 1.2 m, door 0.9 m, mm units), unitless DXF, calibration maths, estimates, history, upload validation, confirm flow, confidence propagation, vision-blocked 503.
