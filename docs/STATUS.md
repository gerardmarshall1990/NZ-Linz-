# Status (last updated 2026-10-18, end of the autopilot run)

Legend: **Done** = built and tested. **Done, needs you** = built; shows "needs input" or a flagged placeholder until you supply something (docs/BLOCKERS.md). **Partly** = what is left is listed. **Flagged off** = built, behind a feature flag that only you can switch on.
Tests: 283 (`make test`). Bootstrap proven on a slice (docs/BOOTSTRAP.md). Validation report: `docs/VALIDATION.md` (`make validate`): NO-GO until your spot-checks and calibration data exist.
Checklist of the autopilot run: docs/AUTOPILOT.md. Explanations: docs/IPHONE_TEST.md (start here), PART7_STEP4.md, DEALSHEET_RANKING_CALIBRATION.md, DEVELOPMENT_FLOW.md, SCREENING_OUTREACH.md, SCALE.md, CONFLICTS.md.

## Part 1: Master brief
| Step | Status | Notes |
|---|---|---|
| 1 LINZ ingest | Done | 559,528 sites; rotate the LINZ key (BLOCKERS 15) |
| 2 Zoning, overlays, hazards, amenities | Partly | zones, overlays, hazards, distances done; rating values (none published) and OSM amenities (host blocked) missing |
| 3 Rules corpus | Done, needs you | 1,361 rules (33 PC120 proposed); none owner-verified: send back the 10 standards checks |
| 4 Māori land and rest home provider layers | Partly | LINZ Māori flag, Māori Purpose zone, map layer, module; TPK export and HealthCERT list importers built, files not loaded |
| 5 Agent and tools | Partly | built and tested with a scripted model; needs ANTHROPIC_API_KEY / ANTHROPIC_MODEL for the real one |
| 6 Calculators | Done, needs you | fit_units, subdivision_yield (area rule only), feasibility, rest home economics and verdicts |
| 7 Frontend | Done | map with layers, 14 tabs, login; phone width tested |
| 8 Floor plan reader | Partly | DXF exact, tracing, human review, calibration; vision reader needs the key; no sample plan from you yet |
| 9 Consent prep | Done, Council checklist partly seen | building consent pack to AC1009; resource consent pack to the spec list (Council RC checklist unseen) |
| 10 Docs, refresh, backup | Done | README with the 5-step setup; encrypted backups (need BACKUP_PASSPHRASE and the private repo) |

## Part 2: Development-site flow
| Step | Status | Notes |
|---|---|---|
| 2 Rules evaluator | Done, needs you | geometry rules, UNKNOWN when a rule is not loaded; vehicle access standards not in the corpus |
| 3 Layout and financial engines | Done, needs you | 20+ arrangements per run, binding constraint; finance inputs yours |
| 4 Services module | Done, needs you | licence-aware, manual fields, capacity UNKNOWN until a letter |
| 5 Site Panel buttons 1 to 3 | Done | Develop tab: scenarios, report PDF, consent pack |
| 6 Consent pathway engine | Partly | activity rows and trigger list in the report; no per-scenario consent status derivation |
| 7 Māori land specifics | Done, needs you | partnership-first, entity and TPK data blank until you supply them |
| 8 Docs | Done | DEVELOPMENT_FLOW.md |

## Part 3: Rest home tool
All steps Done or Done, needs you (rates, running costs and QS quotes are yours): property record, plan reader, bed yield, compliance (regulatory numbers blank until Ngā Paerewa / Building Code are supplied), retrofit with calibration loop, feasibility, Deal Sheet PDF, ranking and sliders, timeline scenarios and parallel tracks (lead times blank), certification checklist (Ministry steps not discovered).

## Part 4: Screening, listings, outreach
| Step | Status | Notes |
|---|---|---|
| Bulk screening, map layer, shortlists, suburb analytics | Done, needs you | 362k candidates, ESTIMATED beds from a flagged placeholder; certified beds and census blank until files loaded |
| Listings (CSV), digest, saved searches | Done | Trade Me connector built, off until terms and keys (BLOCKERS 2, 26) |
| House-scale and portfolio economics | Done, needs you | |
| Field capture, CRM, routes, offer generator | Flagged off | guardrails tested; straight-line routes (no routing engine) |

## Part 5: Feeds, flags, validation
Feeds register and admin tab, importers (attributes, sales, rest homes, census) with dry run, feature flags, validation report, CONFLICTS.md: Done. Validation says NO-GO (3 of 7 checks pass; the rest need your data).

## Part 6: Listings to offer
Verdicts, map, Offer Builder (worked example is a test), proposal pack, digest: Done, needs you (placeholders cap verdicts at AMBER until your real costs are in).

## Part 7: Remote conversion pipeline
Steps 1 to 5 Done: property intake, plan reader, layouts, compliance, drawings (DRAFT), economics, consent pack to AC1009, engineer review workflow, approvals, RFI tracker, timeline, capture guide, plan request pack, metrics.

## Part 8: Scale design
Approval Queue, touchpoint timing, Next Best Action, dashboard and weekly digest, capture portal (flagged off), playbooks and delta (engineers write the content once), batch engineer workflow, capacity planner: Done.

## Part 9: Best Use
Done (three columns, honest "best" rule, hazard rule tested).

## Tests by module (273)
| Module | Tests |
|---|---|
| Rules corpus (Stage 3) | 69 |
| Chat agent, SQL guard, read-only role | 38 |
| Economics, Offer Builder, worked example | 18 |
| Listings, matching, verdicts | 16 |
| Consent pack (AC1009, statements, register, gate, reviews, approvals, lodgement) | 15 |
| Development engine (evaluator, layout, finance, subdivision) | 12 |
| Property Record, DXF reader, plan review | 10 |
| Login and access control | 10 |
| Part 7 step 2 (layouts, drawings, compliance, briefs, gaps) | 8 |
| Bulk screening, portfolio, importers (8 + 4) | 12 |
| Placeholders | 7 |
| Workflow (RFI, timeline, certification, metrics) | 6 |
| Scenarios API | 6 |
| Part 8 scale | 6 |
| Outreach layer (flagged off) | 6 |
| Deal sheet, ranking, calibration, plan request | 5 |
| Feature flags and validation settings | 5 |
| Development flow, Best Use, Māori, playbooks, layers | 10 |
| Settings and map; digest, CRM, Trade Me | 7 |
| Forbidden words, demo, backups, browser smoke | 7 |

## Blocked on you
docs/BLOCKERS.md is the current list. Highest value first: `APP_PASSWORD` and `TS_AUTHKEY` (open the app on your iPhone: docs/IPHONE_TEST.md); reply to the 10 standards checks; Ngā Paerewa and Building Code documents (docs/sources_manual/README.md); the Council's AC1021, portal screens and fee schedule; your real running costs and QS quotes; stage probabilities and some logged minutes; engineer fees and playbook content; `BACKUP_PASSPHRASE` and the private backup repo; `ANTHROPIC_API_KEY` and model; HealthCERT list and census file; Trade Me keys.
