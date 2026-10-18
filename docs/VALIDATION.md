# Validation report
Generated 2026-10-18T20:16:28 by `make validate`. 3 of 7 checks pass.

| # | Check | Result |
|---|---|---|
| 1 | Rules: owner spot-check of at least 15 key standards in each of the four main residential zones | **PENDING** |
| 2 | Geometry: layout, compliance evaluator and plan reader hand-calculated test cases | **PASS** |
| 3 | Economics: hand-calculated formulas; unset inputs give 'needs input' and no numbers | **PASS** |
| 4 | Calibration on real properties (tool vs reality) | **PENDING** |
| 5 | Data coverage | **PENDING** |
| 6 | Compliance guardrails | **PASS** |
| 7 | Feeds: every feed live or consciously manual | **FAIL** |

## 1. Rules: owner spot-check of at least 15 key standards in each of the four main residential zones: PENDING

- Residential - Single House Zone: 0 confirmed by you of 64 extracted rules (need 15)
- Residential - Mixed Housing Suburban Zone: 0 confirmed by you of 81 extracted rules (need 15)
- Residential - Mixed Housing Urban Zone: 0 confirmed by you of 83 extracted rules (need 15)
- Residential - Terrace Housing and Apartment Building Zone: 0 confirmed by you of 84 extracted rules (need 15)
Nothing is marked verified until you confirm it. Open docs/key_standards_check.html and reply with your checks.

## 2. Geometry: layout, compliance evaluator and plan reader hand-calculated test cases: PASS

- 18 passed, 0 failed
- `18 passed, 1 warning in 4.58s`

## 3. Economics: hand-calculated formulas; unset inputs give 'needs input' and no numbers: PASS

- 24 passed, 0 failed (includes the Part 6.4 worked example)
- `24 passed, 1 warning in 2.45s`

## 4. Calibration on real properties (tool vs reality): PENDING

- Tolerance (your input): not set
- Properties you chose: none chosen (pick 3 to 5)
- Quotes on file by line: none
Needs from you: a tolerance %, 3 to 5 properties, at least one QS quote per rate line used, and one operator's real cost sheet.

## 5. Data coverage: PENDING

- Listings matched to a LINZ address with high/medium confidence: 0 of 0 (no listings imported yet)
- Properties with any fact, by confidence tier: none yet
- Allowance share of retrofit cost in recent runs: no retrofit total has been computed (rates blank)
- Licensed property feed match rate: not measurable (no feed yet)

## 6. Compliance guardrails: PASS

- 27 passed, 0 failed (forbidden-words scan, login/access control, no generated statements or signatures, review link flag)
- Outreach, field capture and offer-letter flags: outreach_enabled=False, field_capture_enabled=False, offer_letters_enabled=False (gated routes answer 403 while false; tested)
- CRM source/lawful-basis gates, do-not-contact enforcement and bulk-send limits: the outreach features are not built (flags stay off), so these cannot be tested yet. They must be built and tested before any flag is flipped.

## 7. Feeds: every feed live or consciously manual: FAIL

- 12 feed(s) are neither live nor consciously manual:
  - pending_licence: Watercare water and wastewater network data
  - pending_purchase: Licensed property attributes and sales (Cotality, Valocity or similar)
  - pending_licence: Trade Me developer API (rentals)
  - blocked: realestate.co.nz listings
  - not_started: Te Puni Kōkiri / Māori Land Court public data
  - blocked: OpenStreetMap via Geofabrik extract
  - not_started: Stats NZ census (population aged 75+)
  - not_started: MBIE Building Code, Building Act, change-of-use guidance (building.govt.nz)
  - blocked: Anthropic API (agent, plan vision)
  - pending_purchase: Quantity surveyor rates and real quotes
  - pending_purchase: Operator running costs
  - not_started: Routing (OSRM/pgRouting, self-hosted)

