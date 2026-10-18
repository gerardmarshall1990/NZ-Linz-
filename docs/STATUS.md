# Status (last updated 2026-10-18)

Priority (docs/BUILD_NOW.md): Part 7 Remote Conversion Pipeline is the main product; then 1) rest home finder, 2) development site finder, 3) Māori land finder. Everything else is LATER.
Legend: **Done** = built and tested; **Partly** = some of it built, the rest listed; **Not started**. "Needs you" = finished code that shows "needs input" until you supply something (see Blocked on you).
Tests: 191 pass (`make test`). Bootstrap proven on a slice (`docs/BOOTSTRAP.md`).

## Part 1: Master brief (stages)
| Step | Status | Notes |
|---|---|---|
| 1 LINZ ingest | Done | 559,528 sites; rotate the LINZ key (BLOCKERS 15) |
| 2 Zoning, overlays, hazards, amenities, values into `core.sites` | Partly | done: zones, overlays, hazards, hospital/school/rail/bus distances. Missing: rating values (none published), shops/OSM (Geofabrik blocked), slope |
| 3 Rules corpus | Done | 99 chapters, 2,166 chunks, 1,361 rules (33 PC120 proposed); nothing owner-verified yet (10 checks sent) |
| 4 Māori land + rest home provider layers | Partly | only LINZ "Maori" parcel flag and Māori Purpose zone; TPK / Māori Land Court and HealthCERT list not loaded (manual files) |
| 5 Agent + tools + read-only guard | Partly | built; 26 SQL attack cases rejected; tested with a scripted fake model only; the 10 sample queries not run (no key) |
| 6 Calculators (fit_units, subdivision_yield, feasibility, rest_home_score) | Partly | rest home economics and verdicts done; fit_units, subdivision_yield, development feasibility not started |
| 7 Frontend | Partly | map, listing layer, Site Panel (rest home), Ask tab, login; no zone/overlay/parcel layers, no Māori layer, transportable-homes flow not built |
| 8 Floor plan reader + conversion estimator | Partly | DXF exact, manual tracing, human review, calibration; vision reader untested (no key); no sample plan from you yet |
| 9 Consent prep module | Not started | consent packs last |
| 10 Docs, `make refresh`, backup | Partly | DATA_SOURCES, AGENT, LIMITATIONS, BOOTSTRAP, BACKUP, ACCESS done; `make bootstrap` and encrypted backups done; **README with 5-step setup missing** |

## Part 2: Site flow (section 13 build order)
| Step | Status | Notes |
|---|---|---|
| 1 Finish stages 1 to 6 | Partly | see Part 1 |
| 2 Rules engine ingestion and evaluator | Partly | corpus, search, seeds, PC120 operative/proposed done; the rule evaluator is not built |
| 3 Layout engine and financial engine | Partly | rest home layouts and economics done; development layout (max density) engine not started |
| 4 Services module | Not started | licence rules apply (LATER) |
| 5 Site Panel and Button 1, Button 2 report | Partly | Site Panel for rest homes; no development feasibility Buttons 1 and 2 |
| 6 Consent pathway engine and consent packs | Not started | last |
| 7 Māori land specifics | Partly | Māori Purpose and subdivision rule seeds only; no entity layer or proposal outline |
| 8 Docs | Partly | RULES, LIMITATIONS done; CONSENT_PACKS not started |

## Part 3: Rest home tool (section 11 build order)
| Step | Status | Notes |
|---|---|---|
| 1 Property Record, intake UI, CSV import, auto-estimates | Done | |
| 2 Requirements and bed rules discovery with spot-check table | Partly | 17 requirement slots and bed rules config built; every regulatory number blank (Ngā Paerewa and Building Code documents are behind bot challenges: needs you) |
| 3 Compliance gap engine and bed yield engine | Partly | 18 checks, 3 layout options, binding constraint; room-size, ensuite, corridor and door rules not applied until sourced |
| 4 Retrofit cost engine, blank rates, calibration loop | Partly | quantities and cost range built; rates blank (needs you); calibration loop not built |
| 5 Fiscal feasibility, deal sheet, ranking, what-if sliders | Partly | feasibility, walk-away rent, sensitivity, Offer Builder done; one-page Deal Sheet PDF, effort-point ranking and live sliders not built |
| 6 Floor plan reader (DXF, then vision) with review UI | Partly | DXF and manual done; vision untested |
| 7 Plan request pack and site visit form | Not started | |
| 8 Timeline and parallel tracks, conversion consent packs, certification checklist | Not started | |
| 9 Agent tools and acceptance tests | Partly | rest-home tools built; more tools LATER |

