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
| 13 | Confirm staffing interpretation (4 positions per 8 beds) and the roster coverage multiplier (placeholder 1.4) | Owner | open |
| 14 | Lawyer review of outreach process, offer letters and JV terms sheets (before any flag is flipped) | Owner | open |
| 15 | Rotate the LINZ key (old key was in git history; history is now cleaned) | Owner | open |
| 16 | 10+ known-outcome regression parcels (or approve sourcing from Council's published decisions) | Owner | open |
| 17 | Where to keep user-data backups off the sandbox (`make backup` output is sandbox-local; options in docs/BACKUP.md). Also set BACKUP_PASSPHRASE | Owner | open |
| 18 | www.building.govt.nz sits behind a bot challenge (not bypassed). Drop into `docs/sources_manual/standards/`: Building Code Acceptable Solutions C/AS (fire), D1/AS1 (access), F6/F7, G1 to G3; Ngā Paerewa NZS 8134:2021; MBIE change-of-use guidance. Until then every numeric requirement is blank and the compliance engine says UNKNOWN or NEEDS_PROFESSIONAL | Owner | open |
| 19 | Fill `config/bed_rules.yaml` regulatory values (min resident room area, ensuite ratio, double occupancy, communal area per bed) from Ngā Paerewa, with clause and date | Owner / me once the PDF is supplied | open |
| 20 | Fill `config/deal_assumptions.yaml` blanks (roster coverage, clinical lead, manager, cook/cleaner, utilities, insurance, supplies, repairs, compliance, other opex, stabilised occupancy, fill ramp, pre-opening, working capital, cost of capital, target and minimum profit, cash limit) and `config/rates.yaml` with QS rates | Owner | open |
