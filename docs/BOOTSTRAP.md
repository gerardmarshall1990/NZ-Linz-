# make bootstrap: rebuild every regenerable layer from the original sources

`make bootstrap` (script `scripts/bootstrap.sh`) rebuilds the database named in `.env` from the public sources, in this order, with a timing per step in `bootstrap_timings.log`:
`init_db` (database, extensions, schemas, read-only role) → `ingest_linz` → `ingest_auckland` (Council layers, plan-change summaries, AT stops) → `core_sites` → `rules_corpus` (AUP and PC120 PDFs, OCR, chunks, rules, checks) → `owner_review_log` (replay your rule answers) → `feeds_register` → `app_tables_roles` (app role, rest home tables, requirement slots) → `manual_sources` (files you dropped in `docs/sources_manual/`, if any).
Needs: `.env` with `LINZ_API_KEY` and the database passwords. No other manual step remains (two were found and removed by the proof below).

## Proof on a slice (rule: do not repeat the full rebuild)
Slice mode: `SLICE_BBOX=minE,minN,maxE,maxN` (EPSG:2193) in `.env` loads only that rectangle (cache under `data/slice`). Proof run: a clean clone of the repository, an empty database and empty cache, a Devonport / Narrow Neck / Bayswater rectangle with 4,609 parcels.
| Step | Time |
|---|---|
| init_db | 1 s |
| ingest_linz | 4 s |
| ingest_auckland | 28 s |
| core_sites | 92 s |
| rules_corpus | 199 s (OCR results and PDFs were already cached from the earlier attempts; see the estimate below) |
| owner_review_log, feeds, app tables, manual | 1 s |
| **Total** | **325 s** |

Row counts against the main database (centre-in-rectangle for geometry tables): all LINZ and Council raw tables, `core.sites` (4,609 = 4,609), all analytics tables equal: 1,361 rules (1,328 operative, 33 proposed), 2,166 text chunks, 99 source documents, 4 plan versions, 17 requirement slots, and an identical checksum of every operative rule's zone, parameter and numeric value. Differences, all explained: 3 parcels changed upstream at LINZ since the main load (one subdivided into two: 2 new, 1 gone) and 5 parcel areas edited upstream; 7 parcels crossing the rectangle edge have fewer buildings or one fewer overlay (their features lie outside the rectangle); distance-to-hospital and distance-to-rail differ in slice mode because the nearest facility can lie outside the rectangle; the plan-change attribute tables hold only the slice's rows (every one of them exists in main).

## Defects the proof found (all fixed in the repository)
1. `ocr_aup.py` let tesseract use 4 OpenMP threads per process: 4 workers on 4 cores stalled for 20+ minutes on one page. Now one thread per process.
2. PC120 info sheets were extracted in column-interleaving layout mode (the earlier fix had been done by hand on the main database), so the quote checks failed. Now reading order.
3. A Council layer with no features in the extent left no table and crashed the core step. Now an empty table with the layer's own columns.
4. **The Council property pick per parcel was arbitrary when property polygons overlap** (an unordered UPDATE ... FROM). Two builds disagreed on about 9% of parcels in the slice (411 of 4,607), which moved the PC120 flags on about 12. Now deterministic (smallest polygon, then lowest id), and overlay lists are sorted. The main database was built before this fix and was re-run on 2026-10-17 with your go-ahead (see below).

## Full-run estimate (not re-run, by instruction)
Measured from scratch on live sources: LINZ ingest 4,119 s (69 min) and Council layers 4,507 s (75 min). Not measured on a clean full run: core build (the earlier full build took on the order of an hour; per-parcel scaling from the slice is unreliable because overlay joins dominate) and the rules step (first-time OCR of 99 chapters on 4 cores after the thread fix: tens of minutes, unmeasured). Plan for roughly 3.5 to 5 hours end to end, mostly download time. Free disk needed: about 14 GB (6.6 GB downloads, 6.3 GB database, working space).

## Main database re-run of 30_sites_enrich.sql and 50_plan_versions.sql (2026-10-17)
Rollback first: `backups/rollback/core_sites_plan_versions_before_20261017.dump` (core.sites and analytics.plan_versions, restorable with pg_restore), `backups/rollback/v_site_plan_status_before.sql`, and a column copy of core.sites in schema `rollback_20261017` (drop it when satisfied: `DROP SCHEMA rollback_20261017 CASCADE`). Run time: file 30 took 1,013 s, file 50 took 91 s.
Result (`scripts/diff_sites_rerun.py`): 559,528 parcels before and after, same ids. **Zone changes: 0. Overlay changes (as sets): 0.** Council property record changed on 59,650 parcels (10.7%; the old pick was arbitrary where property polygons overlap, and often landed on a unit-level or non-residential record). PC120 flags changed on 12,502 parcels (proposed zone or zone-differs; 449 changed `pc120_depends`: parcels that had no proposed-zone match now have one). Sites "depends on PC120": 449,980 → 450,285; "not assessed": 109,548 → 109,243. No other table changed row counts (96 tables compared). Example: 35 Argyle Street, Herne Bay (Single House): property 30011914 → 11220654; PC120 proposed zone none → Mixed Housing Urban, zone differs → true.
Side effect found and fixed: 50_plan_versions.sql re-granted the agent role SELECT on every core table, including the chat history. The grant is now narrowed, `99_ai_grants.sql` revokes chat history access at the end of `make app-db`, and the agent-role test caught it.

## Final proof on the final code (2026-10-17, after every fix above)
Clean clone, empty database, empty cache, same 4,609-parcel rectangle. **Total 1,285 s (21.4 min)**: init 1 s, LINZ 31 s, Council layers 64 s, core sites 43 s, **rules 1,145 s (19 min, first-ever OCR run on an empty cache with the one-thread fix)**, the rest 2 s. No errors.
Against the main database (after its re-run): `core.sites` 4,609 = 4,609; **Council property record differences 0; PC120 flag differences 0; zone differences 0**; rules checksum (zone, parameter, value, status over all 1,361 rules) identical (f430b7d69d...), 2,166 chunks, 99 documents, 4 plan versions, 17 requirement slots all equal; every plan-change row in the slice exists in main. Remaining differences, 14 parcels of 4,607 (0.3%), all upstream or edge: 5 parcel areas edited at LINZ, 8 parcels crossing the rectangle edge (fewer buildings or one fewer overlay), 1 parcel whose address list gained a point at LINZ (55 Calliope Road became 55A/55B). Two parcels differ in membership (one subdivided at LINZ, one reclassified at LINZ from surveyed to legalisation). Hospital and rail distances differ by design in slice mode.
The full-run estimate above is updated by this clean timing: rules ≈ 20 to 30 minutes on 4 cores (OCR dominates), so a full rebuild is about 3 to 4.5 hours, mostly the LINZ (69 min) and Council (75 min) downloads.