## Part 4: Auckland-wide screening, listings, outreach
| Step | Status | Notes |
|---|---|---|
| 1 `core.rh_screen` bulk run, vector tiles, shortlists | Not started | LATER (bulk screening) |
| 2 Listings module, geocoding, alerts, offer logic | Partly | CSV import, LINZ address matching with confidence, history, review queue, verdicts, offer logic done; Trade Me API blocked on terms; no alerts or digest |
| 3 House-scale economics, minimum beds, portfolio view | Partly | minimum beds and too-small flag done; clusters, shared staff, portfolio view not built |
| 4 Field capture PWA, plan request queue | Not started | LATER |
| 5 CRM, routing, call sheets, offer generator, JV terms sheet | Not started | LATER (proposal pack exists, Part 6) |
| 6 Suburb analytics and targeting | Not started | LATER |
| 7 Agent tools, docs (OUTREACH_POLICY, LISTINGS_TERMS) | Partly | LISTINGS.md only |

## Part 5: Feeds, flags, validation
| Step | Status | Notes |
|---|---|---|
| 1 `core.feeds`, FEEDS.md, BLOCKERS.md, `make feeds-status` | Partly | all done except the admin page |
| 2 Importers for pending feeds | Partly | manual-file loader and CSV listings done; licensed attributes and sales importer, Trade Me connector not built |
| 3 Feature flags and gating | Not started | nothing outreach-related exists yet to gate |
| 4 `make validate` and Validation Report | Not started | |
| 5 CONFLICTS.md | Not started | |

## Part 6: Listings to offer (6.9 build order)
| Step | Status | Notes |
|---|---|---|
| Verdict engine (GREEN, AMBER, RED, GREY) | Done | capped at AMBER while placeholders are used; hazards information only |
| Map layer and digest | Partly | map layer, filters, coverage banner done; nightly digest and email not built |
| Offer Builder with Part 6.4 worked example test | Done | fixed, profit share, hybrid; downside cases; cash required; flags |
| Owner proposal pack | Done | markdown and PDF, lawyer banner, wording scan |
| CRM link | Not started | LATER |

## Part 7: Remote conversion pipeline (7.6 build order)
| Step | Status | Notes |
|---|---|---|
| 1 Property intake, plan upload, plan reader with human review | Done | vision reader needs the Anthropic key |
| 2 Evidence gaps, layout options, compliance gaps, fire brief | Done | DRAFT-stamped DXF/PDF drawings, 4 briefs; regulatory numbers blank (needs you) |
| 3 Retrofit quantities, economics, Offer Builder link | Done (needs you) | rates blank; placeholders loaded for running costs |
| 4 Draft consent pack, engineer review workflow, completeness check, upload sheet | Done, Council checklist unverified | pack built to a spec-derived checklist (`council_verified: false`), so "ready to lodge" is refused until you supply the Council's checklist (docs/PART7_STEP4.md) |
| 5 Capture Guide, RFI tracker, timeline widget, metrics | Not started | |

## Part 8: Scale design (8.10 build order)
| Step | Status | Notes |
|---|---|---|
| Approval Queue and touchpoint timing | Not started | LATER: after Part 7 steps 1 to 4 and your go |
| Dashboard | Not started | |
| Capture portal | Not started | |
| Playbooks and delta view | Not started | apartment playbook is Part 8.3 |
| Batch engineer workflow | Not started | |
| Capacity planner | Not started | |

## Platform work not in the spec's step lists (done)
Deal Sheet PDF, ranking by effort point, what-if sliders, retrofit calibration loop, plan request pack with site visit form (docs/DEALSHEET_RANKING_CALIBRATION.md). `make bootstrap` proven on a slice; owner login and Tailscale private access script; user-data backups with encrypted push to a private repo (needs setup); placeholders with banner and AMBER cap; My inputs, Placeholders and Import tabs.

## Tests by module (206 pass)
| Module | Tests |
|---|---|
| Rules corpus (Stage 3) | 69 |
| Chat agent, SQL guard, read-only role | 38 |
| Economics, Offer Builder, worked example | 18 |
| Listings, matching, verdicts, listing offers | 16 |
| Property Record, DXF reader, plan review (Part 7 s1) | 10 |
| Login and access control | 10 |
| Part 7 step 2 (layouts, drawings, compliance, briefs, gaps) | 8 |
| Deal sheet, ranking, what-if, calibration loop, plan request pack | 5 |
| Part 7 step 4 (consent pack, statements, register check, ready gate, reviews, flag) | 10 |
| Placeholders | 7 |
| Scenarios API: retrofit, economics, proposal (Part 7 s3) | 6 |
| Settings and map | 4 |
| Forbidden-words scan | 2 |
| Backups (split check, encrypted push: 11 shell checks) | 2 |
| Browser smoke test (phone width, signs in) | 1 |

## Blocked on you
See docs/BLOCKERS.md (current list). Highest value first: set `APP_PASSWORD` and `TS_AUTHKEY` (open the app on your iPhone); reply to the 10 standards checks; create the private backup repo and set `BACKUP_PASSPHRASE`; `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`; the Ngā Paerewa PDF and Building Code documents; your real running costs to replace placeholders and QS rates; a sample plan and your listings CSV.
