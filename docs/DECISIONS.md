# Decisions log

Owner decisions are in MASTER_SPEC.md Part 0.4 (numbered 1 to 19; they override everything else). This file records those in short form plus decisions made while building. Newest last.

## Owner decisions (Part 0.4)
1. Stage 3 first; slope right after, before the layout engine, candidate parcels only, open licence-clean elevation data, record source and date.
2. Plan currency check first; mark density outputs "plan version unverified" until resolved.
3. Hosts: retest Geofabrik; Auckland Transport + Council open data as fallback; never bypass health.govt.nz; `docs/sources_manual/` for hand-dropped files.
4. Rest home tool (Part 3 steps 1 to 5) before consent packs; feeds register right after Stage 3.
5. Non-fillable council forms: field-by-field data sheet in portal order plus attachments list; never call anything "pre-filled" unless it is.
6. Forbidden-word scan targets outcome claims, not the word "approved" itself.
7. Regression parcels from published Council decisions; owner spot-checks. Watercare distances for 5 sites, owner verifies.
8. Watercare licence concern covers network GIS only; fee schedules are separate.
9. Storeys unknown from LINZ until plans or licensed/surface data confirm.
10. Unsourceable inputs stay blank and flagged.
11. realestate.co.nz: no scraping, no third-party scrapers; source `blocked`; manual/CSV meanwhile; Trade Me only via official API if terms permit.
12. Offer Builder is a priority: fixed, JV profit share, hybrid; always show cash required and downside.
13. Part 7 is PRIORITY 1. For conversions of existing buildings, natural hazards are information only.
14. AI-drafted drawings allowed if stamped DRAFT; never producer statements, signatures, registration numbers or final fire reports. Engineer preferences go in `docs/ENGINEER_PREFERENCES.md`.
15. Scale design (Part 8): virtual-first, human minutes measured, one-tap Approval Queue, no automated outreach or lodgement without the owner's approval record.
16. Rules stored as `operative` or `proposed` + plan change id; never merged; "depends on PC120" where they differ.
17. Numeric standards stay unverified until the owner verifies them; `ocr_confidence` recorded; `docs/key_standards_check.html` for phone checking.
18. OCR time-boxed to residential/business zones, activity tables, and needed E chapters.
19. Build priority per `docs/BUILD_NOW.md`; everything else LATER. Best Use tab (Part 9) after rest home pipeline and development flow.

## Build decisions (mine)
- 2026-10-17: The five old spec files were never committed to the repo (they existed only as uploads), so there was nothing to `git rm`. `MASTER_SPEC.md` is now the single spec; `CLAUDE.md` is the short pointer.
- Environment: PostgreSQL 16 + PostGIS installed with apt in the sandbox (no Docker daemon). `scripts/db_up.sh` restarts it. Backups: `make backup` writes to `backups/` (gitignored, sandbox-local: copy off-sandbox when a server exists).
- Git history was rewritten with `git filter-repo` to remove the committed LINZ key; branch force-pushed. The key must still be rotated by the owner.
- Rules corpus built from Council's official chapter PDFs with OCR repair (text layers drop content). Quote-matching is not the same as owner verification; see decision 17.
- Plan currency: loaded zone layer = operative AUP (fully operative 23 Jul 2026). PC120 is proposed (submissions closed 24 Sep 2026) and not applied.
- 2026-10-18 (autopilot): the earlier instruction "do not start the development-site flow until I say" is superseded by the owner's autopilot list, which includes it (item E). Order follows the owner's list.
- 2026-10-18 (autopilot): demo data is labelled DEMO (source_id `DEMO-n`), uses invented rent and bedrooms on real addresses, is removable with `make demo-clear`, and never writes your saved inputs.
- 2026-10-18 (autopilot): Trade Me connector built against the API as I know it, kept OFF and marked UNVERIFIED until keys and terms; CSV remains the route. CRM leads can be created only while outreach_enabled is true (routes gated).
- 2026-10-18 (autopilot): bulk screening table is analytics.rh_screen (regenerable, rebuilt by make screen), not core.rh_screen as the spec names it, so it stays out of the small user-data backup. Screening gfa_per_bed is a flagged placeholder (60 m2, cautious).

## Staffing default: 1 staff position per 3 beds (owner instruction)
The owner changed the default from 4 positions per 8 beds to 1 per 3 beds (stored as 2.666667 positions per 8 beds in config/deal_assumptions.yaml). The roster cover multiplier (1.4) still applies on top. A value saved in My inputs still overrides this default.

## Profit target: $1,000 net per bed per week (owner instruction)
Saved as profit_per_bed_per_week = 1000 in config/deal_assumptions.yaml. The Quick answer on the Offer tab uses it as the profit floor (after running costs, retrofit repayment and the rent paid). At the owner's fee of $1,600 per bed per week and the current cost placeholders it cannot be met at any rent; the screen says so and shows the fee that would meet it.
