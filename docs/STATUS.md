# Status (last updated 2026-10-17)

**Priority (docs/BUILD_NOW.md):** Part 7 Remote Conversion Pipeline is the main product; then 1) rest home finder, 2) development site finder, 3) Māori land finder. Everything else is LATER.

| # | Step | Status | Last updated | Blockers / notes |
|---|---|---|---|---|
| 1 | Stage 1 LINZ ingest | done | 2026-10-16 | LINZ key must still be rotated (BLOCKERS 15) |
| 2 | Stage 2 Council layers, `core.sites` (559,528 sites) | done | 2026-10-16 | no rating values published; slope not done |
| 3 | Stage 3 rules corpus | **built; awaiting owner spot-check** | 2026-10-17 | 99 AUP chapters, 2,166 chunks, 1,361 rules (operative + 33 proposed PC120); 69 tests pass; nothing owner-verified (BLOCKERS 4) |
| 3a | Rules corrections (decisions 16-18): operative/proposed, OCR confidence, key standards check page; plan currency | done | 2026-10-17 | `docs/key_standards_check.html` sent to owner; 18 values are OCR-only |
| 3b | **Part 7 Remote Conversion Pipeline** | steps 1-2 built and tested (step 2: evidence gaps, 3 layout options, DXF/PDF drawings, compliance checks, 4 briefs); steps 3-5 not started | 2026-10-17 | plan reader vision needs ANTHROPIC_API_KEY (BLOCKERS 3); engineer preferences missing (BLOCKERS 7) |
| 4 | Feeds register, BLOCKERS, `make feeds-status` | done | 2026-10-17 | |
| 3d | Economics engine + Offer Builder (Part 6.4 worked example tested), retrofit cost engine (rates blank), proposal pack | built, 22 tests | 2026-10-17 | `docs/ECONOMICS.md`; needs your inputs: deal assumptions, QS rates (BLOCKERS 20) |
| 3e | Listings: CSV import, address matching, history, Property Record upgrade, verdicts (GREEN/AMBER/RED/GREY), minimum beds | built, 12 tests | 2026-10-17 | `docs/LISTINGS.md`; Trade Me terms pending, realestate.co.nz blocked; verdicts GREY until deal inputs set (BLOCKERS 20) |
| 3f | Map and Site Panel (`/`), My inputs screen (assumptions and rates stored in the app), parcel-at-point, listing map layer | built, browser-tested | 2026-10-17 | no shortlists, digest, alerts yet |
| 3c | Scale layers (Part 8) | LATER | | after Part 7 steps 1-4 and owner go |
| 5 | Slope for candidate parcels | not started | | before layout engine; open DEM/contours, record source and date |
| 6 | Stage 4 Māori land + rest home provider layers | not started | | HealthCERT list is manual (BLOCKERS 5) |
| 7 | Stage 5 agent, Stage 6 calculators | LATER (agent) / needed for development finder (calculators) | | agent needs API key |
| 8-9 | Rules engine, layout, financial engine; Site Panel UI | not started | | development site finder |
| 10 | Rest home tool (Part 3) | part of Part 7 | | bed rules need Ngā Paerewa PDF (BLOCKERS 6) |
| 10b | Listings-to-offer (Part 6) | not started | | Trade Me terms and realestate.co.nz (BLOCKERS 1-2) |
| 9 | Best Use tab (Part 9) | LATER | | after rest home pipeline and development flow |
| 11-16 | Services, floor plan extras, flags, bulk screening, consent packs, docs | LATER | | |

Environment: PostgreSQL 16 + PostGIS via apt in the sandbox (`scripts/db_up.sh`); `make backup` writes to `backups/` (sandbox-local, gitignored). `make bootstrap` is not built yet: rebuild order today is `make refresh` (LINZ, Council, plan changes, AT stops, core, rules).
Part 7 step 1 (`docs/PART7_STEP1.md`): `make app-db` then `make app` (port 8000). Step 2: `docs/PART7_STEP2.md`. Next: Part 7 step 3 (retrofit quantities, economics, Offer Builder link): needs `config/rates.yaml` (QS rates, BLOCKERS 8-ish) and deal assumptions.
