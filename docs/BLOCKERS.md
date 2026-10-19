# Blockers and decisions only the owner can make (kept current; shown at the end of each build step)

| # | Item | Needed from | Status |
|---|---|---|---|
| 1 | **Ask realestate.co.nz about licensed listing data access.** No official public API identified; no scraping or scraper services (decision 11). Source status `blocked`, map shows a coverage warning. | Owner | open |
| 2 | **Read Trade Me developer terms** (register a developer app); decide on commercial-use approval. Until then Trade Me is `pending_licence` and CSV/manual entry is used. | Owner | open |
| 3 | **ANTHROPIC_API_KEY and ANTHROPIC_MODEL** in `.env` (none set in the sandbox). Blocks the plan reader's vision step, the chat agent and any Claude-drafted text. DXF parsing and everything else do not need it. | Owner | open |
| 4 | **Spot-check the key standards** (open `docs/key_standards_check.html` on your phone and send back the list). Nothing is marked verified until you do (decision 17). | Owner | open |
| 5 | **HealthCERT certified providers list** (browser download into `docs/sources_manual/healthcert/`; health.govt.nz blocks scripts) | Owner | open |
| 6 | **Ngā Paerewa NZS 8134:2021 PDF** into `docs/sources_manual/standards/` (bed rules and requirements) | Owner | open |
| 7 | Engineer preferences: preferred drawing formats, file naming, review package layout, turnaround, fees (`docs/ENGINEER_PREFERENCES.md`) | Owner | open |
| 8 | Allow `download.geofabrik.de` (still blocked) | Owner | open |
| 9 | Ask Watercare in writing for permission to use network data commercially (SPEC Part 5 item 2) | Owner | open |
| 10 | Quotes/samples from licensed property data providers; confirm the licence allows AI querying | Owner | open |
| 11 | At least one QS quote and one operator cost sheet for calibration | Owner | open |
| 12 | Ask a HealthCERT-designated auditing agency: staffing at rest-home level; per-site certification and cost; audit timeframes | Owner | open |
| 13 | ~~Confirm roster coverage multiplier~~ confirmed 1.4 by owner on 2026-10-17 (an operator should still confirm staffing: 4 positions per 8 beds) | Operator via owner | partly closed |
| 14 | Lawyer review of outreach process, offer letters and JV terms sheets (before any flag is flipped) | Owner | open |
| 15 | Rotate the LINZ key (old key was in git history; history is now cleaned) | Owner | open |
| 16 | 10+ known-outcome regression parcels (or approve sourcing from Council's published decisions) | Owner | open |
| 17 | Backups: create a PRIVATE GitHub repo `nz-linz-private-backups` (I cannot: 403) and tell me; set `BACKUP_PASSPHRASE` as an environment variable in the cloud environment settings (steps in docs/BACKUP.md; never in chat); plans and uploads need a separate route (docs/BACKUP.md) | Owner | open |
| 18 | www.building.govt.nz sits behind a bot challenge (not bypassed). Drop into `docs/sources_manual/standards/`: Building Code Acceptable Solutions C/AS (fire), D1/AS1 (access), F6/F7, G1 to G3; Ngā Paerewa NZS 8134:2021; MBIE change-of-use guidance. Until then every numeric requirement is blank and the compliance engine says UNKNOWN or NEEDS_PROFESSIONAL | Owner | open |
| 19 | Fill `config/bed_rules.yaml` regulatory values (min resident room area, ensuite ratio, double occupancy, communal area per bed) from Ngā Paerewa, with clause and date | Owner / me once the PDF is supplied | open |
| 20 | Replace the 11 loaded placeholders (cook/cleaner/laundry, utilities, insurance, repairs, compliance, pre-opening, working capital, lease term, cost of capital, minimum and target profit) with real figures on the Placeholders page, plus your $10,000 per bed estimate; fill `config/rates.yaml` with QS rates. Cash limit still blank | Owner | open |
| 21 | Open the app on your iPhone: create a Tailscale account, install the app, set `APP_PASSWORD` and `TS_AUTHKEY` in the environment settings, allow the Tailscale domains (docs/ACCESS.md) | Owner | open |
| 22 | ~~Write `README.md` with the 5-step setup~~ done 2026-10-18 | Me | closed |
| 23 | Reply to the 10 numeric standards checks sent in chat (and later the rest of `docs/key_standards_check.html`) | Owner | open |
| 24 | PENDING (owner): HealthCERT / Ministry certification steps and parallel-track lead times (recruitment, audit, long-lead orders): all blank in `config/parallel_tracks.yaml` and the certification checklist; set them on the Track tab when known. | Owner | open |
| 25 | PENDING (owner): Council RFI due dates are entered by you from the Council's letter; no statutory period is assumed. | Owner | open |
| 26 | PENDING (owner): Trade Me API keys (TRADEME_CONSUMER_KEY/SECRET, TRADEME_TOKEN/TOKEN_SECRET) after reading the developer terms, then set `trademe.status: live` in `config/listing_sources.yaml`. The connector's endpoint and field names are unverified against the live API. | Owner | open |
| 27 | PENDING (owner / later): Healthy Waters stormwater layer not yet discovered and ingested; Watercare network data stays unloaded until written permission (licence); Watercare Infrastructure Growth Charge schedule not fetched. Services fields are manual meanwhile. Also: vehicle access standards (transport chapter) are not in the rules corpus, so access is UNKNOWN in every development scenario. | Owner / me | open |
| 28 | PENDING (owner / later): Stats NZ census (population aged 75+) source and licence not discovered; no HealthCERT list: suburb analytics leave certified beds and beds per 1,000 aged 75+ blank. A routing engine (OSRM / pgRouting with an NZ extract) is not installed: call-sheet distances are straight-line. | Owner / me | open |
| 29 | 2026-10-19: building.govt.nz, legislation.govt.nz, mbie.govt.nz, health.govt.nz and aucklandcouncil.govt.nz all answer scripts with a bot challenge or block (not bypassed), so no Acceptable Solution or Building Code text was fetched. The new **Standards** tab lets the owner type the four bed-rule values from their own copy with clause and date; blank until then. config/building_code_clause_checklist.yaml lists clause identifiers only (unverified). | Owner | open |
| 30 | 2026-10-19: only 6 snippet-only consent-outcome leads found, all retirement villages, none matchable to a parcel (docs/validation/KNOWN_OUTCOMES.md). Item 16 stays open: supply 10+ Auckland sites with known care or conversion consent outcomes, or save Council decision PDFs into docs/sources_manual/other/. | Owner | open |