`make feeds-status`:
```
STATUS           LAST             ROWS  FEED
live             2026-10-16    737,649  LINZ Data Service (parcels, titles, buildings, addresses)
live             2026-10-16    559,528  Auckland Council open data (zones, overlays, hazards, property keys)
                                          licence: open (CC BY 4.0) | blocked: no rating values published | next: ask licensed provider for values
live             2026-10-17      2,166  Auckland Council plan text (operative AUP chapters)
live             2026-10-17         33  Auckland Council PC120 documents (proposed rules)
manual           -                   -  Auckland Council forms, fee schedules, lodgement checklists
                                          licence: public | blocked: AC1009 lodgement checklist v.21 supplied by the owner and loaded; AC1021, the portal screens and the fee schedule not seen (aucklandcouncil.govt.nz is not reachable from the sandbox) | next: owner drops AC1021, portal screens and the fee schedule into docs/sources_manual/council_forms/ (BLOCKERS)
live             2026-10-17      6,863  Auckland Transport GTFS (stops)
pending_licence  -                   -  Watercare water and wastewater network data
                                          licence: non-commercial / no-derivatives: written permission needed | blocked: licence | next: owner asks Watercare in writing (BLOCKERS 9)
manual           -                   -  Vector network capacity
                                          licence: indicative map only
pending_purchase -                   -  Licensed property attributes and sales (Cotality, Valocity or similar)
                                          licence: paid; confirm AI-query licence | blocked: no quote yet | next: owner obtains quotes (BLOCKERS 10)
pending_licence  -                   -  Trade Me developer API (rentals)
                                          licence: official API; commercial use may need approval | blocked: terms not yet read; connector built (off until keys and terms) | next: owner reads developer terms, registers an app, sets keys, then trademe.status live (BLOCKERS 2, 26)
blocked          -                   -  realestate.co.nz listings
                                          licence: no official public API identified; no scraping | blocked: no lawful automated route (decision 11) | next: owner asks realestate.co.nz about licensed data access (BLOCKERS 1)
manual           -                 n/a  HealthCERT certified rest home list
                                          licence: public; health.govt.nz serves a bot challenge to scripts | blocked: bot challenge (not bypassed) | next: owner drops the list export into docs/sources_manual/healthcert (BLOCKERS 5)
not_started      -                   -  Te Puni Kōkiri / Māori Land Court public data
                                          licence: public only | next: Stage 4 cross-check
blocked          -                   -  OpenStreetMap via Geofabrik extract
                                          licence: ODbL | blocked: download.geofabrik.de blocked in sandbox; Overpass unreachable | next: owner allowlists host (BLOCKERS 8)
not_started      -                   -  Stats NZ census (population aged 75+)
                                          licence: to discover | blocked: data.stats.govt.nz blocked; datafinder.stats.govt.nz reachable
not_started      -                   -  MBIE Building Code, Building Act, change-of-use guidance (building.govt.nz)
                                          licence: public | next: host now reachable; discover and load
manual           -                   0  Ngā Paerewa NZS 8134:2021 and HealthCERT guidance
                                          licence: free PDF; owner download | blocked: file not yet supplied | next: owner drops PDF in docs/sources_manual/standards (BLOCKERS 6)
manual           -                   -  Council property file / LIM, title copies, Companies Office
                                          licence: per-request fees
blocked          -                   -  Anthropic API (agent, plan vision)
                                          licence: owner key, usage-based | blocked: no key in sandbox environment | next: owner adds key and model to .env (BLOCKERS 3)
pending_purchase -                   -  Quantity surveyor rates and real quotes
                                          licence: owner relationships | next: owner provides QS quote (BLOCKERS 11)
pending_purchase -                   -  Operator running costs
                                          licence: owner inputs | next: owner provides operator cost sheet (BLOCKERS 11, 13)
not_started      -                   -  Routing (OSRM/pgRouting, self-hosted)
                                          licence: free | blocked: LATER
```

## Go / no-go

**NO-GO.** Not every check passes. The outreach, field capture and offer letter flags stay off. This report never flips a flag; you do, in `config/feature_flags.yaml`, only when you decide.

Blocking items:
- 1. Rules: owner spot-check of at least 15 key standards in each of the four main residential zones (PENDING)
- 4. Calibration on real properties (tool vs reality) (PENDING)
- 5. Data coverage (PENDING)
- 7. Feeds: every feed live or consciously manual (FAIL)
