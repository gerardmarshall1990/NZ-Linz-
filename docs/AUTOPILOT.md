# AUTOPILOT checklist (read this first in a new session, then continue from the first unchecked item)

Rules (owner's autopilot instruction, 2026-10-18): never stop to ask; decide the safest conservative option and log one line in `docs/DECISIONS.md`; a value only the owner can give becomes a flagged placeholder or a PENDING line in `docs/BLOCKERS.md`; tests must pass before an item is done; no invented rules, rates or numbers; DRAFT stamps; nothing sent or lodged without an approval record; outreach behind feature flags (all off); commit after every item; milestone report of at most 8 lines (iPhone, test counts, blocked on owner).
Start of session: read MASTER_SPEC.md, this file, docs/STATUS.md. `bash scripts/db_up.sh` (Postgres stops between sessions). Tests: `python -m pytest -q` (run long ones in the background).

Status key: [x] done, [~] partly done (what is left in the note), [ ] not started, [P] pending on the owner.

## A. Make the app testable on the iPhone
- [x] A1 docs/IPHONE_TEST.md: setup steps, login, 3 DEMO listings, 10-step test script (done)
- [x] A2 `make demo-seed` / `make demo-clear`, DEMO badge, `make preflight` (done; opening on the iPhone itself is [P] on APP_PASSWORD + TS_AUTHKEY)

## B. Part 7 steps 4 and 5, plan request pack
- [x] B1 Consent pack, review workflow, completeness against AC1009 (151 lines), DRAFT stamps, upload slots, PS validity (90 days, register)  (done 2026-10-18)
- [x] B2 Plan request pack (email, Council LIM guidance, site visit form, request log)  (done)
- [x] B3 Approval records: table + API; gate review link issue, plan request "sent", lodgement record (done)
- [x] B4 Capture Guide generator (done)
- [x] B5 RFI tracker (done)
- [x] B6 Timeline widget, parallel tracks, milestones, human-minutes metrics (done; track lead times blank until owner sets them)

## C. Part 3
- [x] C1 Retrofit calibration loop (done)
- [x] C2 Deal Sheet PDF (done)
- [x] C3 Ranking and what-if sliders (done)
- [x] C4 Timeline scenarios target / delay (+13 weeks) feed the Offer Builder; contract has no phase split so it cannot (done)
- [x] C5 Certification checklist and lease conditions; policy templates only (done; Ministry steps PENDING, BLOCKERS 5)

## D. Part 6
- [x] D1 Digest and alerts, saved searches (in-app only; Digest tab) (done)
- [x] D2 CRM link: leads from listings with guardrails (source + lawful basis, do-not-contact, no tenants), behind the outreach flag (done)
- [x] D3 Trade Me connector ready for keys: off until terms read + keys set; CSV meanwhile; endpoint UNVERIFIED (done)

## E. Part 2 (development sites, Māori land)
- [x] E1 Rules evaluator: yards, coverage, impervious, landscaped, height, HIRB, outdoor living, dwelling size; UNKNOWN when a rule is not loaded; badge logic (done)
- [x] E2 Development layout engine, fit_units, subdivision_yield, dev financial engine (done)
- [x] E3 Services module, licence-aware, capacity UNKNOWN until letter (done; Watercare/Healthy Waters data not loaded, BLOCKERS 27)
- [x] E4 Site Panel buttons 1 to 3 for development sites: Develop tab, scenarios, report PDF, consent pack (done)
- [x] E5 Resource consent pack (draft; Council RC checklist unseen, council_verified false) (done)
- [x] E6 Best Use tab (done)
- [x] E7 Zone / overlay / hazard / Māori map layers (done)
- [x] E8 Māori land module (done; TPK export PENDING)
- [x] E9 Apartment playbook (done)

## F. Part 4
- [x] F1 Bulk Auckland screening: analytics.rh_screen (362k candidates), layers, filters, shortlists (done)
- [x] F2 House-scale and portfolio economics (done)
- [x] F3 Suburb analytics (done; certified beds and census PENDING, BLOCKERS 28)
- [x] F4 Field capture app, behind flag (done)
- [x] F5 CRM page, funnel by rep/suburb/source/type, audit log, behind flag (done)
- [x] F6 Route planning and call sheets, straight-line, behind flag (done)
- [x] F7 Offer generator: letters, emails, one-pagers, terms sheets, behind flag (done)

## G. Part 8
- [~] G1 Approval Queue (basic queue and Approvals tab done; extend to all draft kinds in G-phase)
- [ ] G2 Dashboard
- [ ] G3 Capture portal
- [~] G4 Playbooks and delta view (playbook skeletons + delta view done; engineers to write content once; UI to add)
- [ ] G5 Batch engineer workflow
- [ ] G6 Capacity planner

## H. Part 5 and close-out
- [ ] H1 Feeds admin page, importers, CONFLICTS.md
- [x] H2 Feature flags and validation report (done; re-run `make validate` at the end)
- [ ] H3 README refreshed, final backup, STATUS.md final

## Owner-blocked inputs (do not wait for these; see docs/BLOCKERS.md)
APP_PASSWORD, TS_AUTHKEY, BACKUP_PASSPHRASE + private backup repo, ANTHROPIC_API_KEY/MODEL, Ngā Paerewa and Building Code documents, HealthCERT list, AC1021 / portal screens / fee schedule, PS author register export, real costs and QS quotes, standards spot-checks, tolerance and chosen validation properties.
